
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
