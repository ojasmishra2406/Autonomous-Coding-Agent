import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.sandbox import Sandbox
from src.dataset import Task
from src.test_selector import TestSelector
import json

def test_selector():
    tasks_to_test = [
        ("django__django-11630", ["django/db/models/base.py"]), 
        ("astropy__astropy-12907", ["astropy/modeling/separable.py"]), 
        ("django__django-10914", ["django/core/files/storage.py"]) 
    ]
    
    with open("data/eval_tasks.jsonl", "r", encoding="utf-8") as f:
        all_data = [json.loads(line) for line in f]
        
    for instance_id, changed_files in tasks_to_test:
        print(f"\n--- Testing {instance_id} ---")
        data = next(d for d in all_data if d["instance_id"] == instance_id)
        task = Task(**data)
        if not task.repo.startswith("http"):
            task.repo = f"https://github.com/{task.repo}.git"
        sb = Sandbox()
        sb.start(task.repo, task.base_commit)
        try:
            selector = TestSelector(sb)
            results = selector.select_relevant_tests(changed_files)
            print(f"Changed files: {changed_files}")
            print(f"Selected tests: {results}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_selector()
