import json
import shlex
import os
import base64
from typing import List, Dict, Optional, Any
from unidiff import PatchSet
from unidiff.errors import UnidiffParseError
from src.sandbox import Sandbox
from src.test_selector import TestSelector

def _truncate(text: str, max_len: int = 2000) -> str:
    """Helper to truncate middle of long outputs."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    if len(text) > max_len:
        keep = max_len // 2
        return text[:keep] + f"\n... [{len(text) - max_len} characters truncated] ...\n" + text[-keep:]
    return text

class AgentTools:
    """
    Collection of tools that the coding agent can use to interact with the repository.
    """
    
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox
        self.changed_files = set()
        self.test_selector = TestSelector(sandbox)
        self.scratchpad = ""

    def update_scratchpad(self, notes: str) -> str:
        """
        Overwrites the scratchpad string held in the agent's state.
        """
        self.scratchpad = notes
        return "Scratchpad updated successfully."

    def list_files(self, path: str) -> List[str]:
        """
        List files in a directory respecting .gitignore.
        """
        safe_path = shlex.quote(path)
        cmd = f"git -C /workspace/repo ls-files {safe_path}"
        stdout, stderr, exit_code = self.sandbox.exec(cmd, timeout=30)
        
        if exit_code != 0:
            return [f"Error listing files: {stderr}"]
            
        files = [f.strip() for f in stdout.splitlines() if f.strip()]
        if len(files) > 250:
            return files[:250] + [f"... and {len(files) - 250} more files. Please specify a more specific path/directory to list."]
        return files

    def read_file(self, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        """
        Read the contents of a file, returning prefixed line numbers.
        """
        safe_path = shlex.quote(path)
        cmd = f"cat /workspace/repo/{safe_path}"
        stdout, stderr, exit_code = self.sandbox.exec(cmd, timeout=30)
        
        if exit_code != 0:
            return f"Error reading file: {stderr}"
            
        lines = stdout.splitlines()
        
        start = max(0, (start_line - 1)) if start_line is not None else 0
        end = min(len(lines), end_line) if end_line is not None else len(lines)
        
        if start >= len(lines):
            return "Error: start_line is beyond the end of the file."
            
        result = []
        for i, line in enumerate(lines[start:end], start=start + 1):
            result.append(f"{i:4d} | {line}")
            
        result_str = "\n".join(result)
        if start_line is None and end_line is None:
            return _truncate(result_str)
        return result_str

    def search_code(self, query: str, path: Optional[str] = None) -> str:
        """
        Search for a string or regex using ripgrep.
        """
        safe_query = shlex.quote(query)
        path_arg = shlex.quote(path) if path else "."
        cmd = f"rg --json {safe_query} {path_arg}"
        
        stdout, stderr, exit_code = self.sandbox.exec(cmd, timeout=30)
        
        if exit_code == 2:
            return f"Search failed: {stderr}"
            
        matches = []
        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if data.get("type") == "match":
                    match_data = data["data"]
                    file_path = match_data["path"]["text"]
                    line_num = match_data["line_number"]
                    match_text = match_data["lines"]["text"].rstrip('\n')
                    matches.append({
                        "file": file_path,
                        "line": line_num,
                        "match_text": match_text
                    })
            except json.JSONDecodeError:
                continue
                
        matches_str = json.dumps(matches, indent=2)
        return _truncate(matches_str)

    def apply_patch(self, diff: str) -> Dict[str, Any]:
        """
        Apply a unified diff patch.
        """
        try:
            patch = PatchSet(diff)
            if len(patch) == 0:
                raise UnidiffParseError("No valid unified diff headers found (--- a/file, +++ b/file)")
            for p in patch:
                self.changed_files.add(p.path)
        except UnidiffParseError as e:
            return {
                "success": False,
                "error": "Malformed unified diff",
                "details": str(e),
                "suggestion": "Ensure the diff has standard headers (--- a/file\n+++ b/file) and correct line prefixes (+, -, space)."
            }
            
        success = self.sandbox.apply_patch(diff)
        if not success:
            return {
                "success": False,
                "error": "Patch application failed",
                "details": "The patch was well-formed but did not apply cleanly to the repository."
            }
            
        return {"success": True}

    def edit_file(self, filepath: str, start_line: int, end_line: int, new_content: str) -> str:
        """
        Replaces a line range in a file with new content.
        """
        self.changed_files.add(filepath)
        
        new_b64 = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
        
        py_code = f"""
import base64, sys, os, py_compile
file_path = {repr(filepath)}
start_line = {start_line}
end_line = {end_line}
new_content = base64.b64decode('{new_b64}').decode('utf-8')

full_path = os.path.join('/workspace/repo', file_path) if not file_path.startswith('/workspace/repo') else file_path

