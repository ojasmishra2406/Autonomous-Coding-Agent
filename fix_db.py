import re

for file in ["scripts/run_dev.py", "scripts/run_eval.py"]:
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the block where it does resetting runs.db
    reset_pattern = r'print\("Resetting runs\.db\.\.\."\)\s+try:\s+import sqlite3\s+with sqlite3\.connect\("runs\.db"\) as conn:\s+conn\.execute\("DELETE FROM runs;"\)\s+conn\.commit\(\)\s+except Exception as e:\s+pass'
    
    new_reset_code = '''
    if getattr(args, "fresh", False):
        print("Resetting runs.db as requested (--fresh)...")
        try:
            import sqlite3
            with sqlite3.connect("runs.db") as conn:
                conn.execute("DELETE FROM runs;")
                conn.commit()
        except Exception as e:
            pass
    '''
    
    content = re.sub(reset_pattern, new_reset_code, content)
    
    # Also need to add --fresh argument
    arg_add_pattern = r'parser\.add_argument\("--max-tasks"'
    new_arg_code = 'parser.add_argument("--fresh", action="store_true", help="Clear runs.db before starting")\n    parser.add_argument("--max-tasks"'
    content = re.sub(arg_add_pattern, new_arg_code, content)

    with open(file, "w", encoding="utf-8") as f:
        f.write(content)
