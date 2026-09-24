import re

with open('scripts/run_eval.py', 'r', encoding='utf-8') as f:
    content = f.read()

main_replace = '''def main():
    print("Cleaning up orphaned sandbox-base containers...")
    try:
        import docker
        client = docker.from_env()
        for container in client.containers.list(all=True):
            if 'sandbox-base' in str(container.image):
                container.remove(force=True)
    except Exception as e:
        print(f"Warning: could not clean containers: {e}")
    print("Done cleaning up containers.")
    
    print("Resetting runs.db...")
    try:
        with sqlite3.connect("runs.db") as conn:
            conn.execute("DELETE FROM runs;")
    except Exception as e:
        print(f"Warning: could not reset runs.db: {e}")'''

content = re.sub(r'def main\(\):\n    print\("Cleaning up orphaned sandbox-base containers\.\.\."\).*?print\("Done cleaning up containers\."\)', main_replace, content, flags=re.DOTALL)

with open('scripts/run_eval.py', 'w', encoding='utf-8') as f:
    f.write(content)
