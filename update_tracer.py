import re

with open("src/tracing.py", "r", encoding="utf-8") as f:
    content = f.read()

old_func = '''    def record_run(self, status: str, steps_taken: int, total_input_tokens: int, total_output_tokens: int, total_thoughts_tokens: int = 0):
        """Save the summary of the task to the SQLite database."""
        end_time = datetime.now()
        wall_clock_seconds = (end_time - self.start_time).total_seconds()
        total_tokens = total_input_tokens + total_output_tokens + total_thoughts_tokens
        timestamp = end_time.isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(\'\'\'
                INSERT OR REPLACE INTO runs 
                (instance_id, status, steps_taken, total_tokens, cost_usd, wall_clock_seconds, timestamp, thoughts_tokens) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            \'\'\', (self.instance_id, status, steps_taken, total_tokens, self.total_cost, wall_clock_seconds, timestamp, total_thoughts_tokens))
            conn.commit()'''

new_func = '''    def record_run(self, status: str, steps_taken: int, total_input_tokens: int, total_output_tokens: int, total_thoughts_tokens: int = 0, provider: str = "unknown"):
        """Save the summary of the task to the SQLite database."""
        end_time = datetime.now()
        wall_clock_seconds = (end_time - self.start_time).total_seconds()
        total_tokens = total_input_tokens + total_output_tokens + total_thoughts_tokens
        timestamp = end_time.isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(\'\'\'
                INSERT OR REPLACE INTO runs 
                (instance_id, status, steps_taken, total_tokens, cost_usd, wall_clock_seconds, timestamp, thoughts_tokens, provider) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            \'\'\', (self.instance_id, status, steps_taken, total_tokens, self.total_cost, wall_clock_seconds, timestamp, total_thoughts_tokens, provider))
            conn.commit()'''

content = content.replace(old_func, new_func)

with open("src/tracing.py", "w", encoding="utf-8") as f:
    f.write(content)