try:
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    lines = content.splitlines(keepends=True)
    backup_content = content
    
    start_idx = max(0, start_line - 1)
    end_idx = min(len(lines), end_line)
    
    new_lines = new_content.splitlines(keepends=True)
    if new_lines and not new_lines[-1].endswith('\\n') and end_idx < len(lines):
        new_lines[-1] += '\\n'
        
    lines[start_idx:end_idx] = new_lines
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
        
    if full_path.endswith('.py'):
        try:
            py_compile.compile(full_path, doraise=True)
        except Exception as e:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(backup_content)
            print('Syntax validation failed after edit. Edit reverted. Compile error:\\n' + str(e), file=sys.stderr)
            sys.exit(1)
            
    print('Edit successful.')
except Exception as e:
    print('Error: ' + str(e), file=sys.stderr)
    sys.exit(1)
"""
        py_code_b64 = base64.b64encode(py_code.encode('utf-8')).decode('utf-8')
        cmd = f"python3 -c \"import base64, sys; exec(base64.b64decode('{py_code_b64}').decode('utf-8'))\""
        
        stdout, stderr, exit_code = self.sandbox.exec(cmd, timeout=30)
        
        if exit_code != 0:
            return f"Edit failed:\n{stderr.strip() or stdout.strip()}"
            
        return "Edit successful."

    def replace_file_content(self, file_path: str, target_content: str, replacement_content: str) -> str:
        """
        Uses exact string replacement via a short Python script inside the sandbox.
        """
        self.changed_files.add(file_path)
        
        target_b64 = base64.b64encode(target_content.encode('utf-8')).decode('utf-8')
        replace_b64 = base64.b64encode(replacement_content.encode('utf-8')).decode('utf-8')
        
        py_code = f"""
import base64, sys, os, difflib, py_compile
file_path = {repr(file_path)}
target = base64.b64decode('{target_b64}').decode('utf-8')
replacement = base64.b64decode('{replace_b64}').decode('utf-8')

full_path = os.path.join('/workspace/repo', file_path) if not file_path.startswith('/workspace/repo') else file_path

try:
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if target not in content:
        lines = content.splitlines()
        target_lines = target.splitlines()
        if target_lines:
            closest = difflib.get_close_matches(target_lines[0], lines, n=1, cutoff=0.3)
            if closest:
                idx = lines.index(closest[0])
                context_start = max(0, idx - 2)
                context_end = min(len(lines), idx + 3)
                context_lines = '\\n'.join(lines[context_start:context_end])
                print(f'Error: target_content not found exactly in the file. Check whitespace and indentation. The closest existing content (around line {{idx+1}}) is:\\n{{context_lines}}', file=sys.stderr)
            else:
                print('Error: target_content not found exactly in the file.', file=sys.stderr)
        else:
            print('Error: target_content not found exactly in the file.', file=sys.stderr)
        sys.exit(1)
        
    if content.count(target) > 1:
        print('Error: target_content found multiple times. Provide more lines for unique context.', file=sys.stderr)
        sys.exit(1)
        
    backup_content = content
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content.replace(target, replacement))
        
    if full_path.endswith('.py'):
        try:
            py_compile.compile(full_path, doraise=True)
        except Exception as e:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(backup_content)
            print('Syntax validation failed after edit. Edit reverted. Compile error:\\n' + str(e), file=sys.stderr)
            sys.exit(1)
            
    print('Replacement successful.')
except Exception as e:
    print('Error: ' + str(e), file=sys.stderr)
    sys.exit(1)
"""
        py_code_b64 = base64.b64encode(py_code.encode('utf-8')).decode('utf-8')
        cmd = f"python3 -c \"import base64, sys; exec(base64.b64decode('{py_code_b64}').decode('utf-8'))\""
        
        stdout, stderr, exit_code = self.sandbox.exec(cmd, timeout=30)
        
        if exit_code != 0:
            return f"Replacement failed:\n{stderr.strip() or stdout.strip()}"
            
        return "Replacement successful."

    def run_tests(self, test_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run tests and format output, truncating if necessary.
        """
        selection_method = "model-specified"
        timeout_val = 120
        
        if not test_ids:
            if not self.changed_files:
                return {
                    "passed": False,
                    "error": "You must provide specific test_ids or edit a file first.",
                    "stderr": "",
                    "output": ""
                }
                
            test_ids = self.test_selector.select_relevant_tests(list(self.changed_files))
            
            has_config_change = any(f.endswith('settings.py') or f.endswith('conf.py') or 'config' in f for f in self.changed_files)
            if not test_ids and has_config_change:
                test_ids = []
                selection_method = "full-suite-escalation"
                timeout_val = 600
            else:
                selection_method = "auto-selected"
            
            if not test_ids and selection_method != "full-suite-escalation":
                return {
                    "passed": False,
                    "error": "Auto-selection found no relevant tests for your changes. You must provide specific test_ids.",
                    "stderr": "",
                    "output": ""
                }
        
        try:
            result = self.sandbox.run_tests(test_ids, timeout=timeout_val)
        except TypeError:
            result = self.sandbox.run_tests(test_ids)
            
        return {
            "passed": result.passed,
            "stderr": _truncate(result.stderr),
            "output": f"[TEST SELECTION METHOD: {selection_method}]\n" + _truncate(result.output)
        }
