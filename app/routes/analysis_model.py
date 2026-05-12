from flask import Blueprint, request, jsonify, render_template, send_file
import threading
import uuid
import json
import os
from datetime import datetime

from ..services.model_trainer import ModelTrainerService, TRAINING_STATUS, TRAINING_STATUS_LOCK

model_bp = Blueprint('analysisModel', __name__, url_prefix='/analysisModel')

trainer_service = ModelTrainerService()


@model_bp.route('/', methods=['GET'])
def model_train_page():
    return render_template('model_train.html')


@model_bp.route('/upload', methods=['POST'])
def upload_data():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.endswith('.jsonl'):
        return jsonify({'error': 'Only .jsonl files are supported'}), 400

    try:
        content = file.read().decode('utf-8')
    except Exception as e:
        return jsonify({'error': f'Failed to read file: {str(e)}'}), 400

    seed = request.form.get('seed', 42)
    try:
        seed = int(seed)
    except ValueError:
        seed = 42

    result = trainer_service.preprocess_uploaded_data(content, seed)

    if not result['success']:
        return jsonify({'error': result['message']}), 400

    task_id = str(uuid.uuid4())
    ModelTrainerService.init_task(task_id)

    with TRAINING_STATUS_LOCK:
        TRAINING_STATUS[task_id].update({
            'train_data': result['train_data'],
            'val_data': result['val_data'],
            'test_data': result['test_data'],
            'stats': result['stats'],
            'status': 'preprocessed',
            'model_type': None,
            'progress': {},
            'predictions': None,
            'result_dir': None
        })

    return jsonify({
        'success': True,
        'task_id': task_id,
        'stats': result['stats'],
        'message': f'Data loaded: {result["stats"]["total"]} samples (train: {result["stats"]["train"]}, val: {result["stats"]["val"]}, test: {result["stats"]["test"]})'
    })


@model_bp.route('/startTraining', methods=['POST'])
def start_training():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON data'}), 400

    task_id = data.get('task_id')
    model_type = data.get('model_type')

    if not task_id or not model_type:
        return jsonify({'error': 'Missing task_id or model_type'}), 400

    if model_type not in ['modernbert', 'gptsniffer']:
        return jsonify({'error': 'Invalid model_type. Must be modernbert or gptsniffer'}), 400

    with TRAINING_STATUS_LOCK:
        task_info = TRAINING_STATUS.get(task_id)
        if not task_info:
            return jsonify({'error': 'Task not found'}), 404
        if task_info.get('status') not in ['preprocessed', 'cancelled']:
            return jsonify({'error': f'Invalid task status: {task_info.get("status")}'}), 400

        train_data = task_info['train_data']
        val_data = task_info['val_data']
        test_data = task_info['test_data']
        task_info['status'] = 'training'
        task_info['model_type'] = model_type
        task_info['cancelled'] = False
        task_info['progress'] = {}

    params = {
        'seed': data.get('seed', 42),
        'epochs': data.get('epochs', 3 if model_type == 'modernbert' else 12),
        'batch_size': data.get('batch_size', 64 if model_type == 'modernbert' else 32),
        'learning_rate': data.get('learning_rate', 5e-5),
        'max_length': data.get('max_length', 512),
    }
    if model_type == 'modernbert':
        params['model_name'] = data.get('model_name', 'answerdotai/ModernBERT-base')
    else:
        params['model_name'] = data.get('model_name', 'microsoft/codebert-base')

    def progress_callback(key, value):
        with TRAINING_STATUS_LOCK:
            task = TRAINING_STATUS.get(task_id)
            if task:
                if key == 'predictions':
                    task['predictions'] = value
                elif key == 'result_dir':
                    task['result_dir'] = value
                elif key == 'test_metrics':
                    task['test_metrics'] = value
                elif key == 'epoch_metrics':
                    if 'epoch_metrics_list' not in task:
                        task['epoch_metrics_list'] = []
                    task['epoch_metrics_list'].append(value)
                elif key == 'log':
                    if 'log_list' not in task:
                        task['log_list'] = []
                    task['log_list'].append(value)
                elif key == 'tqdm':
                    task['progress']['tqdm'] = value
                else:
                    task['progress'][key] = value

    def run():
        try:
            trainer_service.run_training(
                task_id=task_id,
                train_data=train_data,
                val_data=val_data,
                test_data=test_data,
                model_type=model_type,
                progress_callback=progress_callback,
                params=params
            )
            with TRAINING_STATUS_LOCK:
                task = TRAINING_STATUS.get(task_id)
                if task and task.get('cancelled'):
                    task['status'] = 'cancelled'
                elif task:
                    task['status'] = 'completed'
        except Exception as e:
            with TRAINING_STATUS_LOCK:
                task = TRAINING_STATUS.get(task_id)
                if task:
                    task['status'] = 'failed'
                    task['error'] = str(e)
                    if 'log_list' not in task:
                        task['log_list'] = []
                    task['log_list'].append(f'ERROR: {str(e)}')

    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()

    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': f'Training started with {model_type}'
    })


@model_bp.route('/trainingProgress/<task_id>', methods=['GET'])
def get_training_progress(task_id):
    with TRAINING_STATUS_LOCK:
        task = TRAINING_STATUS.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        return jsonify({
            'task_id': task_id,
            'status': task.get('status'),
            'model_type': task.get('model_type'),
            'stats': task.get('stats'),
            'progress': task.get('progress', {}),
            'epoch_metrics_list': task.get('epoch_metrics_list', []),
            'test_metrics': task.get('test_metrics'),
            'predictions': task.get('predictions'),
            'log_list': task.get('log_list', []),
            'error': task.get('error'),
            'result_dir': task.get('result_dir')
        })


@model_bp.route('/cancelTraining', methods=['POST'])
def cancel_training():
    data = request.get_json()
    if not data or not data.get('task_id'):
        return jsonify({'error': 'Missing task_id'}), 400

    task_id = data['task_id']
    ModelTrainerService.cancel_training(task_id)

    with TRAINING_STATUS_LOCK:
        task = TRAINING_STATUS.get(task_id)
        if task and task.get('status') == 'training':
            task['status'] = 'cancelled'

    return jsonify({
        'success': True,
        'message': 'Training cancellation requested'
    })


@model_bp.route('/downloadPredictions/<task_id>', methods=['GET'])
def download_predictions(task_id):
    with TRAINING_STATUS_LOCK:
        task = TRAINING_STATUS.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        result_dir = task.get('result_dir')
        if not result_dir:
            return jsonify({'error': 'No result directory available'}), 400

    csv_path = os.path.join(result_dir, 'predictions.csv')
    if not os.path.exists(csv_path):
        return jsonify({'error': 'Predictions file not found'}), 404

    return send_file(
        csv_path,
        mimetype='text/csv',
        as_attachment=True,
        download_name='predictions.csv'
    )