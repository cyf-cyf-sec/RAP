from flask import Blueprint, request, jsonify, send_file, current_app
import threading
import uuid
import asyncio
from datetime import datetime
import json
import os
import zipfile
import io
import sys

from app.core.task_manager import TaskManager
from ..utils.error_handling import error_handler
from ..services.code_analyzer import CodeAnalyzer
from ..services.deduplication import Deduplication
from ..services.code_generator import CodeGenerator

code_bp = Blueprint('analysisCode', __name__)

@code_bp.route('/extractFunctions', methods=['POST'], endpoint='extractFunctions')
@error_handler
def start_function_extraction():
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Invalid JSON data'}), 400
    
    required_fields = ['pr_details_path', 'code_files_path']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    task_id = str(uuid.uuid4())
    
    pr_details_path = data['pr_details_path']
    code_files_path = data['code_files_path']
    thread_count = data.get('thread_count', 4)
    
    print(f"Received function extraction request for PR details: {pr_details_path}")
    print(f"Code files path: {code_files_path}")

    code_analyzer = CodeAnalyzer()
    
    def run_function_extraction():
        try:
            def progress_callback(processed_files, total_files, extracted_functions=0):
                TaskManager.update_task(task_id, {
                    'progress_data': {
                        'processed_count': processed_files,
                        'total_count': total_files,
                        'extracted_functions': extracted_functions,
                        'status': 'running',
                        'last_updated': datetime.now().isoformat()
                    }
                })

            result = code_analyzer.construct_datasets(
                pr_details_path=pr_details_path,
                code_files_path=code_files_path,
                thread_count=thread_count,
                progress_callback=progress_callback
            )
            
            stats = result.get('stats', {})
            total_functions = stats.get('total_functions', 0)
            total_files = stats.get('total_files', 0)
            agent_stats = stats.get('agent_stats', {})
            
            TaskManager.update_task(task_id, {
                'status': 'completed',
                'result': result,
                'completed_at': datetime.now().isoformat(),
                'progress_data': {
                    'status': 'completed',
                    'last_updated': datetime.now().isoformat(),
                    'output_file': result.get('output_dir', ''),
                    'total_functions': total_functions,
                    'extracted_functions': total_functions,
                    'total_files': total_files,
                    'processed_files': total_files,
                    'stats': stats,
                    'agent_stats': agent_stats,
                    'results': result.get('results', [])
                }
            })
                
        except Exception as e:
            TaskManager.update_task(task_id, {
                'status': 'failed',
                'error': str(e),
                'completed_at': datetime.now().isoformat(),
                'progress_data': {
                    'status': 'failed',
                    'error': str(e),
                    'last_updated': datetime.now().isoformat()
                }
            })
    
    TaskManager.add_task(task_id, {
        'status': 'running',
        'started_at': datetime.now().isoformat(),
        'type': 'function_extraction',
        'progress_data': {
            'status': 'running',
            'last_updated': datetime.now().isoformat()
        }
    })
    
    thread = threading.Thread(target=run_function_extraction)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'task_id': task_id,
        'status': 'started',
        'message': 'Function extraction started',
        'task_type': 'function_extraction'
    })

@code_bp.route('/taskStatus/<task_id>', methods=['GET'], endpoint='taskStatus')
def get_task_status(task_id):
    with tasks_lock:
        task = tasks.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        return jsonify({
            'task_id': task_id,
            'status': task['status'],
            'started_at': task.get('started_at'),
            'completed_at': task.get('completed_at'),
            'error': task.get('error'),
            'result': task.get('result')
        })

