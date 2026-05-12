import json
import os
from datetime import datetime
from typing import Dict, List, Tuple
from fastcore.xtras import obj2dict

# Agent identification rules - Based on head branch name, author field, and PR body
AGENT_RULES = {
    'copilot': {
        'head_patterns': ['copilot/'],
        'author_patterns': ['copilot'],
        'body_patterns': []
    },
    'codex': {
        'head_patterns': ['codex/'],
        'author_patterns': [],
        'body_patterns': []
    },
    'cursor': {
        'head_patterns': ['cursor/'],
        'author_patterns': [],
        'body_patterns': []
    },
    'devin': {
        'head_patterns': [],
        'author_patterns': ['devin-ai-integration[bot]'],
        'body_patterns': []
    },
    'codegen': {
        'head_patterns': [],
        'author_patterns': ['codegen-sh[bot]'],
        'body_patterns': []
    },
    'jules': {
        'head_patterns': [],
        'author_patterns': ['google-labs-jules[bot]'],
        'body_patterns': []
    },
    'claude': {
        'head_patterns': [],
        'author_patterns': [],
        'body_patterns': ['Co-Authored-By:Claude']
    }
}

class PRClassifier:
    """PR Classifier"""
    
    def __init__(self, output_dir: str = "results/pr_list_filtered"):
        self.output_dir = output_dir
    
    def classify_prs(self, pr_file_path: str, start_date: str = None, end_date: str = None, progress_callback=None) -> Dict[str, any]:
        pr_list = self._read_prs_from_file(pr_file_path)
        agent_prs = {}
        human_prs = []
        
        # Initialize PR lists for each agent
        for agent_name in AGENT_RULES.keys():
            agent_prs[agent_name] = []
        
        # Statistics
        stats = {
            'total': len(pr_list),
            'human': 0,
            'agent': 0
        }
        
        # Time filtering
        filtered_time = 0
        if start_date or end_date:
            filtered_prs = []
            for pr in pr_list:
                if self._is_in_date_range(pr, start_date, end_date):
                    filtered_prs.append(pr)
                else:
                    filtered_time += 1
            pr_list = filtered_prs
        
        total_prs = len(pr_list)
        filtered_merged = 0
        processed_count = 0
        
        for pr in pr_list:
            if not self._is_merged(pr):
                filtered_merged += 1
                processed_count += 1
                if progress_callback and processed_count % 10 == 0:
                    progress_callback(processed_count, total_prs, {
                        'filtered_time': filtered_time,
                        'filtered_merged': filtered_merged,
                        'remaining': total_prs - processed_count
                    })
                continue

            agent_type = self._identify_agent_type(pr)
            
            if agent_type:
                pr['agent'] = agent_type
                agent_prs[agent_type].append(pr)
            else:
                # Mark as human PR
                pr['agent'] = 'human'
                human_prs.append(pr)
            
            processed_count += 1
            # Update progress every 10 PRs
            if progress_callback and processed_count % 10 == 0:
                progress_callback(processed_count, total_prs, {
                    'filtered_time': filtered_time,
                    'filtered_merged': filtered_merged,
                    'remaining': total_prs - processed_count,
                    'human_count': len(human_prs),
                    'agent_count': sum(len(prs) for prs in agent_prs.values())
                })
        
        # Count agent types
        agent_counts = {}
        for agent_name, prs in agent_prs.items():
            agent_counts[agent_name] = len(prs)
        agent_counts['human'] = len(human_prs)
        
        total_agent_prs = sum(len(prs) for prs in agent_prs.values())
        total_all_prs = len(human_prs) + total_agent_prs
        
        save_result = self.save_classification_results(
            human_prs, 
            agent_prs, 
            pr_file_path
        )
        output_dir = save_result['output_path']
        
        return {
            'success': True,
            'message': f'Successfully classified {total_all_prs} PRs (Human: {len(human_prs)}, Agent: {total_agent_prs})',
            'total_prs': total_all_prs,
            'human_prs': len(human_prs),
            'agent_prs': total_agent_prs,
            'agent_breakdown': agent_counts,
            'output_path': output_dir,
            'statistics': {
                'total_input_prs': total_prs,
                'filtered_time_prs': filtered_time,
                'filtered_merged': filtered_merged,
                'remaining_prs': total_all_prs
            }
        }
    
    def _identify_agent_type(self, pr: Dict) -> str:
        """Identify agent type of PR"""
        
        # Check head branch name
        head_ref = pr.get('head', {}).get('ref', '').lower()
        if head_ref:
            for agent_name, rules in AGENT_RULES.items():
                for pattern in rules['head_patterns']:
                    if pattern.lower() in head_ref:
                        return agent_name
        
        # Check author info
        author_login = pr.get('user', {}).get('login', '').lower()
        if author_login:
            for agent_name, rules in AGENT_RULES.items():
                for pattern in rules['author_patterns']:
                    if pattern.lower() in author_login:
                        return agent_name
        
        # Check PR body
        body = pr.get('body', '')
        if body and isinstance(body, str):
            body_lower = body.lower()
            for agent_name, rules in AGENT_RULES.items():
                for pattern in rules['body_patterns']:
                    if pattern.lower() in body_lower:
                        return agent_name
        
        return ''
    
    def _is_merged(self, pr: Dict) -> bool:
        merged_at = pr.get('merged_at')
        if merged_at is None or merged_at == {} or merged_at == '':
            return False
        return True
    
    def _is_in_date_range(self, pr: Dict, start_date: str, end_date: str) -> bool:
        created_at = pr.get('created_at', '')
        if not created_at:
            return False
        
        try:
            pr_date = created_at.split('T')[0]
            if start_date and pr_date < start_date:
                return False
            if end_date and pr_date > end_date:
                return False
            return True
        except Exception:
            return False
    
    def save_classification_results(self, human_prs: List[Dict], agent_prs: Dict[str, List[Dict]], 
                                  input_file_path: str = None) -> Dict[str, any]:
        """Save classification results to file"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_files = {}
        
        # Count agent types
        agent_counts = {}
        
        base = os.path.splitext(os.path.basename(input_file_path))[0]
        
        output_path = os.path.join(self.output_dir, base)
        os.makedirs(output_path, exist_ok=True)

        # Save PRs for each agent
        for agent_name, prs in agent_prs.items():
            if prs:
                filename = f"{agent_name}.jsonl"
                filepath = os.path.join(output_path, filename)
                
                self._save_prs_to_file(prs, filepath)
                output_files[f'{agent_name}_prs'] = filepath
                agent_counts[agent_name] = len(prs)
        
        # Save human PRs
        if human_prs:
            filename = f"human.jsonl"
            filepath = os.path.join(output_path, filename)
            
            self._save_prs_to_file(human_prs, filepath)
            output_files['human_prs'] = filepath
            agent_counts['human'] = len(human_prs)
        
        return {
            'output_path': output_path,
            'agent_counts': agent_counts,
            'total_human_prs': len(human_prs),
            'total_agent_prs': sum(len(prs) for prs in agent_prs.values()),
            'total_all_prs': len(human_prs) + sum(len(prs) for prs in agent_prs.values())
        }
    
    def _save_prs_to_file(self, prs: List[Dict], filepath: str):
        """Save PR list to file"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for pr in prs:
                    try:
                        json_line = json.dumps(obj2dict(pr), ensure_ascii=False, default=str)
                        f.write(json_line + '\n')
                    except Exception as e:
                        print(f"Failed to serialize PR: {e}")
                        continue
        except Exception as e:
            print(f"Failed to save file {filepath}: {e}")
            raise
    
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
