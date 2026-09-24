with open("src/sandbox.py", "r", encoding="utf-8") as f:
    content = f.read()

import re
# Replace the build context logic
old_logic = '''            import os
            with open("Dockerfile.tmp", "w") as df:
                df.write(dockerfile)
            self.client.images.build(path=".", dockerfile="Dockerfile.tmp", tag=tag, rm=True)
            os.remove("Dockerfile.tmp")'''

new_logic = '''            from io import BytesIO
            f = BytesIO(dockerfile.encode('utf-8'))
            self.client.images.build(fileobj=f, tag=tag, rm=True)'''

content = content.replace(old_logic, new_logic)

with open("src/sandbox.py", "w", encoding="utf-8") as f:
    f.write(content)
