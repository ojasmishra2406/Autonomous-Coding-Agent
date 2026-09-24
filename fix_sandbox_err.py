with open("src/sandbox.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('raise RuntimeError(f"Clone failed: {output.decode()}")', 'raise RuntimeError(f"Clone failed (code {exit_code}): {output.decode()}")')

with open("src/sandbox.py", "w", encoding="utf-8") as f:
    f.write(content)
