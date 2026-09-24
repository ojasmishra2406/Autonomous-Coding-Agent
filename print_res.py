import sqlite3
with sqlite3.connect('runs.db') as conn:
    cursor = conn.cursor()
    cursor.execute('SELECT instance_id, status FROM runs')
    rows = cursor.fetchall()

print("| Instance ID | Final Status |")
print("|-------------|--------------|")
for r in rows:
    print(f"| {r[0]} | {r[1]} |")
