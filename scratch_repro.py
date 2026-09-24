import sys, os, json, traceback
sys.path.insert(0, os.path.abspath("."))
from dotenv import load_dotenv; load_dotenv()

from src.dataset import Task
from src.sandbox import Sandbox
from src.agent import CodingAgent

with open('data/dev_tasks.jsonl', 'r', encoding='utf-8') as f:
    task = Task(**json.loads(f.readline()))

sb = Sandbox()
sb.start(repo_url=f'https://github.com/{task.repo}.git', commit_sha=task.base_commit)
print(f"Sandbox started. Running agent on {task.instance_id}...")

agent = CodingAgent()
try:
    result = agent.solve(task, sb, max_steps=3)
    print("RESULT:", result.status)
except BaseException as e:
    print("CAUGHT BaseException:", type(e).__name__)
    traceback.print_exc()
finally:
    sb.reset()
    print("Sandbox reset.")
