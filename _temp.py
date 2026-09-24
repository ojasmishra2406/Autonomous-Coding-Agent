
import os
import json
from dotenv import load_dotenv
load_dotenv()
from google import genai
import time
from src.tracing import Tracer, calculate_cost

client = genai.Client()
t = Tracer('task6c_fresh')
for i in range(5):
    try:
        response = client.models.generate_content(model='gemini-3.7-flash', contents='Count from 1 to 5')
        break
    except Exception as e:
        print(f'Attempt failed: {e}')
        if i == 4: raise
        time.sleep(10)

p_tok = response.usage_metadata.prompt_token_count
c_tok = response.usage_metadata.candidates_token_count
t_tok = getattr(response.usage_metadata, 'thoughts_token_count', 0)
tot_tok = response.usage_metadata.total_token_count

print('=== 6c. Cross-check tokens (FRESH) ===')
print(f'API prompt_tokens: {p_tok}')
print(f'API candidates_tokens: {c_tok}')
print(f'API thoughts_tokens: {t_tok}')
print(f'API total_tokens: {tot_tok}')

t.log_step(1, 'none', 'n/a', p_tok, c_tok, 100, thoughts_token_count=t_tok or 0)
trace_line = open('traces/task6c_fresh.jsonl').readlines()[-1]
trace_json = json.loads(trace_line)
print(f"Traced model_input_tokens: {trace_json['model_input_tokens']}")
print(f"Traced model_output_tokens: {trace_json['model_output_tokens']}")
print(f"Traced thoughts_token_count: {trace_json['thoughts_token_count']}")

print('\\n=== 6d. Actual arithmetic for cost_usd (FRESH) ===')
import sqlite3
t.record_run('SUCCESS', 2, p_tok, c_tok, t_tok or 0)
c = sqlite3.connect('runs.db')
cost = c.execute("SELECT cost_usd FROM runs WHERE instance_id='task6c_fresh'").fetchone()[0]
expected = calculate_cost(p_tok, c_tok, t_tok or 0)
print(f'Calculated cost from function: {expected}')
print(f'Logged cost_usd in DB: {cost}')

print("=== 5c. Raw response object structure ===")
time.sleep(5)
cmd5c = """
import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types
import time

client = genai.Client()
schema = {
    "name": "list_files",
    "description": "List files in a directory",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {"type": "STRING"}
        },
        "required": ["path"]
    }
}
func = types.FunctionDeclaration(**schema)
tool = types.Tool(function_declarations=[func])
config = types.GenerateContentConfig(tools=[tool], temperature=0.0)

for i in range(5):
    try:
        response = client.models.generate_content(model='gemini-3.7-flash', contents='List the files in the current directory.', config=config)
        break
    except Exception as e:
        print(f"Attempt failed: {e}")
        if i == 4: raise
        time.sleep(10)
print(response)
"""
with open("_temp5c.py", "w") as f: f.write(cmd5c)
print(run_cmd("uv run python _temp5c.py"))

print("=== 6c. Cross-check tokens ===")
time.sleep(5)
cmd6c = """
import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
import json
from src.tracing import Tracer
import time

client = genai.Client()
for i in range(5):
    try:
        response = client.models.generate_content(model='gemini-3.7-flash', contents='Count from 1 to 5')
        break
    except Exception as e:
        print(f"Attempt failed: {e}")
        if i == 4: raise
        time.sleep(10)

print(f"API usage_metadata prompt_tokens: {response.usage_metadata.prompt_token_count}")
print(f"API usage_metadata candidates_tokens: {response.usage_metadata.candidates_token_count}")
thoughts = getattr(response.usage_metadata, 'thoughts_token_count', 0)
print(f"API usage_metadata thoughts_tokens: {thoughts}")
print(f"API usage_metadata total_tokens: {response.usage_metadata.total_token_count}")
print(f"Sum matches total: {response.usage_metadata.prompt_token_count + response.usage_metadata.candidates_token_count + (thoughts or 0) == response.usage_metadata.total_token_count}")

t = Tracer("token_check_task")
t.log_step(1, "none", "n/a", response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count, 100, thoughts_token_count=thoughts or 0)

trace_line = open("traces/token_check_task.jsonl").readlines()[-1]
trace_json = json.loads(trace_line)
print(f"Traced model_input_tokens: {trace_json['model_input_tokens']}")
print(f"Traced model_output_tokens: {trace_json['model_output_tokens']}")
print(f"Traced thoughts_token_count: {trace_json['thoughts_token_count']}")
"""
with open("_temp6c.py", "w") as f: f.write(cmd6c)
print(run_cmd("uv run python _temp6c.py"))

print("=== 6d. Actual arithmetic for cost_usd ===")
cmd6d = """
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
"""
with open("_temp6d.py", "w") as f: f.write(cmd6d)
print(run_cmd("uv run python _temp6d.py"))




