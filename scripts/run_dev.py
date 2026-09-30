import os
import sys
import json
import sqlite3
import argparse
import traceback
from typing import List

# Ensure src is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.dataset import Task
from src.sandbox import Sandbox
from src.agent import CodingAgent, AgentStatus
from src.tracing import Tracer

def is_task_completed(instance_id: str) -> bool:
    if not os.path.exists("runs.db"):
        return False
    with sqlite3.connect("runs.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM runs WHERE instance_id = ?", (instance_id,))
        row = cursor.fetchone()
        if row:
            # We consider it completed if it has any terminal status
            # FAILED_WITH_EXCEPTION is a custom status added by this script
            return True
    return False

def main():
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
    
    
    print("Archiving runs.db...")
    try:
        import sqlite3
        import datetime
        import uuid
        with sqlite3.connect("runs.db") as conn:
            c = conn.cursor()
            
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs';")
            if c.fetchone():
                c.execute("SELECT COUNT(*) FROM runs;")
                count = c.fetchone()[0]
                if count > 0:
                    batch_id = str(uuid.uuid4())
                    archived_at = datetime.datetime.now().isoformat()
                    # We assume runs_archive was created by our migration script
                    c.execute("""
                        INSERT INTO runs_archive 
                        (run_batch_id, archived_at, instance_id, status, steps_taken, total_tokens, cost_usd, wall_clock_seconds, timestamp, thoughts_tokens, provider)
                        SELECT ?, ?, instance_id, status, steps_taken, total_tokens, cost_usd, wall_clock_seconds, timestamp, thoughts_tokens, provider
                        FROM runs;
                    """, (batch_id, archived_at))
                    c.execute("DELETE FROM runs;")
                    conn.commit()
                    print(f"Archived {count} runs to runs_archive with batch ID {batch_id}.")
    except Exception as e:
        print(f"Failed to archive runs.db: {e}")
    
    parser = argparse.ArgumentParser(description="Run the CodingAgent against the dev set.")
    parser.add_argument("--fresh", action="store_true", help="Clear runs.db before starting")
    parser.add_argument("--max-tasks", type=int, default=None, help="Maximum number of tasks to run.")
    parser.add_argument("--resume-from", type=str, default=None, help="Force resume from a specific task ID, skipping everything before it.")
    parser.add_argument("--max-steps", type=int, default=15, help="Max steps per task.")
    args = parser.parse_args()

    tasks: List[Task] = []
    with open("data/subset_tasks.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            tasks.append(Task(**json.loads(line)))

    # Handle resume-from logic
    if args.resume_from:
        resume_idx = -1
        for i, t in enumerate(tasks):
            if t.instance_id == args.resume_from:
                resume_idx = i
                break
        if resume_idx != -1:
            tasks = tasks[resume_idx:]
            print(f"Resuming from task {args.resume_from} (index {resume_idx})")
        else:
            print(f"Task {args.resume_from} not found in dev set.")
            return

    if args.max_tasks is not None:
        tasks = tasks[:args.max_tasks]

    total = len(tasks)
    print(f"Starting Dev-Set Runner for {total} tasks...")

    sandbox = Sandbox()
    agent = CodingAgent()
    
    results_summary = []

    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{total}] Checking {task.instance_id}...")
        
        if is_task_completed(task.instance_id):
            print(f"[{i}/{total}] Task {task.instance_id} already has a terminal status in runs.db. Skipping.")
            continue
            
        print(f"[{i}/{total}] Running {task.instance_id}...")
        
        sandbox.start(repo_url=f"https://github.com/{task.repo}.git", commit_sha=task.base_commit, instance_id=task.instance_id)
        
        try:
            result = agent.solve(task, sandbox, max_steps=args.max_steps, allow_fallback=True)
            print(f"[{i}/{total}] Finished {task.instance_id} with status: {result.status.value}")
            
            if result.final_patch:
                with open(f"traces/{task.instance_id}_final.patch", "w") as pf:
                    pf.write(result.final_patch)
                    
            if result.transcript:
                with open(f"traces/{task.instance_id}_transcript.txt", "w", encoding="utf-8") as tf:
                    tf.write(json.dumps(result.transcript, indent=2))
                    
            results_summary.append({
                "instance_id": task.instance_id,
                "status": result.status.value,
                "steps": result.steps_taken
            })
        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"[{i}/{total}] FAILED_WITH_EXCEPTION on {task.instance_id}: {str(e)}")
            
            # Record the failure manually so we skip it next time
            tracer = Tracer(task.instance_id)
            # Use 0 for tokens and step budget
            tracer.record_run("FAILED_WITH_EXCEPTION", 0, 0, 0, 0)
            
            results_summary.append({
                "instance_id": task.instance_id,
                "status": "FAILED_WITH_EXCEPTION",
                "steps": 0
            })
        finally:
            sandbox.reset()

    # Aggregate provider usage and tool usage from traces
    provider_counts = {}
    tool_counts = {"apply_patch": 0, "replace_file_content": 0}
    non_empty_patches = 0
    
    for t in tasks:
        trace_file = f"traces/{t.instance_id}.jsonl"
        has_non_empty_patch = False
        if os.path.exists(trace_file):
            with open(trace_file, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        
                        # Provider tracking
                        p = entry.get("provider_used", "unknown")
                        if p:
                            provider_counts[p] = provider_counts.get(p, 0) + 1
                            
                        # Tool tracking
                        tool = entry.get("tool_called")
                        if tool in tool_counts:
                            tool_counts[tool] += 1
                            
                        # Final patch tracking
                        if entry.get("event") == "run_completed":
                            if entry.get("final_patch") and len(entry["final_patch"].strip()) > 0:
                                has_non_empty_patch = True
                    except:
                        pass
        if has_non_empty_patch:
            non_empty_patches += 1

    # Generate Summary Table
    if os.path.exists("runs.db"):
        with sqlite3.connect("runs.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, steps_taken, cost_usd FROM runs WHERE instance_id IN ({seq})".format(
                seq=','.join(['?']*len(tasks))), [t.instance_id for t in tasks])
            rows = cursor.fetchall()
            
            if rows:
                resolved_count = sum(1 for r in rows if r[0] == AgentStatus.SUCCESS.value)
                total_runs = len(rows)
                timeout_count = sum(1 for r in rows if r[0] == AgentStatus.TIMEOUT.value)
                avg_steps = sum(r[1] for r in rows) / total_runs
                avg_cost = sum(r[2] for r in rows) / total_runs
                
                print("\n" + "="*40)
                print("DEV SET RUN SUMMARY")
                print("="*40)
                print(f"Total Tasks Run    : {total_runs}")
                print(f"Resolved Count     : {resolved_count} ({resolved_count/total_runs*100:.1f}%)")
                print(f"Timeout Rate       : {timeout_count/total_runs*100:.1f}%")
                print(f"Avg Steps Taken    : {avg_steps:.2f}")
                print(f"Avg Cost per Task  : ${avg_cost:.4f}")
                print(f"Tasks w/ final diff: {non_empty_patches} out of {total_runs}")
                print("-" * 40)
                print("Tool Usage (Edits):")
                print(f"  apply_patch            : {tool_counts['apply_patch']}")
                print(f"  replace_file_content   : {tool_counts['replace_file_content']}")
                print("-" * 40)
                print("Provider Step Distribution:")
                for p, count in sorted(provider_counts.items(), key=lambda x: x[1], reverse=True):
                    print(f"  {p.capitalize():<10}: {count} steps")
                print("="*40)

if __name__ == "__main__":
    main()
