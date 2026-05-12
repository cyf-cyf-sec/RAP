import json
import os
import requests
from typing import Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote
from pathlib import Path
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from app.utils.code_utils import LANGUAGE_NAME_MAP

class FileAnalyzer:    
    def __init__(self, output_dir: str = "results/code_files"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
    
    def analyze_files(self, pr_details_path: str, github_token: str, 
                     thread_count: int = 4, 
                     progress_callback: Callable[[int, int], None] = None) -> Dict[str, any]:

        try:

            return self._analyze(pr_details_path, github_token, thread_count, progress_callback)
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to analyze files: {str(e)}',
                'total_files': 0,
                'downloaded_files': 0
            }
    
    def _analyze_single_file(self, file_path: str, github_token: str, output_dir: str, 
                           thread_count: int, progress_callback: Callable[[int, int], None] = None) -> Dict[str, any]:
        pr_list = self._read_prs_from_file(file_path)
        
        if not pr_list:
            return {
                'success': False,
                'message': 'No PRs found in the file',
                'total_files': 0,
                'downloaded_files': 0
            }

        filename = os.path.basename(file_path)
        type = filename.split('.')[0]
        
        download_results = self._download_code_files_multithreaded(
            pr_list=pr_list,
            output_dir=output_dir,
            type=type,
            github_token=github_token,
            max_workers=thread_count,
            progress_callback=progress_callback
        )
        
        return {
            'success': True,
            'message': f'Successfully downloaded {download_results["downloaded_files"]} code files',
            'total_files': download_results['total_files'],
            'code_files': download_results['code_files'],
            'downloaded_files': download_results['downloaded_files'],
            'failed_files': download_results['failed_files'],
            'basename': type
        }

    def _analyze(self, directory_path: str, github_token: str, 
                         thread_count: int, progress_callback: Callable[[int, int], None] = None) -> Dict[str, any]:

        basename = os.path.basename(directory_path)
        output_dir = os.path.join(self.output_dir, basename)
        files = []
        for filename in os.listdir(directory_path):
            if filename.endswith('.jsonl'):
                filepath = os.path.join(directory_path, filename)
                files.append(filepath)
        
        if not files:
            return {
                'success': False,
                'message': f'No .jsonl files found in directory: {directory_path}',
                'total_files': 0,
                'downloaded_files': 0
            }
        
        results = []
        total_files = 0
        downloaded_files = 0
        failed_files = 0
        code_files = 0
        
        for filepath in files:
            name = Path(filepath).stem
            filename = os.path.basename(filepath)
            
            result = self._analyze_single_file(filepath, github_token, output_dir, thread_count, progress_callback)
            results.append({
                'type': name,
                'result': result
            })
            
            if result['success']:
                total_files += result['total_files']
                code_files += result['code_files']
                downloaded_files += result['downloaded_files']
                failed_files += result.get('failed_files', 0)
        
        successful_files = [r for r in results if r['result']['success']]
        failed_files_count = [r for r in results if not r['result']['success']]
        
        return {
            'success': True,
            'message': f'Successfully analyzed {len(successful_files)} files, failed {len(failed_files_count)} files',
            'total_files': total_files,
            'code_files': code_files,
            'downloaded_files': downloaded_files,
            'failed_files': failed_files,
            'file_results': results,
            'output_path': output_dir
        }
    
    def _read_prs_from_file(self, filepath: str) -> List[Dict]:
        pr_list = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            pr_data = json.loads(line)
                            pr_list.append(pr_data)
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON parse error {filepath}: {e}")
                            continue
        except Exception as e:
            print(f"Failed to read file {filepath}: {e}")
            raise
        
        return pr_list
    
    def _download_code_files_multithreaded(self, pr_list: List[Dict], output_dir: str, type: str,
                                          github_token: str, max_workers: int = 4,
                                          progress_callback: Callable[[int, int], None] = None) -> Dict[str, any]:
        
        files_to_download = []
        total_files = 0
        
        for pr in pr_list:
            pr_number = pr.get('number')
            if not pr_number:
                continue

            for commit in pr.get('commits_list', []):
                commit_sha = commit.get('sha')
                if not commit_sha:
                    continue
                
                for file_info in commit.get('files', []):
                    filename = file_info.get('filename', '')
                    raw_url = file_info.get('raw_url', '')

                    file_ext = Path(filename).suffix.lower()
                    total_files += 1
                    if file_ext in LANGUAGE_NAME_MAP.keys() and raw_url:
                        files_to_download.append({
                            'pr_number': pr_number,
                            'commit_sha': commit_sha,
                            'filename': filename,
                            'raw_url': raw_url,
                            'output_dir': output_dir,
                            'type': type
                        })
        
        code_files = len(files_to_download)
        downloaded_files = 0
        failed_files = 0
        
        if progress_callback:
            progress_callback({
                'processed_count': 0,
                'total_count': total_files,
                'current_type': type,
                'code_files': code_files,
                'downloaded_files': 0,
                'failed_files': 0,
                'total_files': total_files
            })
        
        def download_single_file(file_info: Dict) -> bool:
            try:
                return self._download_file(file_info, github_token)
            except Exception as e:
                print(f"Failed to download file {file_info['filename']}: {e}")
                return False

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(download_single_file, file_info): file_info for file_info in files_to_download}
            
            for future in as_completed(future_to_file):
                try:
                    success = future.result()
                    if success:
                        downloaded_files += 1
                    else:
                        failed_files += 1
                    
                    if progress_callback:
                        progress_callback({
                            'processed_count': downloaded_files + failed_files,
                            'total_count': total_files,
                            'current_type': type,
                            'code_files': code_files,
                            'downloaded_files': downloaded_files,
                            'failed_files': failed_files,
                            'total_files': total_files
                        })
                        
                except Exception as e:
                    print(f"File download task failed: {e}")
                    failed_files += 1
        
        return {
            'total_files': total_files,
            'code_files': code_files,
            'downloaded_files': downloaded_files,
            'failed_files': failed_files
        }
    
    def _download_file(self, file_info: Dict, github_token: str) -> bool:
        """Download single file"""
        pr_number = file_info['pr_number']
        commit_sha = file_info['commit_sha']
        filename = file_info['filename']
        raw_url = file_info['raw_url']
        output_dir = file_info['output_dir']
        type = file_info['type']
        
        # Build save path: results/code_files/basename//type/pr_number/commit_sha/filename
        save_dir = os.path.join(output_dir, type, str(pr_number), commit_sha)
        os.makedirs(save_dir, exist_ok=True)
        
        save_path = os.path.join(save_dir, Path(filename).name)

        if os.path.exists(save_path):
            return True

        session = requests.Session()

        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        headers = {
            'User-Agent': 'Mozilla/5.0'
        }
        
        if github_token:
            headers['Authorization'] = f'token {github_token}'
        
        try:
            response = session.get(raw_url, headers=headers, timeout=30)
            response.raise_for_status()

            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            return True
        
        except Exception as e:
            print(f"Failed to download file {filename}: {e}")
            return False