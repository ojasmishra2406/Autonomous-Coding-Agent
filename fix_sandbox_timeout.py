with open("src/sandbox.py", "r", encoding="utf-8") as f:
    content = f.read()
    
content = content.replace("docker.from_env(timeout=60)", "docker.from_env(timeout=300)")

with open("src/sandbox.py", "w", encoding="utf-8") as f:
    f.write(content)
