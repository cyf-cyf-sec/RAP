import time
import concurrent.futures
import random
from typing import Dict, List, Optional, Tuple, Generator
from ghapi.core import GhApi
from requests.exceptions import HTTPError

class TokenPool:
    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.token_count = len(tokens)

    def get_token_for_process(self, process_id: int = None) -> str:
        if self.token_count == 0:
            return ''
        if process_id is None:
            process_id = random.randint(0, 1000)

        token_index = process_id % self.token_count
        return self.tokens[token_index]

    def get_all_tokens(self) -> List[str]:
        """Get all tokens"""
        return self.tokens.copy()

class GitHubRepo:

    def __init__(self, owner: str, name: str, token_pool: TokenPool, process_id: int = None):
        self.owner = owner
        self.name = name
        self.token_pool = token_pool
        self.process_id = process_id or random.randint(0, 1000)
        
        self.current_token = self.token_pool.get_token_for_process(self.process_id)
        self.api = GhApi(token=self.current_token)
        if hasattr(self.api, 'session'):
            self.api.session.timeout = 30
        
        self.repo = self.call_api(self.api.repos.get, owner=owner, repo=name)
        print(f"[{owner}/{name}] Using token: {self.current_token[:8]}...")
    
    def _is_retryable_error(self, error_msg: str) -> bool:
        """Check if error is retryable"""
        retryable_patterns = [
            "SSL",
            "TLS", 
            "EOF",
            "_ssl.c",
            "urlopen error",
            "connection",
            "timeout",
            "temporarily unavailable",
            "IncompleteRead",
            "bytes read",
            "more expected",
            "ConnectionResetError",
            "BrokenPipeError",
            "ConnectionError",
            "ReadTimeout",
            "ConnectTimeout"
        ]
        
        # Check for network-related retryable errors
        if any(pattern in error_msg for pattern in retryable_patterns):
            return True
        
        # Check for HTTP errors, excluding auth and resource-not-found errors
        if "HTTP" in error_msg:
            # Retryable HTTP errors: server errors (5xx), rate limiting (429)
            if any(code in error_msg for code in ["429", "500", "502", "503", "504"]):
                return True
            # Non-retryable HTTP errors: auth failure (401), permission denied (403), not found (404)
            if any(code in error_msg for code in ["401", "403", "404"]):
                return False
        
        return False

    def switch_token(self):
        current_index = self.token_pool.tokens.index(self.current_token)
        next_index = (current_index + 1) % self.token_pool.token_count
        self.current_token = self.token_pool.tokens[next_index]
        self.api = GhApi(token=self.current_token)
        if hasattr(self.api, 'session'):
            self.api.session.timeout = 30
        print(f"[{self.owner}/{self.name}] Switched to token: {self.current_token[:8]}...")

    def call_api(self, func: callable, **kwargs) -> Dict:
        max_retries = max(self.token_pool.token_count, 1)
        max_total_attempts = max_retries * 3
        
        for total_attempt in range(max_total_attempts):
            for attempt in range(max_retries):
                try:
                    values = func(**kwargs)
                    return values

                except HTTPError as e:
                    if e.response.status_code == 403:
                        print(f"[{self.owner}/{self.name}] Token {self.current_token[:8]}... rate limited, switching...")
                        self.switch_token()
                        time.sleep(1)
                        continue
                    elif e.response.status_code == 404:
                        print(f"[{self.owner}/{self.name}] Resource not found {kwargs}")
                        return None
                    else:
                        print(f"[{self.owner}/{self.name}] HTTP error {e.response.status_code}: {e}")
                        return None

                except Exception as e:
                    print(f"[{self.owner}/{self.name}] fetch error: {e}")
                    error_msg = str(e)

                    if "TLS/SSL" in error_msg or "SSL" in error_msg or "EOF" in error_msg or "_ssl.c" in error_msg or "urlopen error" in error_msg:
                        print(f"[{self.owner}/{self.name}] SSL connection error, retrying in 10 seconds...")
                        time.sleep(10)
                        continue
                    else:
                        print(f"[{self.owner}/{self.name}] API error: {e}")
                        return None
            
            try:
                rl = self.api.rate_limit.get()
                remaining = rl.resources.core.remaining
                print(f"[{self.owner}/{self.name}] All Tokens' rate limit exceeded, waiting for 1 minute, remaining: {remaining}")
                if remaining > 0:
                    break
            except Exception as e:
                print(f"[{self.owner}/{self.name}] Failed to check rate limit: {e}")
                break
            time.sleep(60)
        
        raise RuntimeError(f"[{self.owner}/{self.name}] API call failed after {max_total_attempts} total attempts")

    def get_all_loop(self, func: callable, per_page: int = 100, num_pages: Optional[int] = None, quiet: bool = False, **kwargs) -> Generator:
        page = 1
        args = {
            "owner": self.owner,
            "repo": self.name,
            "per_page": per_page,
            **kwargs,
        }
        
        while True:
            try:
                values = func(**args, page=page)
                for value in values:
                    yield value
                
                if len(values) == 0:
                    break
                    
                if not quiet:
                    rl = self.api.rate_limit.get()
                    print(f"[{self.owner}/{self.name}] Processed page {page} ({per_page} values per page). Remaining calls: {rl.resources.core.remaining}")
                
                if num_pages is not None and page >= num_pages:
                    break
                    
                page += 1
                
            except Exception as e:
                print(f"Error processing page {page}: {e}")
                for _ in range(3):
                    try:
                        rl = self.api.rate_limit.get()
                        if rl.resources.core.remaining > 0:
                            break
                    except Exception:
                        pass
                    print(f"[{self.owner}/{self.name}] Waiting for rate limit reset, checking again in 1 minute")
                    time.sleep(60)
                else:
                    raise RuntimeError(f"[{self.owner}/{self.name}] Rate limit wait exhausted")
        
        if not quiet:
            print(f"[{self.owner}/{self.name}] Processed {(page - 1) * per_page + len(values)} values")

    def _make_request_with_retry(self, func: callable, **kwargs):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return func(**kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Request failed, retry {attempt + 1}/{max_retries}: {e}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    print(f"Request failed, max retries reached: {e}")
                    raise

    def validate_repository(self) -> bool:
        try:
            repo_info = self._make_request_with_retry(
                self.api.repos.get,
                owner=self.owner,
                repo=self.name
            )
            
            if repo_info and hasattr(repo_info, 'name'):
                print(f"Repository validation successful: {self.owner}/{self.name}")
                return True
            else:
                print(f"Repository info retrieval abnormal: {self.owner}/{self.name}")
                return False
                
        except HTTP404NotFoundError:
            print(f"Repository not found: {self.owner}/{self.name}")
            raise ValueError(f"Repository {self.owner}/{self.name} does not exist")
        except HTTP403ForbiddenError:
            print(f"Insufficient access permissions: {self.owner}/{self.name}")
            raise ValueError(f"Insufficient permissions to access repository {self.owner}/{self.name}, please check token or repository permissions")
        except Exception as e:
            print(f"Repository validation failed: {e}")
            raise ValueError(f"Repository validation failed: {str(e)}")

    def get_all_pulls_multithreaded(self, max_workers: int = 8, state="closed", progress_callback=None, **kwargs):
        page = 1
        has_more = True
        futures = {}
        all_prs = []
        failed_pages = {}
        max_retries = 5

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            max_pages = 100
            consecutive_empty_pages = 0
            
            while has_more and page <= max_pages and consecutive_empty_pages < 3:
                if failed_pages:
                    retry_pages = list(failed_pages.keys())
                    for retry_page in retry_pages:
                        if failed_pages[retry_page] < max_retries:
                            print(f"Retrying page {retry_page} (attempt {failed_pages[retry_page] + 1}/{max_retries})")
                            future = executor.submit(
                                self.api.pulls.list,
                                owner=self.owner,
                                repo=self.name,
                                state=state,
                                per_page=100,
                                page=retry_page,
                                **kwargs
                            )
                            futures[future] = retry_page
                            failed_pages[retry_page] += 1
                        else:
                            print(f"Page {retry_page} reached max retries, skipping")
                            del failed_pages[retry_page]

                if len(futures) < max_workers:
                    future = executor.submit(
                        self.api.pulls.list,
                        owner=self.owner,
                        repo=self.name,
                        state=state,
                        per_page=100,
                        page=page,
                        **kwargs
                    )
                    futures[future] = page
                    page += 1

                if progress_callback:
                    print(f"[DEBUG] Calling progress callback after submitting task: page={page-1}, all_prs_count={len(all_prs)}")
                    progress_callback(page - 1, len(all_prs))

                if len(futures) >= max_workers or (not failed_pages and page > max_pages):
                    done, _ = concurrent.futures.wait(
                        futures.keys(),
                        return_when=concurrent.futures.FIRST_COMPLETED
                    )

                    for future in done:
                        page_num = futures.pop(future)
                        try:
                            prs = future.result()
                            prs = list(prs)
                            print(f"爬取到{len(prs)}个PR，当前页{page_num}")

                            if prs:
                                all_prs.extend(prs)
                                if progress_callback:
                                    print(f"[DEBUG] Calling progress callback after task completion: page_num={page_num}, all_prs_count={len(all_prs)}")
                                    progress_callback(page_num, len(all_prs))
                                if page_num in failed_pages:
                                    print(f"Page {page_num} retry successful")
                                    del failed_pages[page_num]
                            else:
                                consecutive_empty_pages += 1
                                if consecutive_empty_pages >= 3:
                                    has_more = False
                        except Exception as e:
                            error_msg = str(e)
                            print(f"Page {page_num} failed: {error_msg}")

                            if self._is_retryable_error(error_msg):
                                if page_num not in failed_pages:
                                    failed_pages[page_num] = 0
                                print(f"Page {page_num} encountered retryable error, will retry")
                                wait_time = min(2 ** failed_pages[page_num], 30)
                                time.sleep(wait_time)
                            else:
                                print(f"Page {page_num} encountered non-retryable error, skipping")
                                has_more = False

            for future in concurrent.futures.as_completed(futures.keys()):
                try:
                    prs = future.result()
                    if prs:
                        all_prs.extend(prs)
                        if progress_callback:
                            progress_callback(page - 1, len(all_prs))
                except Exception as e:
                    print(f"Remaining task processing failed: {e}")

        return all_prs

    def get_pull_details(self, pr_number: int) -> Dict:
        try:
            pull = self._make_request_with_retry(
                self.api.pulls.get,
                owner=self.owner,
                repo=self.name,
                pull_number=pr_number
            )
            
            return pull
            
        except Exception as e:
            print(f"Failed to get PR #{pr_number} details: {e}")
            return None

    def get_pull_files(self, pr_number: int) -> List[Dict]:

        try:
            files = self._make_request_with_retry(
                self.api.pulls.list_files,
                owner=self.owner,
                repo=self.name,
                pull_number=pr_number
            )
            
            return files
            
        except Exception as e:
            print(f"Failed to get PR #{pr_number} files: {e}")
            return []

    def get_pull_commits(self, pr_number: int) -> List[Dict]:
        try:
            commits = self._make_request_with_retry(
                self.api.pulls.list_commits,
                owner=self.owner,
                repo=self.name,
                pull_number=pr_number
            )
            
            return commits
            
        except Exception as e:
            print(f"Failed to get PR #{pr_number} commits: {e}")
            return []

    def get_commit_details(self, commit_sha: str) -> Optional[Dict]:
        try:
            commit_details = self._make_request_with_retry(
                self.api.repos.get_commit,
                owner=self.owner,
                repo=self.name,
                ref=commit_sha
            )
            
            return commit_details
            
        except Exception as e:
            print(f"Failed to get commit {commit_sha} details: {e}")
            return None

def parse_repo_url(repo_url: str) -> Tuple[str, str]:
    if 'github.com/' in repo_url:
        path = repo_url.split('github.com/')[1]
    else:
        path = repo_url

    path = path.rstrip('/').replace('.git', '')

    parts = path.split('/')
    if len(parts) >= 2:
        return parts[0], parts[1]
    else:
        raise ValueError(f"Invalid repository URL: {repo_url}")