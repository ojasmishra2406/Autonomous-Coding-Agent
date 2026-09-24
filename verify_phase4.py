import os
import subprocess
import json
import tiktoken
from src.repo_map import build_repo_map

def clone_if_not_exists(repo_url, target_dir):
    if not os.path.exists(target_dir):
        print(f"Cloning {repo_url}...")
        subprocess.check_call(["git", "clone", repo_url, target_dir])

def verify():
    enc = tiktoken.get_encoding("cl100k_base")
    
    # 1. Three repos of different sizes
    repos = {
        "Small (this repo)": ".",
        "Medium (Flask)": "test_repos/flask",
        "Large (Requests)": "test_repos/requests"
    }
    
    os.makedirs("test_repos", exist_ok=True)
    clone_if_not_exists("https://github.com/pallets/flask.git", "test_repos/flask")
    clone_if_not_exists("https://github.com/psf/requests.git", "test_repos/requests")
    
    print("\n--- 1. Testing on 3 repos of different sizes ---")
    for size_name, path in repos.items():
        out = build_repo_map(path)
        tokens = len(enc.encode(out))
        print(f"{size_name} repo token count: {tokens}")
        print("Sample output:")
        print("\n".join(out.splitlines()[:15]))
        if "truncated" in out:
            print("[Note: Output was truncated as expected for large repos]")
        print("-" * 40)
        
    # 2. Pick a sample issue and check relevance
    print("\n--- 2. Checking sample issue relevance ---")
    with open("data/dev_tasks.jsonl", "r") as f:
        task_data = json.loads(f.readline())
        
    print(f"Task ID: {task_data['instance_id']}, Repo: {task_data['repo']}")
    repo_url = f"https://github.com/{task_data['repo']}.git"
    task_repo_dir = f"test_repos/{task_data['repo'].replace('/', '_')}"
    
    clone_if_not_exists(repo_url, task_repo_dir)
    subprocess.check_call(["git", "-C", task_repo_dir, "checkout", task_data["base_commit"]])
    
    # Get repo map for this issue
    issue_map = build_repo_map(task_repo_dir, task_data["problem_statement"])
    print(f"Generated map for issue {task_data['instance_id']} ({len(enc.encode(issue_map))} tokens).")
    
    # Read the golden patch to see which files were actually modified
    print("Golden patch modified files:")
    modified_files = []
    for line in task_data["patch"].splitlines():
        if line.startswith("--- a/"):
            modified_files.append(line[6:])
    print(modified_files)
    
    # Check if modified files are in the repo map
    for f in modified_files:
        if f in issue_map:
            print(f"SUCCESS: Modified file {f} WAS included in the repo map!")
        else:
            print(f"MISS: Modified file {f} was NOT included in the repo map.")
            
    # 3. Pathological case (no matching terms)
    print("\n--- 3. Testing pathological case (no matching terms) ---")
    pathological_map = build_repo_map("test_repos/flask", "xyzzy plugh zorkmid")
    tokens_path = len(enc.encode(pathological_map))
    print(f"Pathological map tokens: {tokens_path}")
    print("Sample output (first few lines):")
    print("\n".join(pathological_map.splitlines()[:10]))
    if tokens_path > 100:
        print("SUCCESS: Pathological map degraded gracefully to show shortest paths instead of crashing/empty.")

if __name__ == "__main__":
    verify()
