import logging
import json
import os
import time
import threading
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest import result
from fastcore.xtras import obj2dict
from ..utils.github_api import GitHubRepo, TokenPool, parse_repo_url

logger = logging.getLogger(__name__)

class PRCrawler:
    """PR Crawler"""
    
    def __init__(self, input_file: str = None, output_dir: str = "results/pr_list"):

        self.input_file = input_file
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    # Crawl pr_list data
    def crawl(self, repo_url: str, github_token: str, thread_count: int, 
                progress_callback: Callable[[int, int], None] = None) -> Dict:

        try:
            owner, repo_name = parse_repo_url(repo_url)

            tokens = [token.strip() for token in github_token.split(',') if token.strip()]
            if not tokens:
                tokens = [github_token] if github_token else []
            
            token_pool = TokenPool(tokens)

            repo = GitHubRepo(owner, repo_name, token_pool)
            repo.validate_repository()

            all_prs = repo.get_all_pulls_multithreaded(
                max_workers=thread_count,
                progress_callback=progress_callback
            )
            
            if not all_prs:
                return {
                    'success': True,
                    'message': 'No PRs found',
                    'total_prs': 0,
                    'human_prs': 0,
                    'agent_prs': 0,
                    'output_file': None
                }

            output_file = self._save_results(owner, repo_name, all_prs)
            
            return {
                'success': True,
                'message': f'Successfully crawled {len(all_prs)} PRs)',
                'total_prs': len(all_prs),
                'output_file': output_file
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error during crawling: {str(e)}',
                'total_prs': 0,
                'human_prs': 0,
                'agent_prs': 0,
                'errors': [str(e)]
            }

    # Save results to file
    def _save_results(self, owner: str, repo_name: str, results: List[Dict]) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        filename = f"{owner}_{repo_name}_{timestamp}.jsonl"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for i, pr_data in enumerate(results):
                    try:
                        json_line = json.dumps(obj2dict(pr_data), ensure_ascii=False, default=str)
                        f.write(json_line + '\n')
                    except Exception as e:
                        print(f"Failed to serialize PR #{i}: {e}")

            return filepath
            
        except Exception as e:
            error_msg = f"Error saving file: {e}"
            
            with self.progress_lock:
                self.progress['errors'].append(error_msg)
            
            return None