
import sqlite3
import json
from src.tracing import Tracer, calculate_cost
import os

trace_line = open("traces/token_check_task.jsonl").readlines()[-1]
trace_json = json.loads(trace_line)
i_tok = trace_json['model_input_tokens']
o_tok = trace_json['model_output_tokens']
t_tok = trace_json['thoughts_token_count']

t = Tracer("cost_test_task_real")
t.record_run("SUCCESS", 2, i_tok, o_tok, t_tok)

c = sqlite3.connect("runs.db")
cost = c.execute("SELECT cost_usd FROM runs WHERE instance_id='cost_test_task_real'").fetchone()[0]
expected_cost = calculate_cost(i_tok, o_tok, t_tok)
print(f"Calculated cost from function: {expected_cost}")
print(f"Logged cost_usd in DB: {cost}")
