import sqlite3
c = sqlite3.connect('runs.db')
print(c.execute('SELECT status, COUNT(*) FROM runs GROUP BY status').fetchall())
row = c.execute('SELECT * FROM runs WHERE instance_id="mock_task_1"').fetchone()
print(f"instance_id: {row[0]}, status: {row[1]}, steps: {row[2]}, tokens: {row[3]}, cost: {row[4]}, time: {row[5]}, timestamp: {row[6]}")
