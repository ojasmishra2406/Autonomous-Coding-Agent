import sqlite3
c=sqlite3.connect('runs.db').cursor()
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='runs';")
print(c.fetchone()[0])
