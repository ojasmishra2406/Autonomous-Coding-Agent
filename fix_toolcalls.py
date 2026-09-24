with open("src/agent.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("total_thoughts += response.thoughts_tokens\n            \n            \n            if not tool_calls:", "total_thoughts += response.thoughts_tokens\n            \n            tool_calls = response.function_calls\n            if not tool_calls:")

with open("src/agent.py", "w", encoding="utf-8") as f:
    f.write(content)
