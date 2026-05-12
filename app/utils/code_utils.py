from tree_sitter import Language, Parser
import tree_sitter_javascript
import tree_sitter_typescript
import tree_sitter_python
import tree_sitter_go
import tree_sitter_rust
import tree_sitter_cpp
import tree_sitter_c
import tree_sitter_java
import tree_sitter_c_sharp
import tree_sitter_php
import re


LANGUAGE_NAME_MAP = {
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",

    ".ts": "TypeScript",
    ".tsx": "TypeScript",

    ".py": "Python",
    ".pyw": "Python",
    ".pyi": "Python",

    ".go": "Go",
    ".rs": "Rust",

    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".hxx": "C++",
    ".hh": "C++",

    ".c": "C",
    ".h": "C",

    ".php": "PHP",
    ".phtml": "PHP",

    ".java": "Java",

    ".cs": "C#",
}

LANGUAGE_MAP = {
    ".js": tree_sitter_javascript.language(),
    ".jsx": tree_sitter_javascript.language(),
    ".mjs": tree_sitter_javascript.language(),
    ".cjs": tree_sitter_javascript.language(),

    ".ts": tree_sitter_typescript.language_typescript(),
    ".tsx": tree_sitter_typescript.language_tsx(),

    ".py": tree_sitter_python.language(),
    ".pyw": tree_sitter_python.language(),
    ".pyi": tree_sitter_python.language(),

    ".go": tree_sitter_go.language(),
    ".rs": tree_sitter_rust.language(),

    ".cpp": tree_sitter_cpp.language(),
    ".cc": tree_sitter_cpp.language(),
    ".cxx": tree_sitter_cpp.language(),
    ".hpp": tree_sitter_cpp.language(),
    ".hxx": tree_sitter_cpp.language(),
    ".hh": tree_sitter_cpp.language(),

    ".c": tree_sitter_c.language(),
    ".h": tree_sitter_c.language(),

    ".php": tree_sitter_php.language_php(),
    ".phtml": tree_sitter_php.language_php(),

    ".java": tree_sitter_java.language(),

    ".cs": tree_sitter_c_sharp.language(),
}

FUNCTION_NODE_TYPES = {
    "function_declaration",
    "method_definition",
    "function_definition",
    "arrow_function",
    "generator_function",
    "class_method",
    "method_declaration",
}

def get_code_line_count_without_comments(code: str) -> int:
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    code = re.sub(r'"""(.*?)"""', "", code, flags=re.S)
    code = re.sub(r"'''(.*?)'''", "", code, flags=re.S)

    count = 0
    for line in code.split("\n"):
        line = re.sub(r"//.*", "", line)
        line = re.sub(r"#.*", "", line)
        if line.strip():
            count += 1
    return count

def calculate_max_depth(node):
    """Calculate the maximum depth of the AST tree"""
    if not node.children:
        return 1

    max_child_depth = 0
    for child in node.children:
        child_depth = calculate_max_depth(child)
        if child_depth > max_child_depth:
            max_child_depth = child_depth

    return max_child_depth + 1

def calculate_alnum_ratio(code: str) -> float:
    """Calculate alphanumeric character ratio (ignoring whitespace, newlines, etc.)"""
    if not code:
        return 0.0

    # Remove whitespace (spaces, tabs, newlines)
    code_no_space = re.sub(r"\s+", "", code)
    if not code_no_space:
        return 0.0

    alnum_count = sum(ch.isalnum() for ch in code_no_space)
    return alnum_count / len(code_no_space)

def filter_file_code(root, code):
    """Filter code files based on AST depth and character ratio"""

    # Calculate AST depth
    max_depth = calculate_max_depth(root)

    # Calculate alphanumeric character ratio
    alnum_ratio = calculate_alnum_ratio(code)

    # Apply filter conditions
    if not (2 <= max_depth <= 31):
        print(f'Insufficient depth: {max_depth}')
        return False
    # if not (0.2 <= alnum_ratio <= 0.80):
    #     print(f'Insufficient character ratio: {alnum_ratio}')
    #     return False

    return True

