from flask import Blueprint, request, jsonify, current_app
import threading
import uuid
import asyncio
from datetime import datetime
import json
from app.core.task_manager import TaskManager
from ..services.file_analyzer import FileAnalyzer
from ..utils.error_handling import error_handler

file_bp = Blueprint('analysisFile', __name__)

@file_bp.route('/downloadFiles', methods=['POST'], endpoint='downloadFiles')
@error_handler
def start_file_analysis():

    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Invalid JSON data'}), 400
    
    required_fields = ['pr_details_path']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    task_id = str(uuid.uuid4())
    
    pr_details_path = data['pr_details_path']
    github_token = data.get('github_token', '')
    thread_count = data.get('thread_count', 4)

    if not github_token:
        github_token = current_app.config.get('GITHUB_TOKEN', '')

    file_analyzer = FileAnalyzer()
    
    def run_file_analysis():
        try:
            def progress_callback(progress_info):
                task = TaskManager.get_task(task_id)
                if task:
                    if isinstance(progress_info, dict):
                        TaskManager.update_task(task_id, {
                            'progress_data': {
                                'processed_count': progress_info.get('processed_count', 0),
                                'total_count': progress_info.get('total_count', 0),
                                'status': 'running',
                                'current_type': progress_info.get('current_type', ''),
                                'code_files': progress_info.get('code_files', 0),
                                'downloaded_files': progress_info.get('downloaded_files', 0),
                                'failed_files': progress_info.get('failed_files', 0),
                                'total_files': progress_info.get('total_files', 0),
                                'last_updated': datetime.now().isoformat()
                            }
                        })
                    else:
                        processed_count, total_count = progress_info
                        TaskManager.update_task(task_id, {
                            'progress_data': {
                                'processed_count': processed_count,
                                'total_count': total_count,
                                'status': 'running',
                                'last_updated': datetime.now().isoformat()
                            }
                        })

            result = file_analyzer.analyze_files(
                pr_details_path=pr_details_path,
                github_token=github_token,
                thread_count=thread_count,
                progress_callback=progress_callback
            )
            
            if result.get('success'):
                total_files = result.get('total_files', 0)
                code_files = result.get('code_files', 0)
                downloaded_files = result.get('downloaded_files', 0)
                failed_files = result.get('failed_files', 0)
                file_results = result.get('file_results', [])
                TaskManager.update_task(task_id, {
                    'status': 'completed',
                    'result': result,
                    'completed_at': datetime.now().isoformat(),
                    'progress_data': {
                        'processed_count': total_files,
                        'total_count': total_files,
                        'status': 'completed',
                        'last_updated': datetime.now().isoformat(),
                        'output_file': result.get('output_path', ''),
                        'total_files': total_files,
                        'code_files': code_files,
                        'downloaded_files': downloaded_files,
                        'failed_files': failed_files,
                        'file_results': file_results
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
        'type': 'file_analysis',
        'progress_data': {
            'processed_count': 0,
            'total_count': 0,
            'status': 'running',
            'current_page': 0,
            'last_updated': datetime.now().isoformat()
        }
    })
    
    thread = threading.Thread(target=run_file_analysis)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'task_id': task_id,
        'status': 'started',
        'message': 'File analysis started',
        'task_type': 'file_analysis'
    })



