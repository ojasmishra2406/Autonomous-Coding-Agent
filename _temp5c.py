
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
