import re

def update_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    replacement = '''def main():
    print("Cleaning up orphaned sandbox-base containers...")
    try:
        import docker
        client = docker.from_env()
        for container in client.containers.list(all=True):
            if 'sandbox-base' in str(container.image.tags):
                container.remove(force=True)
    except Exception as e:
        print(f"Warning: could not clean containers: {e}")
    print("Done cleaning up containers.")
    
    print("Resetting runs.db...")
    try:
        import sqlite3
        with sqlite3.connect("runs.db") as conn:
            conn.execute("DELETE FROM runs;")
            conn.commit()
    except Exception as e:
        pass
'''
    content = re.sub(r'def main\(\):.*?(?=    parser = argparse\.ArgumentParser)', replacement, content, flags=re.DOTALL)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

update_file('scripts/run_eval.py')
try:
    update_file('scripts/run_dev.py')
except:
    pass
