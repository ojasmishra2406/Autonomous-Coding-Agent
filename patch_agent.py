import re

with open("src/agent.py", "r", encoding="utf-8") as f:
    content = f.read()

pattern = r'with tempfile\.TemporaryDirectory\(\) as tmpdir:.*?repo_map built\."'
replacement = '''with tempfile.TemporaryDirectory() as tmpdir:
            print("DEBUG: Extracting repo from sandbox for repo map...")
            import subprocess
            subprocess.check_call(["docker", "cp", f"{sandbox.container.id}:{sandbox.repo_dir}", f"{tmpdir}/repo"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("DEBUG: Building repo map...")
            repo_map = build_repo_map(f"{tmpdir}/repo", task.problem_statement)
            print("DEBUG: Repo map built."'''

content = re.sub(pattern, replacement, content, flags=re.DOTALL)
with open("src/agent.py", "w", encoding="utf-8") as f:
    f.write(content)
