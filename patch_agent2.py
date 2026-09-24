import re

with open("src/agent.py", "r", encoding="utf-8") as f:
    content = f.read()

sanitize_func = '''
def sanitize_message_history(history):
    if not history: return []
    sanitized = []
    i = 0
    while i < len(history):
        msg = history[i]
        role = msg.get("role")
        if role == "assistant" and msg.get("tool_calls"):
            sanitized.append(msg)
            expected_ids = {tc["id"] for tc in msg["tool_calls"] if "id" in tc}
            i += 1
            while i < len(history) and history[i].get("role") == "tool":
                tool_msg = history[i]
                expected_ids.discard(tool_msg.get("tool_call_id"))
                sanitized.append(tool_msg)
                i += 1
            for orphan_id in expected_ids:
                sanitized.append({
                    "role": "tool",
                    "tool_call_id": orphan_id,
                    "content": "Error: Tool execution was interrupted."
                })
            continue
        if sanitized and role == "user" and sanitized[-1].get("role") == "user":
            sanitized[-1]["content"] = f"{sanitized[-1].get('content', '')}\\n\\n{msg.get('content', '')}"
        else:
            sanitized.append(msg)
        i += 1
    return sanitized
'''

# Insert sanitize_message_history after imports
content = content.replace("class Agent:", sanitize_func + "\nclass Agent:")

# Add history = sanitize_message_history(history) inside the loop
content = content.replace("for step in range(max_steps):", "for step in range(max_steps):\n            history = sanitize_message_history(history)")

# Add anti-apology guardrails
guardrail = '''
            if not tool_calls:
                if not response.text or "apologize" in response.text.lower() or "as an ai" in response.text.lower():
                    history.append({"role": "assistant", "content": response.text or ""})
                    history.append({"role": "user", "content": "Notice: Apologies or blank messages are prohibited. You must use tools to solve the issue."})
                    continue
'''
# Find the part where it handles empty responses
empty_resp = '''if not response.function_calls and not response.text:
                consecutive_errors += 1
                transcript.append({"step": step, "role": "system", "content": "API Error: Empty response returned."})
                if consecutive_errors >= 3:
                    tracer.record_run(AgentStatus.MODEL_ERROR.value, step+1, total_in, total_out, total_thoughts)
                    return AgentResult(status=AgentStatus.MODEL_ERROR, steps_taken=step+1, total_input_tokens=total_in, total_output_tokens=total_out, final_patch=get_final_patch(), transcript=transcript)
                history.append({"role": "user", "content": "Empty response. Please call a tool."})
                continue'''

content = content.replace(empty_resp, guardrail)

# Also update the system prompt
sys_update = '''
          with open(os.path.join("src", "prompts", "system.txt"), "r", encoding="utf-8") as f:
              system_prompt = f.read()
              system_prompt += "\\n\\nOPERATIONAL INVARIANTS:\\n1. ALWAYS use the provided tools to explore, read, search, edit, and test files.\\n2. NEVER apologize, output conversational chit-chat, or claim 'I am an AI and cannot use tools'.\\n3. If a test crashes, dependencies fail, or a tool throws an error, DO NOT give up. Analyze stderr, inspect the repository structure, read the code, and apply a fix.\\n4. When finished, ensure all modified files are clean, your targeted tests pass, and call apply_patch or verify changes before concluding.\\n5. All code modifications MUST be precise and targeted."
'''
content = content.replace('with open(os.path.join("src", "prompts", "system.txt"), "r", encoding="utf-8") as f:\n            system_prompt = f.read()', sys_update)

with open("src/agent.py", "w", encoding="utf-8") as f:
    f.write(content)
