from src.sandbox import Sandbox
sb = Sandbox()
sb.start('https://github.com/pallets/flask.git', 'd73fa1cdcbd8b1465c151db8924ba58b1dd14e35')

print("--- Memory Limit Check ---")
stdout, stderr, exit_code = sb.exec("python -c 'bytearray(3*1024**3)'", timeout=10)
print(f'Exit code: {exit_code}')
print(f'Stderr: {stderr}')

print("--- Network Check ---")
# Disable network first like run_tests does
sb.container.reload()
networks = list(sb.container.attrs['NetworkSettings']['Networks'].keys())
for net_name in networks:
    network = sb.client.networks.get(net_name)
    network.disconnect(sb.container)

stdout, stderr, exit_code = sb.exec("python -c \"import urllib.request; urllib.request.urlopen('https://example.com', timeout=5)\"", timeout=10)
print(f'Exit code: {exit_code}')
print(f'Stderr: {stderr}')

sb.reset()
