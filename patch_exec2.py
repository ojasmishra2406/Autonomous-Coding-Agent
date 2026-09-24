with open("src/sandbox.py", "r", encoding="utf-8") as f:
    content = f.read()

bad_line = '''        wrapped_cmd = f"timeout {timeout} bash -c '{cmd.replace(\"'\", \"'\\''\")}'"'''
good_line = '''        safe_cmd = cmd.replace("'", "'\\\\''")\n        wrapped_cmd = f"timeout {timeout} bash -c '{safe_cmd}'"'''

content = content.replace(bad_line, good_line)

with open("src/sandbox.py", "w", encoding="utf-8") as f:
    f.write(content)
