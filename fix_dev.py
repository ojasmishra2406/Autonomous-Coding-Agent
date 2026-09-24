with open("scripts/run_dev.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    'sandbox.start(repo_url=f"https://github.com/{task.repo}.git", commit_sha=task.base_commit)', 
    'sandbox.start(repo_url=f"https://github.com/{task.repo}.git", commit_sha=task.base_commit, instance_id=task.instance_id)'
)

with open("scripts/run_dev.py", "w", encoding="utf-8") as f:
    f.write(content)