def parse_diff_lines(diff_text):
    """
    Parse diff text and extract changed line ranges
    Returns: list of changed line ranges [(start_line, end_line), ...]
    """
    lines = diff_text.split('\n')
    
    # Line number mapping: records the correspondence between old and new file line numbers
    old_to_new_mapping = {}
    
    # Current chunk info
    current_old_start = 0
    current_new_start = 0
    current_old_line = 0
    current_new_line = 0
    
    # Changed lines set (new file line numbers)
    changed_lines = set()
    
    # Record deleted lines (old file line numbers)
    deleted_lines_old = []
    
    for line in lines:
        if line.startswith('@@'):
            # Parse diff header, e.g. @@ -1,5 +1,6 @@
            match = re.search(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@', line)
            if match:
                current_old_start = int(match.group(1))
                old_length = int(match.group(2))
                current_new_start = int(match.group(3))
                new_length = int(match.group(4))
                
                # Reset line counters
                current_old_line = current_old_start - 1
                current_new_line = current_new_start - 1
                
        elif line.startswith('+'):
            # Added line (only in new file)
            current_new_line += 1
            
            # Check if it's a comment change
            stripped_line = line[1:].strip()
            if stripped_line and not stripped_line.startswith(('//', '/*', '*', '#', '--')):
                # Not a comment, add to changed lines
                changed_lines.add(current_new_line)
                
            # Added lines have no corresponding line in old file
            
        elif line.startswith('-'):
            # Deleted line (only in old file)
            current_old_line += 1
            
            # Record deleted line
            deleted_lines_old.append(current_old_line)
            
            # Check if it's a comment change
            stripped_line = line[1:].strip()
            if stripped_line and not stripped_line.startswith(('//', '/*', '*', '#', '--')):
                # Not a comment, need to map to new file
                # The position of a deleted line in the new file is before its unchanged lines
                if current_new_line >= current_new_start:
                    # Map deleted line to corresponding position in new file
                    changed_lines.add(current_new_line)
            
        elif line.startswith(' '):
            # Unchanged line (exists in both old and new files)
            current_old_line += 1
            current_new_line += 1
            
            # Record line number mapping
            old_to_new_mapping[current_old_line] = current_new_line
            
        else:
            # Other lines (e.g., diff headers, etc.)
            pass
    
    # Handle completely deleted functions: detect consecutive deleted line blocks
    # If a function is completely deleted, it will appear as consecutive deleted line blocks in the diff
    if deleted_lines_old:
        deleted_lines_old.sort()
        
        # Detect consecutive deleted line blocks
        deletion_blocks = []
        block_start = deleted_lines_old[0]
        block_end = deleted_lines_old[0]
        
        for i in range(1, len(deleted_lines_old)):
            if deleted_lines_old[i] == block_end + 1:
                block_end = deleted_lines_old[i]
            else:
                deletion_blocks.append((block_start, block_end))
                block_start = deleted_lines_old[i]
                block_end = deleted_lines_old[i]
        
        deletion_blocks.append((block_start, block_end))
        
        # For each deletion block, try to map to new file
        for block_start, block_end in deletion_blocks:
            # If this deletion block has no corresponding new file line number in the mapping
            # it means this is a completely deleted code block
            has_mapping = False
            for old_line in range(block_start, block_end + 1):
                if old_line in old_to_new_mapping:
                    has_mapping = True
                    break
            
            if not has_mapping:
                # This is a completely deleted block, needs special handling
                # Since we cannot associate it with a specific function in the new file, skip for now
                pass
    
    # Sort changed lines and merge into continuous ranges
    if changed_lines:
        changed_lines_list = sorted(changed_lines)
        ranges = []
        start = changed_lines_list[0]
        end = changed_lines_list[0]
        
        for i in range(1, len(changed_lines_list)):
            if changed_lines_list[i] == end + 1:
                end = changed_lines_list[i]
            else:
                ranges.append((start, end))
                start = changed_lines_list[i]
                end = changed_lines_list[i]
        
        ranges.append((start, end))
        return ranges
    
    return []

def function_overlaps_changes(function, changed_ranges):

    func_start = function['start_line']
    func_end = function['end_line']
    
    for range_start, range_end in changed_ranges:
        if not (func_end < range_start or func_start > range_end):
            return True
    
    return False

def extract_functions(tree, code):
    root = tree.root_node
    if not filter_file_code(root, code):
        return []

    code_bytes = code.encode("utf8")

    functions = []
    seen_ranges = set()  # Avoid duplicates (arrow functions/assignment expressions extracted repeatedly)

    def get_function_name(node):
        for child in node.children:
            if child.type in ("identifier", "property_identifier"):
                return code_bytes[child.start_byte:child.end_byte].decode("utf8")
        return "(anonymous)"

    def traverse(node):
        if node.type in FUNCTION_NODE_TYPES:

            key = (node.start_byte, node.end_byte)
            if key in seen_ranges:
                return
            seen_ranges.add(key)

            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            code_segment = code_bytes[node.start_byte:node.end_byte].decode("utf8")
            name = get_function_name(node)

            functions.append({
                "name": name,
                "start_line": start_line,
                "end_line": end_line,
                "code": code_segment,
            })

        for c in node.children:
            traverse(c)

    traverse(root)
    return functions

def extract_changed_functions(diff_text, file_content, ext):

    changed_ranges = parse_diff_lines(diff_text)
    
    if not changed_ranges:
        return [], ''

    if ext not in LANGUAGE_MAP:
        return [], ''
    
    language = Language(LANGUAGE_MAP[ext])
    parser = Parser(language)
    tree = parser.parse(file_content.encode("utf8"))
    all_functions = extract_functions(tree, file_content)
    
    if not all_functions:
        return [], ''
    
    changed_functions = []
    for func in all_functions:
        if function_overlaps_changes(func, changed_ranges):
            changed_functions.append(func)

    language_name = LANGUAGE_NAME_MAP.get(ext, "")
    return changed_functions, language_name