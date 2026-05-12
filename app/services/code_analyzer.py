import logging
import json
import os
import re
from typing import Dict, List, Optional, Callable, Set, Tuple, Generator
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from app.utils.code_utils import LANGUAGE_NAME_MAP, parse_diff_lines, extract_changed_functions
from app.utils.code_utils import get_code_line_count_without_comments

class CodeAnalyzer:
    """Code Analyzer - Extract changed function information from PR details"""
    def __init__(self, output_dir: str = "results/extracted_functions"):
        self.output_dir = output_dir
        
        os.makedirs(output_dir, exist_ok=True)
    
    def construct_datasets(self, pr_details_path: str, code_files_path: str, 
        thread_count: int, progress_callback: Callable[[int, int], None] = None) -> Dict[str, any]:
        try:
            basename = os.path.basename(pr_details_path) # Repository name
            self.output_dir = os.path.join(self.output_dir, basename)
            os.makedirs(self.output_dir, exist_ok=True)

            files = []
            for filename in os.listdir(pr_details_path):
                if filename.endswith(".jsonl"):
                    files.append(os.path.join(pr_details_path, filename))
            if not files:
                return {
                    'success': False,
                    'message': f'No .jsonl files found in directory: {pr_details_path}',
                    'total_functions': 0
                }

            # Initialize global ID counter
            global_ids = {
                'commit_idx': 1,
                'diff_idx': 1,
                'file_idx': 1,
                'function_idx': 1
            }

            # Initialize statistics
            stats = {
                'total_prs': 0,
                'total_commits': 0,
                'total_diffs': 0,
                'total_files': 0,
                'total_functions': 0,
                'output_files': {},
                'file_types': {},
                'agent_stats': {}
            }

            # Initialize output files
            pr_file = os.path.join(self.output_dir, "pr.jsonl")
            commit_file = os.path.join(self.output_dir, "commit.jsonl")
            diff_file = os.path.join(self.output_dir, "diff.jsonl")
            file_file = os.path.join(self.output_dir, "file.jsonl")
            function_file = os.path.join(self.output_dir, "function.jsonl")

            # Clear files
            for file_path in [pr_file, commit_file, diff_file, file_file, function_file]:
                with open(file_path, "w", encoding="utf-8") as f:
                    pass

            results = []
            total_files_count = len(files)
            processed_files_count = 0

            for filepath in files:
                filename = os.path.basename(filepath)
                file_type = filename.split('.')[0]

                pr_list = self._read_prs_from_file(filepath)
                if not pr_list:
                    results.append({
                        'file': filename,
                        'result': {
                            'success': False,
                            'message': 'No PRs found in file'
                        }
                    })
                    continue

                # Start organizing data
                file_stats = self._organize_prs(pr_list, os.path.join(code_files_path, file_type), 
                                              pr_file, commit_file, diff_file, file_file, function_file,
                                              global_ids, file_type)
                
                # Update overall statistics
                stats['total_prs'] += file_stats['prs']
                stats['total_commits'] += file_stats['commits']
                stats['total_diffs'] += file_stats['diffs']
                stats['total_files'] += file_stats['files']
                stats['total_functions'] += file_stats['functions']
                stats['file_types'][file_type] = file_stats
                stats['agent_stats'][file_type] = file_stats['functions']
                
                results.append({
                    'file_type': file_type,
                    'stats': file_stats
                })
                
                # Update progress
                processed_files_count += 1
                if progress_callback:
                    progress_callback(processed_files_count, total_files_count, stats['total_functions'])
            
            # Count agent statistics from function.jsonl
            agent_stats = {}
            with open(function_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            func_data = json.loads(line)
                            agent = func_data.get('agent', 'unknown')
                            if agent not in agent_stats:
                                agent_stats[agent] = 0
                            agent_stats[agent] += 1
                        except json.JSONDecodeError:
                            continue
            
            stats['agent_stats'] = agent_stats
            
            # Set output file paths
            stats['output_files'] = {
                'pr_file': pr_file,
                'commit_file': commit_file,
                'diff_file': diff_file,
                'file_file': file_file,
                'function_file': function_file
            }
            
            return {
                'success': True,
                'message': f'Successfully constructed dataset with {stats["total_functions"]} functions',
                'stats': stats,
                'results': results,
                'output_dir': self.output_dir
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to construct dataset: {str(e)}',
                'stats': {},
                'results': [],
                'output_dir': ''
            }
        
    def _organize_prs(self, pr_list: List[Dict], code_files_path: str,
                      pr_file: str, commit_file: str, diff_file: str, file_file: str, function_file: str,
                      global_ids: Dict[str, int], file_type: str) -> Dict:
        """Organize PR data and return statistics"""
        
        # Initialize statistics
        stats = {
            'prs': 0,
            'commits': 0,
            'diffs': 0,
            'files': 0,
            'functions': 0
        }
        
        # Use global IDs
        commit_idx = global_ids['commit_idx']
        diff_idx = global_ids['diff_idx']
        file_idx = global_ids['file_idx']
        function_idx = global_ids['function_idx']

        for pr in pr_list:
            pr_id = pr.get('id', 0)
            number = pr.get('number', 0)
            commits = pr.get('commits_list', [])
            
            pr.pop('commits_list')
        
            code_files_path_pr = os.path.join(code_files_path, str(number))
            
            # Process commits
            commit_stats = self._organize_commit(commits, pr_id, commit_file, diff_file, 
                file_file, function_file, commit_idx, diff_idx, file_idx, function_idx, code_files_path_pr, file_type)
            
            # Update statistics
            stats['prs'] += 1
            stats['commits'] += commit_stats['commits_processed']
            stats['diffs'] += commit_stats['diffs_processed']
            stats['files'] += commit_stats['files_processed']
            stats['functions'] += commit_stats['functions_processed']
            
            # Update global IDs
            global_ids['commit_idx'] = commit_stats['commit_idx']
            global_ids['diff_idx'] = commit_stats['diff_idx']
            global_ids['file_idx'] = commit_stats['file_idx']
            global_ids['function_idx'] = commit_stats['function_idx']

            # Write PR data
            with open(pr_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(pr, ensure_ascii=False) + "\n")
        
        return stats

                
    def _organize_commit(self, commits: List[Dict], pr_idx, commit_file, diff_file, 
        file_file, function_file, commit_idx: int, diff_idx: int, file_idx: int, 
        function_idx: int, code_files_path: str, file_type: str) -> Dict[str, any]:

        commit_datas = []
        stats = {
            'commits_processed': 0,
            'diffs_processed': 0,
            'files_processed': 0,
            'functions_processed': 0
        }

        for commit in commits:
            
            files = commit.get('files', [])
            commit.pop('files')
            commit['agent'] = file_type
            commit_datas.append(commit)

            code_files_path_commit = os.path.join(code_files_path, commit['sha'])

            # Process diffs
            diff_stats = self._organize_diff(files, pr_idx, commit_idx, diff_file, 
                                            file_file, function_file, diff_idx, file_idx,
                                            function_idx, code_files_path_commit, file_type)
            
            # Update statistics
            stats['commits_processed'] += 1
            stats['diffs_processed'] += diff_stats['diffs_processed']
            stats['files_processed'] += diff_stats['files_processed']
            stats['functions_processed'] += diff_stats['functions_processed']
            
            diff_idx = diff_stats['diff_idx']
            file_idx = diff_stats['file_idx']
            function_idx = diff_stats['function_idx']
            commit_idx += 1

        # Write commit data
        with open(commit_file, "a", encoding="utf-8") as f:
            for item in commit_datas:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        return {
            'commit_idx': commit_idx,
            'diff_idx': diff_idx,
            'file_idx': file_idx,
            'function_idx': function_idx,
            'commits_processed': stats['commits_processed'],
            'diffs_processed': stats['diffs_processed'],
            'files_processed': stats['files_processed'],
            'functions_processed': stats['functions_processed']
        }

    def _organize_diff(self, files: List[Dict], pr_idx, commit_idx, diff_file, 
        file_file, function_file, diff_idx: int, file_idx: int, function_idx: int, 
        code_files_path: str, file_type: str) -> Dict[str, any]:

        diff_datas = []
        stats = {
            'diffs_processed': 0,
            'files_processed': 0,
            'functions_processed': 0
        }
        
        for file in files:
            
            if 'patch' not in file or file['patch'] is None or get_code_line_count_without_comments(file['patch']) <= 0:
                continue
            
            file['agent'] = file_type
            diff_datas.append(file)

            filename = os.path.basename(file["filename"])
            file_path = os.path.join(code_files_path, filename)

            file_stats = self._organize_file(file_path, file["filename"], pr_idx, commit_idx, 
                                            diff_idx, file_idx, function_idx, file_file, function_file, file['patch'], file_type)

            stats['diffs_processed'] += 1
            stats['files_processed'] += file_stats['files_processed']
            stats['functions_processed'] += file_stats['functions_processed']
            
            file_idx = file_stats['file_idx']
            function_idx = file_stats['function_idx']
            diff_idx += 1

        with open(diff_file, "a", encoding="utf-8") as f:
            for item in diff_datas:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
                
        return {
            'diff_idx': diff_idx,
            'file_idx': file_idx,
            'function_idx': function_idx,
            'diffs_processed': stats['diffs_processed'],
            'files_processed': stats['files_processed'],
            'functions_processed': stats['functions_processed']
        }

    def _organize_file(self, file_path, filename, pr_idx, commit_idx, diff_idx, file_idx,
                        function_idx, file_file, function_file, diff_text, file_type: str) -> Dict[str, any]:
        """Organize file data and return statistics"""

        stats = {
            'files_processed': 0,
            'functions_processed': 0
        }

        if not os.path.exists(file_path):
            return {
                'file_idx': file_idx,
                'function_idx': function_idx,
                'files_processed': 0,
                'functions_processed': 0
            }

        try:
            code = open(file_path, "r", encoding="utf8").read()
            ext = os.path.splitext(filename)[1]

            function_stats = self.construct_function(code, pr_idx, commit_idx, diff_idx, file_idx, function_idx, function_file, diff_text, ext, file_type)

            with open(file_file, "a", encoding="utf-8") as f:
                item = {
                    "id": file_idx, 
                    "diff_id": diff_idx, 
                    "filename": filename, 
                    "code": code, 
                    "language": function_stats['language'],
                    "agent": file_type
                }
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
            
            stats['files_processed'] = 1
            stats['functions_processed'] = function_stats['functions_processed']
            file_idx += 1
            function_idx = function_stats['function_idx']
            
        except Exception as e:
            print(f"Failed to process file {file_path}: {e}")

        return {
            'file_idx': file_idx,
            'function_idx': function_idx,
            'files_processed': stats['files_processed'],
            'functions_processed': stats['functions_processed']
        }
    
    def construct_function(self, code, pr_idx, commit_idx, diff_idx, file_idx, function_idx, 
                            function_file, diff_text, ext, file_type: str) -> Dict[str, any]:
        
        stats = {
            'functions_processed': 0,
            'language': ''
        }
        
        try:
            if ext not in LANGUAGE_NAME_MAP.keys():
                return {
                    'function_idx': function_idx,
                    'functions_processed': 0,
                    'language': ''
                }
            
            funcs, language = extract_changed_functions(diff_text, code, ext)
            stats['language'] = language
            
            if len(funcs) == 0:
                return {
                    'function_idx': function_idx,
                    'functions_processed': 0,
                    'language': language
                }

            with open(function_file, "a", encoding="utf-8") as f:
                for func in funcs:
                    item = {
                        "id": function_idx, 
                        "pr_id": pr_idx, 
                        "commit_id": commit_idx, 
                        "diff_id": diff_idx, 
                        "ext": ext, 
                        "language": language, 
                        "file_id": file_idx, 
                        "code": func.get("code", ""),
                        "start_line": func.get("start_line", 0), 
                        "end_line": func.get("end_line", 0),
                        "agent": file_type
                    }
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    function_idx += 1
                    stats['functions_processed'] += 1
            
        except Exception as e:
            print(f"Function extraction failed: {e}")
        
        return {
            'function_idx': function_idx,
            'functions_processed': stats['functions_processed'],
            'language': stats['language']
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
        except Exception as e:
            print(f"Failed to read file {filepath}: {e}")
            raise
        
        return pr_list
    