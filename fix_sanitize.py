with open("src/agent.py", "r", encoding="utf-8") as f:
    content = f.read()

sanitize_code = '''
def sanitize_message_history(history):
    \"\"\"
    Ensures message history complies with Groq API constraints:
    - Orphaned tool_calls must be paired with a synthetic tool response.
    - Role interleaving must be strictly alternating (user/assistant) or correctly chained.
    \"\"\"
    sanitized = []
    for i, msg in enumerate(history):
        sanitized.append(msg)
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            # Check if next message is a tool response
            if i + 1 < len(history) and history[i+1].get("role") == "tool":
                continue
            else:
                # Insert synthetic dummy tool response
                dummy_response = {
                    "role": "tool",
                    "content": "{\"error\": \"Tool call interrupted or system state reset.\"}",
                    "name": msg["tool_calls"][0]["function"]["name"],
                    "tool_call_id": msg["tool_calls"][0]["id"]
                }
                sanitized.append(dummy_response)
    return sanitized

class CodingAgent:
'''

content = content.replace("class CodingAgent:", sanitize_code)

with open("src/agent.py", "w", encoding="utf-8") as f:
    f.write(content)
