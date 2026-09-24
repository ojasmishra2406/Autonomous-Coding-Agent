import docker
client = docker.from_env()
container = client.containers.run("python:3.7-slim", command="tail -f /dev/null", detach=True, tty=True)
cmd = "PYTHONWARNINGS=ignore python -c 'import sys; print(\"OK\")'"
wrapped_cmd = f"timeout 10 bash -c '{cmd.replace(\"'\", \"'\\''\")}'"
print(wrapped_cmd)
exit_code, output = container.exec_run(["bash", "-c", wrapped_cmd], demux=True)
print(f"exit_code: {exit_code}")
print(f"output: {output}")
container.kill()
container.remove()
