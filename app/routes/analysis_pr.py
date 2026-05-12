from flask import Blueprint, request, jsonify, current_app
import threading
import uuid
import asyncio
from datetime import datetime
import json

from app.core.task_manager import TaskManager
from ..services.pr_crawler import PRCrawler
from ..services.pr_classifier import PRClassifier
from ..services.pr_detail_crawler import PRDetailCrawler
from ..utils.error_handling import error_handler

pr_bp = Blueprint('analysisPR', __name__)

@pr_bp.route('/crawlPRList', methods=['POST'], endpoint='crawlPRList')
@error_handler
def pr_list_crawling():

    data = request.get_json()

    if not data:
        return jsonify({'error': 'Invalid JSON data'}), 400
    
    required_fields = ['repo_url']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    task_id = str(uuid.uuid4())
    
    repo_url = data['repo_url']
    github_token = data.get('github_token', '')
    thread_count_str = data.get('thread_count', '4')
    thread_count = int(thread_count_str) if thread_count_str and thread_count_str.strip() else 4

    
    if not github_token:
        github_token = current_app.config.get('GITHUB_TOKEN', '')
    
    crawler = PRCrawler("results/pr_list")
    
    def run_pr_crawling():
        try:
            def progress_callback(current_page, processed_prs):
                task = TaskManager.get_task(task_id)
                if task:
                    existing_pr_count = task.get('progress_data', {}).get('pr_count', 0)
                    actual_pr_count = max(existing_pr_count, processed_prs)
                    
                    TaskManager.update_task(task_id, {
                        'progress_data': {
                            'pr_count': actual_pr_count,
                            'output_file': '',
                            'total_prs': 0,
                            'status': 'running',
                            'current_page': current_page,
                            'last_updated': datetime.now().isoformat()
                        }
                    })
            
            result = crawler.crawl(
                repo_url=repo_url,
                github_token=github_token,
                thread_count=thread_count,
                progress_callback=progress_callback
            )
            
            if result.get('success'):
                TaskManager.update_task(task_id, {
                    'status': 'completed',
                    'result': result,
                    'completed_at': datetime.now().isoformat(),
                    'progress_data': {
                        'pr_count': result.get('total_prs', 0),
                        'output_file': result.get('output_file', ''),
                        'total_prs': result.get('total_prs', 0),
                        'status': 'completed',
                        'last_updated': datetime.now().isoformat()
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
        'repo_url': repo_url,
        'crawler': crawler,
        'type': 'pr_crawl',
        'progress_data': {
            'output_file': '',
            'total_prs': 0,
            'status': 'running'
        }
    })
    
    thread = threading.Thread(target=run_pr_crawling)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'task_id': task_id,
        'status': 'started',
        'message': 'PR list crawling started',
        'task_type': 'pr_crawl'
    })

@pr_bp.route('/classifyPRs', methods=['POST'], endpoint='classifyPRs')
@error_handler
def start_pr_classification():
    """PR classification endpoint - Classify crawled PR list"""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Missing data'}), 400
    
    required_fields = ['pr_file_path']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    task_id = str(uuid.uuid4())
    
    pr_file_path = data['pr_file_path']
    start_date = data.get('start_date', '')
    end_date = data.get('end_date', '')
    
    classifier = PRClassifier()
    
    def run_pr_classification():
        try:
            def progress_callback(processed_count, total_count, stats=None):
                task = TaskManager.get_task(task_id)
                if task:
                    TaskManager.update_task(task_id, {
                        'progress_data': {
                            'processed_count': processed_count,
                            'total_count': total_count,
                            'status': 'running',
                            'last_updated': datetime.now().isoformat(),
                            'statistics': stats or {}
                        }
                    })

            result = classifier.classify_prs(
                start_date=start_date,
                end_date=end_date,
                pr_file_path=pr_file_path,
                progress_callback=progress_callback
            )
            
            
            if result.get('success'):
                TaskManager.update_task(task_id, {
                    'status': 'completed',
                    'result': result,
                    'completed_at': datetime.now().isoformat(),
                    'progress_data': {
                        'processed_count': result.get('statistics', {}).get('total_input_prs', 0),
                        'total_count': result.get('statistics', {}).get('total_input_prs', 0),
                        'status': 'completed',
                        'last_updated': datetime.now().isoformat(),
                        'output_path': result.get('output_path', ''),
                        'human_prs': result.get('human_prs', 0),
                        'agent_prs': result.get('agent_prs', 0),
                        'agent_breakdown': result.get('agent_breakdown', {}),
                        'statistics': result.get('statistics', {})
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
        'classifier': classifier,
        'type': 'pr_classification',
        'progress_data': {
            'processed_count': 0,
            'total_count': 0,
            'status': 'running',
            'last_updated': datetime.now().isoformat()
        }
    })
    
    thread = threading.Thread(target=run_pr_classification)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'task_id': task_id,
        'status': 'started',
        'message': f'PR classification task submitted',
        'task_type': 'pr_classification',
    })


