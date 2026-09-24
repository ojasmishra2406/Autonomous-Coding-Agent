import json
import shlex
import os
from typing import List, Dict, Optional, Any
from unidiff import PatchSet
from unidiff.errors import UnidiffParseError
from src.sandbox import Sandbox
from src.test_selector import TestSelector

class AgentTools:
    """
    Collection of 5 minimal tools that the coding agent can use to interact
    with the repository.
    """
    
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox
        self.changed_files = set()
        self.test_selector = TestSelector(sandbox)

    def list_files(self, path: str) -> List[str]:
        """
        Prevent: The agent being overwhelmed by irrelevant files (like compiled 
        objects or node_modules) or reading the entire repo at once.
        Using `git ls-files` naturally respects .gitignore.
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
        Prevent: The model hallucinating line numbers when constructing a patch. 
        By returning prefixed line numbers, the model has exact anchors for its edits.
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
            
        return "\n".join(result)

    def search_code(self, query: str, path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Prevent: The model blindly reading dozens of files to find a single function.
        ripgrep (rg) quickly surfaces exact matches with line numbers, saving context.
        """
        safe_query = shlex.quote(query)
        path_arg = shlex.quote(path) if path else "."
        # rg --json returns structured JSON objects for matches
        cmd = f"rg --json {safe_query} {path_arg}"
        
        stdout, stderr, exit_code = self.sandbox.exec(cmd, timeout=30)
        
        # ripgrep returns exit code 0 if match found, 1 if no match, 2 if error
        if exit_code == 2:
            return [{"error": f"Search failed: {stderr}"}]
            
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
                
        return matches

    def apply_patch(self, diff: str) -> Dict[str, Any]:
        """
        Prevent: A malformed diff crashing the sandbox quietly with a cryptic git error.
        Validating with `unidiff` first allows us to return a clean, structured Python
        error message back to the model so it understands *why* its diff syntax failed.
        """
        # Validate the diff syntax before touching the sandbox
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
                "suggestion": "Ensure the diff has standard unified diff headers (--- a/file\\n+++ b/file) and correct line prefixes (+, -, space)."
            }
            
        # Sandbox execution
        success = self.sandbox.apply_patch(diff)
        if not success:
            return {
                "success": False,
                "error": "Patch application failed",
                "details": "The patch was well-formed but did not apply cleanly to the repository."
            }
            
        return {"success": True}

    def replace_file_content(self, file_path: str, target_content: str, replacement_content: str) -> str:
        """
        Prevent: Model repeatedly failing to format unified diffs exactly right.
        Uses exact string replacement via a short Python script inside the sandbox.
        """
        import base64
        
        # Track changed file
        self.changed_files.add(file_path)
        
        # We base64 encode strings to pass them safely into the sandbox via bash
        target_b64 = base64.b64encode(target_content.encode('utf-8')).decode('utf-8')
        replace_b64 = base64.b64encode(replacement_content.encode('utf-8')).decode('utf-8')
        
        # Build the python script that will run inside the sandbox
        py_code = f"""
import base64, sys, os
file_path = {repr(file_path)}
target = base64.b64decode('{target_b64}').decode('utf-8')
replacement = base64.b64decode('{replace_b64}').decode('utf-8')

# Ensure we're targeting the right file inside the sandbox
full_path = os.path.join('/workspace/repo', file_path) if not file_path.startswith('/workspace/repo') else file_path

try:
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if target not in content:
        print('Error: target_content not found exactly in the file. Check whitespace and indentation.', file=sys.stderr)
        sys.exit(1)
        
    if content.count(target) > 1:
        print('Error: target_content found multiple times. Provide more lines for unique context.', file=sys.stderr)
        sys.exit(1)
        
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content.replace(target, replacement))
        
    print('File updated successfully.')
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
        Prevent: The agent assuming it fixed the issue just because it wrote a patch.
        Forces the agent to run the tests and observe real stderr before concluding.
        """
        selection_method = "model-specified"
        timeout_val = 120
        
        if not test_ids:
            if not self.changed_files:
                return {
                    "passed": False,
                    "error": "You must provide specific test_ids or edit a file first. Running the entire test suite is too slow.",
                    "stderr": "",
                    "output": ""
                }
                
            test_ids = self.test_selector.select_relevant_tests(list(self.changed_files))
            
            # Check for config/settings changes
            has_config_change = any(f.endswith('settings.py') or f.endswith('conf.py') or 'config' in f for f in self.changed_files)
            if not test_ids and has_config_change:
                test_ids = []  # empty implies run full suite in Sandbox logic
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
        
        # Override the timeout for run_tests in sandbox if possible, but Sandbox API currently might have it hardcoded.
        # We will log the selection method.
        # Let's pass the timeout to run_tests if it accepts it.
        # We need to check Sandbox run_tests signature.
        try:
            result = self.sandbox.run_tests(test_ids, timeout=timeout_val)
        except TypeError:
            result = self.sandbox.run_tests(test_ids) # fallback if timeout is not a param
            
        return {
            "passed": result.passed,
            "stderr": result.stderr,
            "output": f"[TEST SELECTION METHOD: {selection_method}]\n" + result.output
        }
