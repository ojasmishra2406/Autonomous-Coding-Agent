with open("src/sandbox.py", "r", encoding="utf-8") as f:
    content = f.read()
    
content = content.replace('numpy<2.0.0', 'numpy==1.26.4')

with open("src/sandbox.py", "w", encoding="utf-8") as f:
    f.write(content)