@pr_bp.route('/crawlPRDetails', methods=['POST'], endpoint='crawlPRDetails')
@error_handler
def start_pr_details_crawling():
    data = request.get_json()
    print(data)
    
    if not data:
        return jsonify({'error': 'Invalid JSON data'}), 400
    
    required_fields = ['pr_file_path']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    task_id = str(uuid.uuid4())
    
    pr_file_path = data['pr_file_path']
    github_token = data.get('github_token', '')
    thread_count = data.get('thread_count', 4)

    if not github_token:
        github_token = current_app.config.get('GITHUB_TOKEN', '')
    
    print(f"Received PR details crawling request for file: {pr_file_path}")
    
    crawler = PRDetailCrawler()
    
    def run_pr_details_crawling():
        try:
            def progress_callback(processed_count, total_count, current_page=None):
                task = TaskManager.get_task(task_id)
                if task:
                    TaskManager.update_task(task_id, {
                        'progress_data': {
                            'processed_count': processed_count,
                            'total_count': total_count,
                            'status': 'running',
                            'current_page': current_page or 0,
                            'last_updated': datetime.now().isoformat()
                        }
                    })

            result = crawler.crawl_pr_details(
                pr_file_path=pr_file_path,
                github_token=github_token,
                thread_count=thread_count,
                progress_callback=progress_callback
            )
            
            print(f"PR详情爬取结果: {result}")
            
            if result.get('success'):
                total_prs = result.get('total_actual_crawled', result.get('total_prs', 0))
                total_count = result.get('total_original_prs', total_prs)
                TaskManager.update_task(task_id, {
                    'status': 'completed',
                    'result': result,
                    'completed_at': datetime.now().isoformat(),
                    'progress_data': {
                        'processed_count': total_prs,
                        'total_count': total_count,
                        'status': 'completed',
                        'last_updated': datetime.now().isoformat(),
                        'output_file': result.get('output_file', ''),
                        'statistics': result.get('statistics', {})
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
        'pr_file_path': pr_file_path,
        'crawler': crawler,
        'type': 'pr_details_crawl',
        'progress_data': {
            'processed_count': 0,
            'total_count': 0,
            'status': 'running',
            'current_page': 0,
            'last_updated': datetime.now().isoformat()
        }
    })
    
    thread = threading.Thread(target=run_pr_details_crawling)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'task_id': task_id,
        'status': 'started',
        'message': 'PR details crawling started',
        'task_type': 'pr_details_crawl'
    })

