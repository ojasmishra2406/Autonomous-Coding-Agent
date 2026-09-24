import re

for file in ["scripts/run_dev.py", "scripts/run_eval.py"]:
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()
        
    archive_logic = '''
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
    '''

    # Find the --fresh block I added earlier and replace it with this archive logic
    fresh_pattern = r'if getattr\(args, "fresh", False\):\s+print\("Resetting runs\.db as requested \(--fresh\)\.\.\."\)\s+try:\s+import sqlite3\s+with sqlite3\.connect\("runs\.db"\) as conn:\s+conn\.execute\("DELETE FROM runs;"\)\s+conn\.commit\(\)\s+except Exception as e:\s+pass'
    
    content = re.sub(fresh_pattern, archive_logic.strip(), content)
    
    with open(file, "w", encoding="utf-8") as f:
        f.write(content)
