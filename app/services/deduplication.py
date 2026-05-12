import json
import os
import hashlib
import shutil
from typing import Dict, List, Optional, Callable

class Deduplication:
    
    def __init__(self, output_dir: str = "results/datasets"):
        self.output_dir = output_dir
        
    def deduplicate_functions(self, input_path: str) -> Dict[str, any]:

        try:
            if not os.path.exists(input_path):
                return {
                    'success': False,
                    'message': f'Input path does not exist: {input_path}',
                    'stats': {}
                }
            
            basename = os.path.basename(input_path)
            output_path = os.path.join(self.output_dir, basename)
            os.makedirs(output_path, exist_ok=True)

            input_files = {
                'pr': os.path.join(input_path, 'pr.jsonl'),
                'commit': os.path.join(input_path, 'commit.jsonl'),
                'diff': os.path.join(input_path, 'diff.jsonl'),
                'file': os.path.join(input_path, 'file.jsonl'),
                'function': os.path.join(input_path, 'function.jsonl')
            }
            
            output_files = {
                'pr': os.path.join(output_path, 'pr.jsonl'),
                'commit': os.path.join(output_path, 'commit.jsonl'),
                'diff': os.path.join(output_path, 'diff.jsonl'),
                'file': os.path.join(output_path, 'file.jsonl'),
                'function': os.path.join(output_path, 'function.jsonl')
            }

            for file_type, file_path in input_files.items():
                if not os.path.exists(file_path):
                    return {
                        'success': False,
                        'message': f'Input file does not exist: {file_path}',
                        'stats': {}
                    }

            self._copy_files(input_files, output_files, ['pr', 'commit', 'diff', 'file'])
            stats = self._deduplicate_function_file(input_files['function'], output_files['function'])

            return {
                'success': True,
                'message': f'Successfully deduplicated {stats["original_count"]} functions to {stats["unique_count"]} unique functions',
                'stats': stats,
                'input_path': input_path,
                'output_path': output_path,
                'output_files': output_files
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to deduplicate functions: {str(e)}',
                'stats': {},
                'input_path': input_path,
                'output_path': '',
                'output_files': {}
            }
    
    def _copy_files(self, input_files: Dict[str, str], output_files: Dict[str, str], file_types: List[str]):
        for file_type in file_types:
            if file_type in input_files and file_type in output_files:
                shutil.copy2(input_files[file_type], output_files[file_type])
    
    def _deduplicate_function_file(self, input_function_file: str, output_function_file: str) -> Dict[str, any]:

        functions = []
        with open(input_function_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        function_data = json.loads(line)
                        functions.append(function_data)
                    except json.JSONDecodeError as e:
                        print(f"Failed to parse JSON line: {e}, line content: {line}")
        
        original_count = len(functions)
        print(f"Read {original_count} functions")
        
        # Count original functions by agent
        agent_stats_original = {}
        for function in functions:
            agent = function.get('agent', 'unknown')
            if agent not in agent_stats_original:
                agent_stats_original[agent] = 0
            agent_stats_original[agent] += 1

        unique_functions = []
        seen_hashes = set()
        
        for function in functions:
            code = function.get('code', '')
            if code:
                function_hash = self._calculate_hash(code)
                
                if function_hash not in seen_hashes:
                    seen_hashes.add(function_hash)
                    function['hash'] = function_hash
                    unique_functions.append(function)
        
        unique_count = len(unique_functions)
        
        # Count deduplicated functions by agent
        agent_stats_unique = {}
        for function in unique_functions:
            agent = function.get('agent', 'unknown')
            if agent not in agent_stats_unique:
                agent_stats_unique[agent] = 0
            agent_stats_unique[agent] += 1

        with open(output_function_file, 'w', encoding='utf-8') as f:
            for function in unique_functions:
                f.write(json.dumps(function, ensure_ascii=False) + '\n')
        
        # Calculate deduplication rate by agent
        agent_dedup_rates = {}
        for agent in agent_stats_original:
            original = agent_stats_original.get(agent, 0)
            unique = agent_stats_unique.get(agent, 0)
            if original > 0:
                agent_dedup_rates[agent] = ((original - unique) / original * 100)
            else:
                agent_dedup_rates[agent] = 0

        return {
            'original_count': original_count,
            'unique_count': unique_count,
            'duplicate_count': original_count - unique_count,
            'deduplication_rate': ((original_count - unique_count) / original_count * 100) if original_count > 0 else 0,
            'agent_stats': {
                'original': agent_stats_original,
                'unique': agent_stats_unique,
                'duplicate': {agent: agent_stats_original.get(agent, 0) - agent_stats_unique.get(agent, 0) 
                            for agent in set(agent_stats_original.keys()) | set(agent_stats_unique.keys())},
                'deduplication_rate': agent_dedup_rates
            }
        }
    
    def _calculate_hash(self, code: str) -> str:

        normalized_code = self._normalize_code(code)

        hash_object = hashlib.sha256(normalized_code.encode('utf-8'))
        return hash_object.hexdigest()
    
    def _normalize_code(self, code: str) -> str:

        lines = [line.strip() for line in code.split('\n')]
        lines = [line for line in lines if line]
        lines = [line for line in lines if not line.startswith('#') and not line.startswith('//')]
        normalized = '\n'.join(lines)
        normalized = ' '.join(normalized.split())
        
        return normalized