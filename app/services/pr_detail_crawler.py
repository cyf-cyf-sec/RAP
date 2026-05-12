import json
import os
from typing import Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastcore.xtras import obj2dict
from ..utils.github_api import GitHubRepo, TokenPool

class PRDetailCrawler:
    """PR Detail Crawler"""
    
    def __init__(self, output_dir: str = "results/pr_details"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def crawl_pr_details(self, pr_file_path: str, github_token: str, 
                        thread_count: int = 4, 
                        progress_callback: Callable[[int, int], None] = None) -> Dict[str, any]:

        try:
            basename, repo_owner, repo_name = self._parse_repo(pr_file_path)
            print(repo_owner, repo_name)
            token_pool = TokenPool([github_token] if github_token else [])
            repo = GitHubRepo(repo_owner, repo_name, token_pool)

            jsonl_files = []
            for filename in os.listdir(pr_file_path):
                if filename.endswith('.jsonl'):
                    filepath = os.path.join(pr_file_path, filename)
                    jsonl_files.append(filepath)
            
            if not jsonl_files:
                return {
                    'success': False,
                    'message': f'No .jsonl files found in directory: {pr_file_path}',
                    'total_prs': 0,
                    'crawled_prs': 0
                }

            all_pr_lists = []
            total_total_prs = 0
            for filepath in jsonl_files:
                pr_list = self._read_prs_from_file(filepath)
                all_pr_lists.append((filepath, pr_list))
                total_total_prs += len(pr_list)

            
            results = []
            total_original_prs = 0
            total_actual_crawled = 0
            global_completed_count = 0
            
            for filepath, pr_list in all_pr_lists:
                filename = os.path.basename(filepath)
                file_type = filename.split('.')[0]
                
                if not pr_list:
                    results.append({
                        'file': filename,
                        'result': {
                            'success': False,
                            'message': 'No PRs found in file',
                            'original_total_prs': 0,
                            'actual_crawled_prs': 0,
                            'output_file': ''
                        }
                    })
                    continue
                
                # Create callback with global progress tracking
                file_start_count = global_completed_count  # Record count before current file starts
                def create_progress_tracker():
                    def track_progress(completed_in_file, total_in_file):
                        nonlocal global_completed_count
                        # Update global progress: count before current file + completed in current file
                        global_completed_count = file_start_count + completed_in_file
                        if progress_callback:
                            progress_callback(global_completed_count, total_total_prs)
                    return track_progress
                
                detailed_prs = self._crawl_pr_details_multithreaded(
                    pr_list=pr_list,
                    repo=repo,
                    max_workers=thread_count,
                    progress_callback=create_progress_tracker()
                )
                
                # Save results
                output_file, output_path = self._save_detailed_prs(
                    detailed_prs=detailed_prs,
                    basename=basename,
                    file_name=filename
                )
                
                result = {
                    'success': True,
                    'message': f'Successfully crawled {len(detailed_prs)} PR details',
                    'original_total_prs': len(pr_list),
                    'actual_crawled_prs': len(detailed_prs),
                    'output_file': output_path,
                    'repo_owner': repo_owner,
                    'repo_name': repo_name
                }
                
                results.append({
                    'file': filename,
                    'result': result
                })
                
                if result['success']:
                    total_original_prs += result['original_total_prs']
                    total_actual_crawled += result['actual_crawled_prs']
            
            successful_files = [r for r in results if r['result']['success']]
            failed_files = [r for r in results if not r['result']['success']]
            
            return {
                'success': True,
                'message': f'Successfully crawled {len(successful_files)} files, failed {len(failed_files)} files',
                'total_files': len(jsonl_files),
                'successful_files': len(successful_files),
                'failed_files': len(failed_files),
                'total_original_prs': total_original_prs,
                'total_actual_crawled': total_actual_crawled,
                'file_results': results,
                'output_file': output_path
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to crawl PR details: {str(e)}',
                'total_prs': 0,
                'crawled_prs': 0
            }
    
    def _read_prs_from_file(self, filepath: str) -> List[Dict]:
        pr_list = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            pr_data = json.loads(line)
                            pr_list.append(pr_data)
                        except json.JSONDecodeError as e:
                            print(f"Failed to parse JSON line: {e}, line content: {line}")
                            continue
        except FileNotFoundError:
            print(f"File does not exist: {filepath}")
            raise
        except Exception as e:
            print(f"Failed to read file {filepath}: {e}")
            raise
        
        return pr_list
    
    def _crawl_pr_details_multithreaded(self, pr_list: List[Dict], repo: GitHubRepo,
        max_workers: int = 4,progress_callback: Callable[[int, int], None] = None) -> List[Dict]:
        
        detailed_prs = []
        total_prs = len(pr_list)
        
        def process_pr(pr: Dict) -> Optional[Dict]:
            try:
                pr_number = pr.get('number')
                if not pr_number:
                    print(f"PR missing number field: {pr}")
                    return None

                pr_details = repo.get_pull_details(pr_number)

                pr_commits = repo.get_pull_commits(pr_number)
                detailed_commits = []
                for commit in pr_commits:
                    commit_sha = commit.get('sha')
                    if commit_sha:
                        commit_details = repo.get_commit_details(commit_sha)
                        if commit_details:
                            detailed_commits.append(commit_details)
                        else:
                            detailed_commits.append(commit)
                    else:
                        detailed_commits.append(commit)

                pr_files = repo.get_pull_files(pr_number)
                detailed_files = []
                for file_info in pr_files:
                    file_details = {
                        'filename': file_info.get('filename', ''),
                        'status': file_info.get('status', ''),
                        'additions': file_info.get('additions', 0),
                        'deletions': file_info.get('deletions', 0),
                        'changes': file_info.get('changes', 0),
                        'patch': file_info.get('patch', ''),
                        'blob_url': file_info.get('blob_url', ''),
                        'raw_url': file_info.get('raw_url', ''),
                        'contents_url': file_info.get('contents_url', '')
                    }
                    detailed_files.append(file_details)
                
                pr_details['commits_list'] = detailed_commits
                pr_details['files_list'] = detailed_files
                
                if pr_details:
                    merged_pr = {**pr, **pr_details}
                    return merged_pr
                else:
                    print(f"Failed to get PR #{pr_number} details")
                    return None
                    
            except Exception as e:
                print(f"Failed to process PR #{pr.get('number', 'unknown')}: {e}")
                return None
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_pr = {executor.submit(process_pr, pr): pr for pr in pr_list}

            completed_count = 0
            for future in as_completed(future_to_pr):
                try:
                    result = future.result()
                    if result:
                        detailed_prs.append(result)
                    
                    completed_count += 1

                    if progress_callback:
                        progress_callback(completed_count, total_prs)
                        
                except Exception as e:
                    print(f"Failed to process PR task: {e}")
                    completed_count += 1
        
        return detailed_prs
    
    def _save_detailed_prs(self, detailed_prs: List[Dict], 
                          basename: str, file_name: str) -> str:

        output_path = os.path.join(self.output_dir, basename)
        os.makedirs(output_path, exist_ok=True)

        filepath = os.path.join(output_path, file_name)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for pr in detailed_prs:
                    try:
                        json_line = json.dumps(obj2dict(pr), ensure_ascii=False, default=str)
                        f.write(json_line + '\n')
                    except Exception as e:
                        print(f"Failed to serialize PR details: {e}")
                        continue
            
            return filepath, output_path
            
        except Exception as e:
            print(f"Failed to save PR detail file {filepath}: {e}")
            raise

    def _parse_repo(self, filepath: str):
        basename = os.path.basename(filepath)
        repo_owner = basename.split('_')[0]
        repo_name = basename.split('_')[1]
        return basename, repo_owner, repo_name