@pr_bp.route('/task-progress/<task_id>', methods=['GET'])
@error_handler
def get_task_progress(task_id):
    """Get task progress information"""
    task = TaskManager.get_task(task_id)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    progress_info = {
        'task_id': task_id,
        'status': task['status'],
        'current_task': task.get('type', 'unknown'),
        'started_at': task.get('started_at', ''),
        'completed_at': task.get('completed_at', ''),
        'error': task.get('error', '')
    }

    if 'progress_data' in task:
        progress_info['progress_data'] = task['progress_data']

        if task['type'] == 'pr_crawl':
            progress_data = task.get('progress_data', {})
            pr_count = progress_data.get('pr_count', 0)
            total_prs = progress_data.get('total_prs', 0)

            percentage = 0
            if task['status'] == 'completed':
                percentage = 100
            elif total_prs > 0:
                percentage = min(99, int((pr_count / total_prs) * 100))
            elif pr_count > 0:
                percentage = min(50, int(pr_count / 10))
            
            progress_info['tasks'] = {
                'pr_crawler': {
                    'current': pr_count,
                    'total': total_prs,
                    'percentage': percentage,
                    'status': task['status'],
                    'message': f"Crawled {pr_count} PRs" if task['status'] == 'running' else f"Crawled {pr_count} PRs (completed)",
                    'current_page': progress_data.get('current_page', 0),
                    'last_updated': progress_data.get('last_updated', ''),
                    'output_file': progress_data.get('output_file', '')
                }
            }
        elif task['type'] == 'pr_details_crawl':
            progress_data = task.get('progress_data', {})
            processed_count = progress_data.get('processed_count', 0)
            total_count = progress_data.get('total_count', 0)

            percentage = 0
            if task['status'] == 'completed':
                percentage = 100
            elif total_count > 0:
                percentage = min(99, int((processed_count / total_count) * 100))
            
            progress_info['tasks'] = {
                'commit_crawler': {
                    'current': processed_count,
                    'total': total_count,
                    'percentage': percentage,
                    'status': task['status'],
                    'message': f"Processed {processed_count}/{total_count} PRs" if task['status'] == 'running' else f"Completed {processed_count}/{total_count} PR details",
                    'current_page': progress_data.get('current_page', 0),
                    'last_updated': progress_data.get('last_updated', ''),
                    'output_file': progress_data.get('output_file', '')
                }
            }
        elif task['type'] == 'file_analysis':
            progress_data = task.get('progress_data', {})
            processed_count = progress_data.get('processed_count', 0)
            total_count = progress_data.get('total_count', 0)
            
            percentage = 0
            if task['status'] == 'completed':
                percentage = 100
            elif total_count > 0:
                percentage = min(99, int((processed_count / total_count) * 100))
            
            current_type = progress_data.get('current_type', '')
            if task['status'] == 'running' and current_type:
                message = f"Processed {current_type} for ({processed_count}/{total_count} files)"
            elif task['status'] == 'completed':
                downloaded = progress_data.get('downloaded_files', 0)
                failed = progress_data.get('failed_files', 0)
                message = f"Download complete: {downloaded} successful, {failed} failed"
            else:
                message = f"Processed {processed_count}/{total_count} files"
            
            progress_info['tasks'] = {
                'file_crawler': {
                    'current': processed_count,
                    'total': total_count,
                    'percentage': percentage,
                    'status': task['status'],
                    'message': message,
                    'current_type': current_type,
                    'last_updated': progress_data.get('last_updated', ''),
                    'output_file': progress_data.get('output_file', ''),
                    'total_files': progress_data.get('total_files', 0),
                    'code_files': progress_data.get('code_files', 0),
                    'downloaded_files': progress_data.get('downloaded_files', 0),
                    'failed_files': progress_data.get('failed_files', 0),
                    'file_results': progress_data.get('file_results', [])
                }
            }
        elif task['type'] == 'function_extraction':
            progress_data = task.get('progress_data', {})
            processed_files = progress_data.get('processed_count', 0)
            total_files = progress_data.get('total_count', 0)
            extracted_functions = progress_data.get('extracted_functions', 0)
            
            percentage = 0
            if task['status'] == 'completed':
                percentage = 100
            elif total_files > 0:
                percentage = min(99, int((processed_files / total_files) * 100))
            
            if task['status'] == 'running':
                message = f"Processed {processed_files}/{total_files} files"
            elif task['status'] == 'completed':
                total_funcs = progress_data.get('total_functions', 0)
                message = f"Extraction complete: {extracted_functions} functions"
            else:
                message = "Function extraction"
            
            progress_info['tasks'] = {
                'function_extractor': {
                    'current': processed_files,
                    'total': total_files,
                    'percentage': percentage,
                    'status': task['status'],
                    'message': message,
                    'last_updated': progress_data.get('last_updated', ''),
                    'output_file': progress_data.get('output_file', ''),
                    'total_functions': progress_data.get('total_functions', 0),
                    'extracted_functions': extracted_functions,
                    'processed_files': processed_files,
                    'total_files': total_files,
                    'agent_stats': progress_data.get('agent_stats', {}),
                    'results': progress_data.get('results', [])
                }
            }
        elif task['type'] == 'code_deduplication':
            progress_data = task.get('progress_data', {})
            remaining_count = progress_data.get('remaining_count', 0)
            original_count = progress_data.get('original_count', 0)
            
            percentage = 0
            if task['status'] == 'completed':
                percentage = 100
            
            if task['status'] == 'running':
                message = "Deduplicating..."
            elif task['status'] == 'completed':
                message = f"Deduplication complete: {remaining_count}/{original_count}"
            else:
                  message = "Code deduplication"
            
            progress_info['tasks'] = {
                'deduplication': {
                    'remaining_count': remaining_count,
                    'original_count': original_count,
                    'percentage': percentage,
                    'status': task['status'],
                    'message': message,
                    'last_updated': progress_data.get('last_updated', ''),
                    'output_file': progress_data.get('output_file', ''),
                    'deduplication_rate': progress_data.get('deduplication_rate', 0),
                    'agent_stats': progress_data.get('agent_stats', {})
                }
            }
        elif task['type'] == 'code_generation':
            progress_data = task.get('progress_data', {})
            generated_count = progress_data.get('generated_count', 0)
            total_count = progress_data.get('total_count', 0)
            
            percentage = 0
            if task['status'] == 'completed':
                percentage = 100
            elif total_count > 0:
                percentage = min(99, int((generated_count / total_count) * 100))
            
            if task['status'] == 'running':
                message = f"Generating {generated_count}/{total_count}"
            elif task['status'] == 'completed':
                message = f"Generation complete: {generated_count} functions"
            else:
                message = "Code generation"
            
            progress_info['tasks'] = {
                'code_generation': {
                    'generated_count': generated_count,
                    'total_count': total_count,
                    'percentage': percentage,
                    'status': task['status'],
                    'message': message,
                    'last_updated': progress_data.get('last_updated', ''),
                    'output_file': progress_data.get('output_file', ''),
                    'agent_stats': progress_data.get('agent_stats', {})
                }
            }
        
        return jsonify(progress_info)


@pr_bp.route('/cancelTask/<task_id>', methods=['POST'])
@error_handler
def cancel_task(task_id):
    task = TaskManager.get_task(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    TaskManager.update_task(task_id, {
        'cancelled': True,
        'status': 'cancelled'
    })

    return jsonify({
        'success': True,
        'message': 'Task cancellation requested'
    })

