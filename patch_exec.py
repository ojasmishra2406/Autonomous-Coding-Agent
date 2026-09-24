with open("src/sandbox.py", "r", encoding="utf-8") as f:
    content = f.read()

# Instead of prepending it to test_cmd, we can just do env var before timeout or use bash -c
# Wait, exec() is defined as:
#         wrapped_cmd = f"timeout {timeout} {cmd}"
#         exit_code, output = self.container.exec_run(
#             ["bash", "-c", wrapped_cmd], 

old_exec = '''        wrapped_cmd = f"timeout {timeout} {cmd}"
        exit_code, output = self.container.exec_run(
            ["bash", "-c", wrapped_cmd],'''

new_exec = '''        wrapped_cmd = f"timeout {timeout} bash -c '{cmd.replace(\"'\", \"'\\''\")}'"
        exit_code, output = self.container.exec_run(
            ["bash", "-c", wrapped_cmd],'''

content = content.replace(old_exec, new_exec)

with open("src/sandbox.py", "w", encoding="utf-8") as f:
    f.write(content)
