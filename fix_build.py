with open("src/sandbox.py", "r", encoding="utf-8") as f:
    content = f.read()

old_logic = '''            from io import BytesIO
            f = BytesIO(dockerfile.encode('utf-8'))
            self.client.images.build(fileobj=f, tag=tag, rm=True)'''

new_logic = '''            import tempfile, os
            with tempfile.TemporaryDirectory() as tmpdir:
                with open(os.path.join(tmpdir, "Dockerfile"), "w") as df:
                    df.write(dockerfile)
                self.client.images.build(path=tmpdir, tag=tag, rm=True)'''

content = content.replace(old_logic, new_logic)

with open("src/sandbox.py", "w", encoding="utf-8") as f:
    f.write(content)
