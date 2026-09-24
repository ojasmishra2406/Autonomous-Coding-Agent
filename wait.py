import sqlite3, os, time
while True:
    try:
        c = sqlite3.connect('runs.db').cursor()
        c.execute('SELECT COUNT(*) FROM runs')
        count = c.fetchone()[0]
        if count >= 5:
            print('DONE', count)
            break
    except:
        pass
    time.sleep(10)
