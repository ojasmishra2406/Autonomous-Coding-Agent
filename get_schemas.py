import sqlite3
c = sqlite3.connect('runs.db').cursor()
c.execute("SELECT sql FROM sqlite_master WHERE type='table';")
for row in c.fetchall():
    print(row[0])
