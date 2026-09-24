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

# NOTE: This script's results are treated as final once run, and reruns must be appended alongside prior results, never overwriting them.
# -----------------------------------------------------------------------------
# DISCLAIMER: DO NOT RUN THIS SCRIPT UNTIL READY FOR FINAL EVALUATION.
# Running the evaluation set before finalizing the agent risks overfitting 
# to the evaluation data. Use run_dev.py for iterative development instead.
# -----------------------------------------------------------------------------

def is_task_completed(instance_id: str) -> bool:
    if not os.path.exists("runs.db"):
        return False
    with sqlite3.connect("runs.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM runs WHERE instance_id = ?", (instance_id,))
        row = cursor.fetchone()
        if row:
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
    
    parser = argparse.ArgumentParser(description="Run the CodingAgent against the final eval set.")
    parser.add_argument("--fresh", action="store_true", help="Clear runs.db before starting")
    parser.add_argument("--max-tasks", type=int, default=None, help="Maximum number of tasks to run.")
    parser.add_argument("--task-id", type=str, default=None)
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--resume-from", type=str, default=None, help="Force resume from a specific task ID, skipping everything before it.")
    args = parser.parse_args()

    tasks: List[Task] = []
    with open("data/eval_tasks.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            tasks.append(Task(**json.loads(line)))

    # Ensure single pinned provider is used in eval
    provider = os.environ.get("MODEL_PROVIDER", "gemini").lower()
    print(f"========================================")
    print(f"EVAL SET RUN")
    print(f"PINNED MODEL PROVIDER: {provider.upper()}")
    print(f"========================================")

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
            print(f"Task {args.resume_from} not found in eval set.")
            return

    if args.max_tasks is not None:
        tasks = tasks[:args.max_tasks]

    total = len(tasks)
    print(f"Starting Eval-Set Runner for {total} tasks...")

    sandbox = Sandbox()
    agent = CodingAgent()

    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{total}] Checking {task.instance_id}...")
        
        if is_task_completed(task.instance_id):
            print(f"[{i}/{total}] Task {task.instance_id} already has a terminal status in runs.db. Skipping.")
            continue
            
        print(f"[{i}/{total}] Running {task.instance_id}...")
        
        try:
            sandbox.start(repo_url=f"https://github.com/{task.repo}.git", commit_sha=task.base_commit, instance_id=task.instance_id)
            result = agent.solve(task, sandbox, max_steps=15, allow_fallback=True)
            print(f"[{i}/{total}] Finished {task.instance_id} with status: {result.status.value}")
            
            if result.final_patch:
                with open(f"traces/{task.instance_id}_final.patch", "w") as pf:
                    pf.write(result.final_patch)
                    
            if result.transcript:
                with open(f"traces/{task.instance_id}_transcript.txt", "w", encoding="utf-8") as tf:
                    tf.write(json.dumps(result.transcript, indent=2))
        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"[{i}/{total}] FAILED_WITH_EXCEPTION on {task.instance_id}: {str(e)}")
            
            tracer = Tracer(task.instance_id)
            tracer.record_run("FAILED_WITH_EXCEPTION", 0, 0, 0, 0)
        finally:
            sandbox.reset()

    # Generate Output Files
    os.makedirs("results", exist_ok=True)
    
    if os.path.exists("runs.db"):
        with sqlite3.connect("runs.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT instance_id, status, steps_taken, cost_usd FROM runs WHERE instance_id IN ({seq})".format(
                seq=','.join(['?']*len(tasks))), [t.instance_id for t in tasks])
            rows = cursor.fetchall()
            
            if rows:
                resolved_count = sum(1 for r in rows if r[1] == AgentStatus.SUCCESS.value)
                total_runs = len(rows)
                timeout_count = sum(1 for r in rows if r[1] == AgentStatus.TIMEOUT.value)
                model_error_count = sum(1 for r in rows if r[1] in [AgentStatus.MODEL_ERROR.value, "RATE_LIMITED", "FAILED_WITH_EXCEPTION"])
                
                resolved_steps = [r[2] for r in rows if r[1] == AgentStatus.SUCCESS.value]
                unresolved_steps = [r[2] for r in rows if r[1] != AgentStatus.SUCCESS.value]
                avg_steps_resolved = sum(resolved_steps) / len(resolved_steps) if resolved_steps else 0
                avg_steps_unresolved = sum(unresolved_steps) / len(unresolved_steps) if unresolved_steps else 0
                
                avg_cost = sum(r[3] for r in rows) / total_runs
                
                # Write summary markdown
                with open("results/eval_summary.md", "w") as f:
                    f.write("# Eval Set Run Summary\n\n")
                    f.write(f"- **Total Tasks Run**: {total_runs}\n")
                    f.write(f"- **Resolved Rate**: {resolved_count/total_runs*100:.1f}%\n")
                    f.write(f"- **Timeout Rate**: {timeout_count/total_runs*100:.1f}%\n")
                    f.write(f"- **Model/Infra Error Rate**: {model_error_count/total_runs*100:.1f}%\n")
                    f.write(f"- **Avg Steps (Resolved)**: {avg_steps_resolved:.2f}\n")
                    f.write(f"- **Avg Steps (Unresolved)**: {avg_steps_unresolved:.2f}\n")
                    f.write(f"- **Avg Cost per Task**: ${avg_cost:.4f}\n\n")
                    
                    f.write("## Task Results\n\n")
                    f.write("| Instance ID | Final Status |\n")
                    f.write("|-------------|--------------|\n")
                    for r in rows:
                        f.write(f"| {r[0]} | {r[1]} |\n")
                    
                # Write failure taxonomy template
                with open("results/failure_taxonomy_template.md", "w") as f:
                    f.write("# Failure Taxonomy\n\n")
                    f.write("| Instance ID | Category | Notes |\n")
                    f.write("|-------------|----------|-------|\n")
                    for r in rows:
                        instance_id = r[0]
                        status = r[1]
                        if status != AgentStatus.SUCCESS.value:
                            f.write(f"| {instance_id} | | |\n")
                
                print("\nGenerated results/eval_summary.md and results/failure_taxonomy_template.md")

if __name__ == "__main__":
    main()

