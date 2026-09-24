import re

with open("src/sandbox.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update _build_image_if_missing
old_build = '''    def _build_image_if_missing(self):
        try:
            self.client.images.get("sandbox-base")
        except docker.errors.ImageNotFound:
            print("Building sandbox-base image. This may take a moment...")
            self.client.images.build(path=".", tag="sandbox-base", rm=True)'''

new_build = '''    def _build_image_if_missing(self, base_image: str):
        tag = f"sandbox-{base_image.replace(':', '-')}"
        try:
            self.client.images.get(tag)
        except docker.errors.ImageNotFound:
            print(f"Building {tag} image based on {base_image}. This may take a moment...")
            dockerfile = f\"\"\"FROM {base_image}
RUN apt-get update && apt-get install -y git build-essential ripgrep && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
RUN pip install --upgrade pip pytest
\"\"\"
            import os
            with open("Dockerfile.tmp", "w") as df:
                df.write(dockerfile)
            self.client.images.build(path=".", dockerfile="Dockerfile.tmp", tag=tag, rm=True)
            os.remove("Dockerfile.tmp")
        return tag'''
        
content = content.replace(old_build, new_build)

# 2. Update start()
old_start = '''    def start(self, repo_url: str, commit_sha: str, instance_id: str = None):
        self.reset()
        self._build_image_if_missing()
        
        self.container = self.client.containers.run(
            "sandbox-base",'''

new_start = '''    def start(self, repo_url: str, commit_sha: str, instance_id: str = None):
        self.reset()
        base_image = "python:3.11-slim"
        if instance_id:
            num = int(instance_id.split("-")[-1])
            if "astropy" in instance_id:
                if num < 10000: base_image = "python:3.7-slim"
                elif num < 14000: base_image = "python:3.9-slim"
            elif "django" in instance_id:
                if num < 13000: base_image = "python:3.7-slim"
                elif num < 16000: base_image = "python:3.9-slim"
            elif "matplotlib" in instance_id:
                if num < 23000: base_image = "python:3.7-slim"
                elif num < 25000: base_image = "python:3.9-slim"
                
        tag = self._build_image_if_missing(base_image)
        
        self.container = self.client.containers.run(
            tag,'''

content = content.replace(old_start, new_start)

# 3. Fix prune logic
content = content.replace("if 'sandbox-base' in str(c.image.tags):", "if any('sandbox-' in t for t in c.image.tags):")

with open("src/sandbox.py", "w", encoding="utf-8") as f:
    f.write(content)
