"""
Dataset loader for SWE-bench Lite.

CRITICAL WARNING:
Golden patches (the `patch` field) and test patches (the `test_patch` field)
must NEVER be passed into the agent's runtime context.
These fields contain the actual solutions and the evaluation tests for the task.
If the agent sees the golden patch, it can simply copy the solution, rendering
the evaluation completely meaningless. If it sees the test patch, it can overfit
to the specific tests rather than solving the underlying problem correctly.
These fields exist purely so the evaluation harness can grade the agent's
work after the fact.
"""

import json
import random
from collections import defaultdict
from typing import List
from pydantic import BaseModel
from datasets import load_dataset

class Task(BaseModel):
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    FAIL_TO_PASS: str
    PASS_TO_FAIL: str
    patch: str
    test_patch: str

def _get_all_tasks() -> List[Task]:
    # Load the test split which contains 300 instances for SWE-bench Lite
    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    
    tasks = []
    for item in ds:
        tasks.append(
            Task(
                instance_id=item["instance_id"],
                repo=item["repo"],
                base_commit=item["base_commit"],
                problem_statement=item["problem_statement"],
                FAIL_TO_PASS=item["FAIL_TO_PASS"],
                PASS_TO_FAIL=item.get("PASS_TO_FAIL", item.get("PASS_TO_PASS", "")),
                patch=item["patch"],
                test_patch=item["test_patch"],
            )
        )
    # Sort by instance_id for absolute determinism
    tasks.sort(key=lambda x: x.instance_id)
    return tasks

def _stratified_sample(tasks: List[Task], n: int, seed: int) -> List[Task]:
    # Group by repo
    repo_to_tasks = defaultdict(list)
    for t in tasks:
        repo_to_tasks[t.repo].append(t)
        
    # Sort repos and their tasks for determinism before shuffling
    repos = sorted(repo_to_tasks.keys())
    for r in repos:
        repo_to_tasks[r].sort(key=lambda x: x.instance_id)
        
    rng = random.Random(seed)
    for r in repos:
        rng.shuffle(repo_to_tasks[r])
        
    sampled = []
    repo_idx = 0
    while len(sampled) < n:
        r = repos[repo_idx % len(repos)]
        if repo_to_tasks[r]:
            sampled.append(repo_to_tasks[r].pop(0))
        repo_idx += 1
        
    # Return to original sort order or keep as is? Keep sorted by instance_id
    sampled.sort(key=lambda x: x.instance_id)
    return sampled

def load_tasks(split: str = "dev", n: int = 30, seed: int = 42) -> List[Task]:
    all_tasks = _get_all_tasks()
    
    # We want dev and eval to have zero overlap.
    # We can compute the dev set using the seed, then for eval, we exclude the dev set,
    # then take a sample from the remainder.
    # To be fully deterministic, we always compute dev first.
    dev_tasks = _stratified_sample(all_tasks.copy(), 30, seed)
    
    if split == "dev":
        result = dev_tasks[:n]
        _save_split("dev_tasks.jsonl", result)
        return result
    elif split == "eval":
        dev_ids = {t.instance_id for t in dev_tasks}
        remaining = [t for t in all_tasks if t.instance_id not in dev_ids]
        result = _stratified_sample(remaining, n, seed + 1)
        _save_split("eval_tasks.jsonl", result)
        return result
    else:
        raise ValueError(f"Unknown split: {split}")

def _save_split(filename: str, tasks: List[Task]):
    import os
    os.makedirs("data", exist_ok=True)
    filepath = os.path.join("data", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        for t in tasks:
            # Dump to JSON and write to line
            f.write(t.model_dump_json() + "\n")
