import pytest
from src.sandbox import Sandbox

@pytest.fixture
def sandbox():
    sb = Sandbox()
    yield sb
    sb.reset()

def test_sandbox_smoke(sandbox):
    """
    Smoke test that clones pallets/flask at a pinned commit and confirms
    pytest runs successfully inside the sandbox.
    """
    repo_url = "https://github.com/pallets/flask.git"
    commit_sha = "d73fa1cdcbd8b1465c151db8924ba58b1dd14e35" # Flask main branch (pytest 8 compatible)
    
    sandbox.start(repo_url, commit_sha)
    
    # Run a specific test file to keep the smoke test fast
    result = sandbox.run_tests(["tests/test_appctx.py"])
    
    if not result.passed:
        print("TEST STDOUT:", result.output)
        print("TEST STDERR:", result.stderr)
    assert result.passed is True

def test_sandbox_exec(sandbox):
    repo_url = "https://github.com/pallets/flask.git"
    commit_sha = "0c0443fe2ccfade93e6e026e625ccab282e17928"
    sandbox.start(repo_url, commit_sha)
    
    stdout, stderr, exit_code = sandbox.exec("echo 'hello'", timeout=5)
    assert exit_code == 0
    assert "hello" in stdout.strip()

def test_sandbox_apply_patch(sandbox):
    repo_url = "https://github.com/pallets/flask.git"
    commit_sha = "0c0443fe2ccfade93e6e026e625ccab282e17928"
    sandbox.start(repo_url, commit_sha)
    
    # Create a dummy tracked file
    sandbox.exec("echo 'test' > /workspace/repo/dummy.txt", timeout=5)
    sandbox.exec("git add dummy.txt", timeout=5)
    
    patch = """diff --git a/dummy.txt b/dummy.txt
--- a/dummy.txt
+++ b/dummy.txt
@@ -1 +1 @@
-test
+patched
"""
    success = sandbox.apply_patch(patch)
    assert success is True
    
    stdout, stderr, exit_code = sandbox.exec("cat /workspace/repo/dummy.txt", timeout=5)
    assert "patched" in stdout.strip()