@code_bp.route('/deduplicateCode', methods=['POST'], endpoint='deduplicateCode')
@error_handler
def deduplicate_code():
    """Code deduplication endpoint"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON data'}), 400
    
    required_fields = ['input_path']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    task_id = str(uuid.uuid4())
    
    input_path = data['input_path']
    
    print(f"Received code deduplication request for input path: {input_path}")
    
    deduplication_service = Deduplication()
    
    def run_deduplication():
        try:
            result = deduplication_service.deduplicate_functions(
                input_path=input_path
            )

            if result.get('success') and 'stats' in result:
                stats = result['stats']
                TaskManager.update_task(task_id, {
                    'status': 'completed',
                    'result': result,
                    'completed_at': datetime.now().isoformat(),
                    'progress_data': {
                        'status': 'completed',
                        'remaining_count': stats.get('unique_count', 0),
                        'remaining_functions': stats.get('unique_count', 0),
                        'original_count': stats.get('original_count', 0),
                        'output_file': result.get('output_path', ''),
                        'deduplication_rate': stats.get('deduplication_rate', 0),
                        'agent_stats': stats.get('agent_stats', {}),
                        'last_updated': datetime.now().isoformat()
                    }
                })
            else:
                TaskManager.update_task(task_id, {
                    'status': 'failed',
                    'result': result,
                    'completed_at': datetime.now().isoformat(),
                    'progress_data': {
                        'status': 'failed',
                        'error': result.get('message', 'Unknown error'),
                        'last_updated': datetime.now().isoformat()
                    }
                })
                
        except Exception as e:
            TaskManager.update_task(task_id, {
                'status': 'failed',
                'error': str(e),
                'completed_at': datetime.now().isoformat(),
                'progress_data': {
                    'status': 'failed',
                    'error': str(e),
                    'last_updated': datetime.now().isoformat()
                }
            })
    
    TaskManager.add_task(task_id, {
        'status': 'running',
        'started_at': datetime.now().isoformat(),
        'type': 'code_deduplication',
        'progress_data': {
            'status': 'running',
            'last_updated': datetime.now().isoformat()
        }
    })
    
    thread = threading.Thread(target=run_deduplication)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'task_id': task_id,
        'status': 'started',
        'message': 'Code deduplication started',
        'task_type': 'code_deduplication'
    })

@code_bp.route('/generateAgentCode', methods=['POST'], endpoint='generateAgentCode')
@error_handler
def generate_agent_code():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON data'}), 400
    
    required_fields = ['function_file_path', 'provider']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    task_id = str(uuid.uuid4())
    
    function_file_path = data['function_file_path']
    provider = data['provider']
    model = data.get('model', '')
    api_key = data.get('api_key', '')
    endpoint = data.get('endpoint', '')
    temperature = data.get('temperature', 0.2)
    max_tokens = data.get('max_tokens', 4096)
    
    print(f"Received agent code generation request for: {function_file_path}")
    print(f"Provider: {provider}, Model: {model}")
    
    code_generator = CodeGenerator()
    
    def run_code_generation():
        try:
            def progress_callback(generated_count, total_count):
                TaskManager.update_task(task_id, {
                    'progress_data': {
                        'generated_count': generated_count,
                        'total_count': total_count,
                        'status': 'running',
                        'last_updated': datetime.now().isoformat()
                    }
                })
            
            result = code_generator.generate_agent_functions(
                function_file_path=function_file_path,
                provider=provider,
                model=model,
                api_key=api_key,
                endpoint=endpoint,
                temperature=temperature,
                max_tokens=max_tokens,
                progress_callback=progress_callback
            )
            
            if result.get('success'):
                TaskManager.update_task(task_id, {
                    'status': 'completed',
                    'result': result,
                    'completed_at': datetime.now().isoformat(),
                    'progress_data': {
                        'status': 'completed',
                        'last_updated': datetime.now().isoformat(),
                        'generated_count': result.get('generated_count', 0),
                        'total_count': result.get('total_count', 0),
                        'agent_stats': result.get('agent_stats', {}),
                        'output_file': result.get('output_file', '')
                    }
                })
            else:
                TaskManager.update_task(task_id, {
                    'status': 'failed',
                    'error': result.get('message', 'Unknown error'),
                    'completed_at': datetime.now().isoformat(),
                    'progress_data': {
                        'status': 'failed',
                        'error': result.get('message', 'Unknown error'),
                        'last_updated': datetime.now().isoformat()
                    }
                })
                
        except Exception as e:
            TaskManager.update_task(task_id, {
                'status': 'failed',
                'error': str(e),
                'completed_at': datetime.now().isoformat(),
                'progress_data': {
                    'status': 'failed',
                    'error': str(e),
                    'last_updated': datetime.now().isoformat()
                }
            })
    
    TaskManager.add_task(task_id, {
        'status': 'running',
        'started_at': datetime.now().isoformat(),
        'type': 'code_generation',
        'progress_data': {
            'status': 'running',
            'last_updated': datetime.now().isoformat()
        }
    })
    
    thread = threading.Thread(target=run_code_generation)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'task_id': task_id,
        'status': 'started',
        'message': 'Agent code generation started',
        'task_type': 'code_generation'
    })

@code_bp.route('/downloadDataset', methods=['POST'], endpoint='downloadDataset')
@error_handler
def download_dataset():
    try:
        data = request.get_json()
        input_path = data.get('input_path')
        
        if not input_path:
            return jsonify({'error': 'Missing input_path parameter'}), 400
        
        
        input_path = os.path.abspath(input_path)
        basename = os.path.basename(input_path)
        memory_file = io.BytesIO()
        
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(input_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, input_path)
                    zf.write(file_path, arcname)
        
        memory_file.seek(0)    
        zip_filename = f"{basename}.zip"
        
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500