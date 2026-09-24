import re
with open('src/test_selector.py', 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('self.sandbox.exec(f"test -f /workspace/repo/{shlex.quote(p)}")', 'self.sandbox.exec(f"test -f /workspace/repo/{shlex.quote(p)}", timeout=10)')
content = content.replace('self.sandbox.exec(cmd)', 'self.sandbox.exec(cmd, timeout=30)')
content = content.replace('self.sandbox.exec(grep_cmd)', 'self.sandbox.exec(grep_cmd, timeout=30)')
with open('src/test_selector.py', 'w', encoding='utf-8') as f:
    f.write(content)
