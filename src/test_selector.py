import os
import shlex
from typing import List

def _path_similarity(src_dir: str, test_dir: str) -> int:
    src_parts = [p.lower() for p in src_dir.split('/') if p not in ('', '.', '..')]
    test_parts = [p.lower() for p in test_dir.split('/') if p not in ('', '.', '..', 'tests', 'test')]
    score = 0
    for sp in src_parts:
        if sp in ('src', 'lib', 'tests', 'test', 'django', 'astropy'): continue
        sp_base = sp.rstrip('s')
        if len(sp_base) < 3: continue
        for tp in test_parts:
            tp_base = tp.rstrip('s')
            if sp_base in tp_base or tp_base in sp_base:
                score += 1
    return score

class TestSelector:
    def __init__(self, sandbox):
        self.sandbox = sandbox
        
    def select_relevant_tests(self, changed_files: List[str]) -> List[str]:
        tests_to_run = set()
        
        for changed_file in changed_files:
            basename = os.path.basename(changed_file)
            if not basename.endswith(".py"):
                continue
                
            if basename.startswith("test_") or basename.endswith("_test.py"):
                tests_to_run.add(changed_file)
                continue
                
            module_name = basename[:-3]
            dirname = os.path.dirname(changed_file).replace("\\\\", "/")
            
            # A: Co-located
            possible_colocated = [
                os.path.join(dirname, f"test_{module_name}.py").replace("\\\\", "/"),
                os.path.join(dirname, f"{module_name}_test.py").replace("\\\\", "/"),
                os.path.join(dirname, "tests", f"test_{module_name}.py").replace("\\\\", "/"),
                os.path.join(dirname, "tests", f"{module_name}_test.py").replace("\\\\", "/")
            ]
            
            found_colocated = False
            for p in possible_colocated:
                stdout, _, exit_code = self.sandbox.exec(f"test -f /workspace/repo/{shlex.quote(p)}", timeout=10)
                if exit_code == 0:
                    tests_to_run.add(p)
                    found_colocated = True
            
            if found_colocated:
                continue
                
            # B: Mirror-directory
            cmd = f"find /workspace/repo -name 'test_{module_name}.py' -o -name '{module_name}_test.py'"
            stdout, _, exit_code = self.sandbox.exec(cmd, timeout=30)
            if exit_code == 0 and stdout.strip():
                matches = [os.path.relpath(m, "/workspace/repo").replace("\\\\", "/") for m in stdout.splitlines() if m.strip()]
                scored = [( _path_similarity(dirname, os.path.dirname(m)), m ) for m in matches]
                max_score = max([s for s, m in scored] + [0])
                if max_score > 0:
                    best_matches = [m for s, m in scored if s == max_score]
                    for m in best_matches:
                        tests_to_run.add(m)
                    continue
                
            # C: Import graph fallback
            grep_cmd = f"grep -rl {shlex.quote(module_name)} /workspace/repo | grep -E 'test_.*\\.py$|.*_test\\.py$'"
            stdout, _, exit_code = self.sandbox.exec(grep_cmd, timeout=30)
            if exit_code == 0 and stdout.strip():
                matches = [os.path.relpath(m, "/workspace/repo").replace("\\\\", "/") for m in stdout.splitlines() if m.strip()]
                scored = [( _path_similarity(dirname, os.path.dirname(m)), m ) for m in matches]
                max_score = max([s for s, m in scored] + [0])
                if max_score > 0:
                    best_matches = [m for s, m in scored if s == max_score][:3]
                    for m in best_matches:
                        tests_to_run.add(m)
                    continue
                else:
                    for m in matches[:3]:
                        tests_to_run.add(m)
                    continue
                
        if not tests_to_run and len(changed_files) <= 3:
            for changed_file in changed_files:
                tests_to_run.add(os.path.dirname(changed_file).replace("\\\\", "/"))
                
        return list(tests_to_run)
