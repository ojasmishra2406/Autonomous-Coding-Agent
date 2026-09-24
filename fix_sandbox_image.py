with open("src/sandbox.py", "r", encoding="utf-8") as f:
    content = f.read()

get_image_update = '''
    def _get_image_name(self, instance_id: str) -> str:
        clean_id = instance_id.lower()
        if "astropy" in clean_id:
            return f"swebench/sweb.eval.x86_64.astropy_1776_{clean_id}:latest".replace("__", "_1776_")
        if "django" in clean_id:
            return f"swebench/sweb.eval.x86_64.django_1776_{clean_id}:latest".replace("__", "_1776_")
        # Fallback generic logic based on SWE-bench hub naming
        repo = clean_id.split("__")[0] if "__" in clean_id else clean_id
        return f"swebench/sweb.eval.x86_64.{repo}_1776_{clean_id}:latest"
'''
# Using regex to replace the old _get_image_name
import re
content = re.sub(
    r'    def _get_image_name\(self, instance_id: str\) -> str:.*?return f"swebench/sweb\.eval\.x86_64\.{clean_id}:latest"',
    get_image_update.strip("\n"),
    content,
    flags=re.DOTALL
)

with open("src/sandbox.py", "w", encoding="utf-8") as f:
    f.write(content)
