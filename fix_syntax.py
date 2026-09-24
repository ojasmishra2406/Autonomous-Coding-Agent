with open("src/sandbox.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('dep_hacks.append("pip install "numpy<2.0.0" pytest-astropy hypothesis")', 'dep_hacks.append("pip install \\"numpy<2.0.0\\" pytest-astropy hypothesis")')

with open("src/sandbox.py", "w", encoding="utf-8") as f:
    f.write(content)
