with open("src/sandbox.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

old_dockerfile = '''            dockerfile = f\"\"\"FROM {base_image}
RUN apt-get update && apt-get install -y git build-essential ripgrep && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
RUN pip install --upgrade pip pytest
\"\"\"'''

new_dockerfile = '''            dockerfile = f\"\"\"FROM {base_image}
RUN if [ "{base_image}" = "python:3.7-slim" ]; then \\
    sed -i s/deb.debian.org/archive.debian.org/g /etc/apt/sources.list && \\
    sed -i 's|security.debian.org|archive.debian.org/|g' /etc/apt/sources.list && \\
    sed -i '/stretch-updates/d' /etc/apt/sources.list && \\
    sed -i '/buster-updates/d' /etc/apt/sources.list; fi
RUN apt-get update -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false && apt-get install -y git build-essential ripgrep && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
RUN pip install --upgrade pip pytest
\"\"\"'''

content = content.replace(old_dockerfile, new_dockerfile)

with open("src/sandbox.py", "w", encoding="utf-8") as f:
    f.write(content)
