with open("src/sandbox.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# We want to prepend PYTHONWARNINGS=ignore to the test_cmd string
# Currently: test_cmd = "pytest"
# We'll replace it with test_cmd = "PYTHONWARNINGS=ignore pytest"
# and we also need to handle the Django test_cmd cases.

old_test_cmd = '''            test_cmd = "pytest"
            if use_smart_tests:
                if self.exec("test -f tests/runtests.py", 10)[2] == 0:
                    test_cmd = "python tests/runtests.py --parallel=1 --settings=test_sqlite"
                elif self.exec("test -f runtests.py", 10)[2] == 0:
                    test_cmd = "python runtests.py --parallel=1 --settings=test_sqlite"'''

new_test_cmd = '''            test_cmd = "PYTHONWARNINGS=ignore pytest -c /dev/null"
            if use_smart_tests:
                if self.exec("test -f tests/runtests.py", 10)[2] == 0:
                    test_cmd = "PYTHONWARNINGS=ignore python tests/runtests.py --parallel=1 --settings=test_sqlite"
                elif self.exec("test -f runtests.py", 10)[2] == 0:
                    test_cmd = "PYTHONWARNINGS=ignore python runtests.py --parallel=1 --settings=test_sqlite"'''

content = content.replace(old_test_cmd, new_test_cmd)

# Actually, the user asked to patch run_tests to set PYTHONWARNINGS=ignore.
# Using -c /dev/null for pytest might be too aggressive (it might bypass needed pytest configs like django settings if pytest is used for django).
# Let's just prepend PYTHONWARNINGS=ignore, which satisfies the user request perfectly.
new_test_cmd_safe = '''            test_cmd = "PYTHONWARNINGS=ignore pytest"
            if use_smart_tests:
                if self.exec("test -f tests/runtests.py", 10)[2] == 0:
                    test_cmd = "PYTHONWARNINGS=ignore python tests/runtests.py --parallel=1 --settings=test_sqlite"
                elif self.exec("test -f runtests.py", 10)[2] == 0:
                    test_cmd = "PYTHONWARNINGS=ignore python runtests.py --parallel=1 --settings=test_sqlite"'''

content = content.replace(new_test_cmd, new_test_cmd_safe)

if old_test_cmd in content:
    content = content.replace(old_test_cmd, new_test_cmd_safe)
else:
    print("Could not find old_test_cmd to replace.")

with open("src/sandbox.py", "w", encoding="utf-8") as f:
    f.write(content)
