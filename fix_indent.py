with open("src/agent.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "with open(os.path.join(\"src\", \"prompts\", \"system.txt\")" in line:
        line = "        with open(os.path.join(\"src\", \"prompts\", \"system.txt\"), \"r\", encoding=\"utf-8\") as f:\n"
    elif "system_prompt = f.read()" in line:
        line = "            system_prompt = f.read()\n"
    elif "system_prompt +=" in line:
        line = "            system_prompt += \"\\n\\nOPERATIONAL INVARIANTS:\\n1. ALWAYS use the provided tools to explore, read, search, edit, and test files.\\n2. NEVER apologize, output conversational chit-chat, or claim 'I am an AI and cannot use tools'.\\n3. If a test crashes, dependencies fail, or a tool throws an error, DO NOT give up. Analyze stderr, inspect the repository structure, read the code, and apply a fix.\\n4. When finished, ensure all modified files are clean, your targeted tests pass, and call apply_patch or verify changes before concluding.\\n5. All code modifications MUST be precise and targeted.\"\n"
    new_lines.append(line)

with open("src/agent.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
