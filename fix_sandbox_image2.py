with open("src/sandbox.py", "r", encoding="utf-8") as f:
    content = f.read()

get_image_update = '''
    def _get_image_name(self, instance_id: str) -> str:
        clean_id = instance_id.lower().replace("__", "_1776_")
        return f"swebench/sweb.eval.x86_64.{clean_id}:latest"
'''
import re
content = re.sub(
    r'    def _get_image_name\(self, instance_id: str\) -> str:.*?return f"swebench/sweb\.eval\.x86_64\.\{repo\}_1776_\{clean_id\}:latest"',
    get_image_update.strip("\n"),
    content,
    flags=re.DOTALL
)

with open("src/sandbox.py", "w", encoding="utf-8") as f:
    f.write(content)
