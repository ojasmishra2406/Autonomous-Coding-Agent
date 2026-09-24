import re
with open('src/agent.py', 'r', encoding='utf-8') as f:
    content = f.read()
content = re.sub(r'            if name in \[\"apply_patch\", \"replace_file_content\"\]:.*?result_data = \{\"tool_output\": result_data, \"test_result\": test_result\}', '', content, flags=re.DOTALL)
with open('src/agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
