import sqlite3, os
if os.path.exists('runs.db'):
 c=sqlite3.connect('runs.db').cursor()
 c.execute('SELECT COUNT(*) FROM runs')
 print(c.fetchone()[0])
else:
 print('0')
