import sqlite3
import datetime

conn = sqlite3.connect('runs.db')
c = conn.cursor()

# 1. Add provider column if it doesn't exist
try:
    c.execute("ALTER TABLE runs ADD COLUMN provider TEXT")
except sqlite3.OperationalError as e:
    if "duplicate column name" not in str(e).lower():
        pass

# 2. Create runs_archive table
c.execute('''
    CREATE TABLE IF NOT EXISTS runs_archive (
        archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_batch_id TEXT,
        archived_at TEXT,
        instance_id TEXT,
        status TEXT,
        steps_taken INTEGER,
        total_tokens INTEGER,
        cost_usd REAL,
        wall_clock_seconds REAL,
        timestamp TEXT,
        thoughts_tokens INTEGER,
        provider TEXT
    )
''')
conn.commit()
conn.close()
