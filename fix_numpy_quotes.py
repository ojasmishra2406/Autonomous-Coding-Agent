with open("src/sandbox.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('pip install numpy<2.0.0', 'pip install \"numpy<2.0.0\"')

with open("src/sandbox.py", "w", encoding="utf-8") as f:
    f.write(content)
