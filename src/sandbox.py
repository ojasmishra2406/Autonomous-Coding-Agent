import docker
import os
import base64
from typing import Optional, List, Tuple
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)

@dataclass
class TestResult:
    passed: bool
    stderr: str
    output: str

class Sandbox:
    def __init__(self):
        self.client = docker.from_env(timeout=300)
        self.container = None
        self._prune_orphaned_containers()

    def _prune_orphaned_containers(self):
        try:
            containers = self.client.containers.list(all=True)
            for c in containers:
                if any('sandbox-' in t for t in c.image.tags):
                    c.remove(force=True)
        except Exception as e:
            pass

    def _build_image_if_missing(self, base_image: str):
        tag = f"sandbox-{base_image.replace(':', '-')}"
        try:
            self.client.images.get(tag)
        except docker.errors.ImageNotFound:
            print(f"Building {tag} image based on {base_image}. This may take a moment...")
            dockerfile = f"""FROM {base_image}
RUN if [ "{base_image}" = "python:3.7-slim" ]; then \
    sed -i s/deb.debian.org/archive.debian.org/g /etc/apt/sources.list && \
    sed -i 's|security.debian.org|archive.debian.org/|g' /etc/apt/sources.list && \
    sed -i '/stretch-updates/d' /etc/apt/sources.list && \
    sed -i '/buster-updates/d' /etc/apt/sources.list; fi
RUN apt-get update -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false && apt-get install -y git build-essential ripgrep && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
RUN pip install --upgrade pip pytest
"""
            import tempfile, os
            with tempfile.TemporaryDirectory() as tmpdir:
                with open(os.path.join(tmpdir, "Dockerfile"), "w") as df:
                    df.write(dockerfile)
                self.client.images.build(path=tmpdir, tag=tag, rm=True)
        return tag

    def start(self, repo_url: str, commit_sha: str, instance_id: str = None):
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
            tag,
            command="tail -f /dev/null",
            detach=True,
            mem_limit="2g",
            memswap_limit="2g",
            nano_cpus=2000000000,
            network_mode="bridge"
        )
        
        clone_cmd = f"git clone {repo_url} /workspace/repo"
        exit_code, output = self.container.exec_run(clone_cmd)
        if exit_code != 0:
            raise RuntimeError(f"Clone failed (code {exit_code}): {output.decode()}")
            
        checkout_cmd = f"git -C /workspace/repo checkout {commit_sha}"
        exit_code, output = self.container.exec_run(checkout_cmd)
        if exit_code != 0:
            raise RuntimeError(f"Checkout failed: {output.decode()}")
            
        # Cheap dependency hack for specific testing
        dep_hacks = []
        if instance_id and "astropy" in instance_id:
            dep_hacks.append("pip install \"numpy<2.0.0\" pytest-astropy hypothesis")
        if instance_id and "django" in instance_id:
            dep_hacks.append("pip install asgiref sqlparse")
            
        for hack in dep_hacks:
            self.container.exec_run(f"bash -c 'cd /workspace/repo && {hack}'")
            
        setup_cmd = "bash -c 'if [ -f /workspace/repo/setup.py ] || [ -f /workspace/repo/pyproject.toml ]; then pip install -e /workspace/repo; fi'"
        self.container.exec_run(setup_cmd)
        
    def exec(self, cmd: str, timeout: int) -> Tuple[str, str, int]:
        if not self.container:
            raise RuntimeError("Sandbox container is not running.")
            
        safe_cmd = cmd.replace("'", "'\\''")
        wrapped_cmd = f"timeout {timeout} bash -c '{safe_cmd}'"
        exit_code, output = self.container.exec_run(
            ["bash", "-c", wrapped_cmd], 
            demux=True,
            workdir="/workspace/repo"
        )
        
        stdout = (output[0] or b"").decode("utf-8") if output else ""
        stderr = (output[1] or b"").decode("utf-8") if output else ""
        
        if exit_code == 124:
            stderr += "\n[Sandbox] Command timed out."
            
        return stdout, stderr, exit_code
        
    def apply_patch(self, diff: str) -> bool:
        if not self.container:
            raise RuntimeError("Sandbox container is not running.")
            
        diff_b64 = base64.b64encode(diff.encode("utf-8")).decode("utf-8")
        cmd = f"echo {diff_b64} | base64 -d > /workspace/repo/patch.diff && git -C /workspace/repo apply patch.diff"
        stdout, stderr, exit_code = self.exec(cmd, timeout=30)
        return exit_code == 0

    def run_tests(self, test_ids: Optional[List[str]], timeout: int = 120) -> TestResult:
        if not self.container:
            raise RuntimeError("Sandbox container is not running.")
            
        self.container.reload()
        networks = list(self.container.attrs['NetworkSettings']['Networks'].keys())
        for net_name in networks:
            network = self.client.networks.get(net_name)
            network.disconnect(self.container)
            
        try:
            use_smart_tests = os.environ.get("FEATURE_SMART_TESTS", "0") == "1"
            
            test_cmd = "PYTHONWARNINGS=ignore pytest"
            if use_smart_tests:
                if self.exec("test -f tests/runtests.py", 10)[2] == 0:
                    test_cmd = "PYTHONWARNINGS=ignore python tests/runtests.py --parallel=1 --settings=test_sqlite"
                elif self.exec("test -f runtests.py", 10)[2] == 0:
                    test_cmd = "PYTHONWARNINGS=ignore python runtests.py --parallel=1 --settings=test_sqlite"
                    
            if test_ids:
                test_cmd += " " + " ".join(test_ids)
                
            stdout, stderr, exit_code = self.exec(test_cmd, timeout=120)
            
            harness_crashed = False
            if exit_code != 0:
                combined_out = stdout + "\n" + stderr
                if not any(x in combined_out for x in ["AssertionError", "FAILED (", "FAIL:", "ERROR:"]):
                    harness_crashed = True
                    stderr = "[TEST HARNESS CRASH DETECTED. THE TESTS DID NOT RUN PROPERLY.]\n" + stderr

            return TestResult(passed=(exit_code == 0), stderr=stderr, output=stdout)
        finally:
            try:
                bridge = self.client.networks.get("bridge")
                bridge.connect(self.container)
            except Exception:
                pass

    def reset(self):
        if self.container:
            try:
                self.container.stop(timeout=1)
                self.container.remove(force=True)
            except Exception:
                pass
            self.container = None
