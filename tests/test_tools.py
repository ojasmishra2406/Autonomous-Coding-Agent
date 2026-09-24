import pytest
import json
import os
from src.sandbox import Sandbox
from src.tools import AgentTools

@pytest.fixture(scope="module")
def tools_sandbox():
    sb = Sandbox()
    repo_url = "https://github.com/pallets/flask.git"
    commit_sha = "d73fa1cdcbd8b1465c151db8924ba58b1dd14e35" # Flask main branch (pytest 8 compatible)
    sb.start(repo_url, commit_sha)
    tools = AgentTools(sb)
    yield tools
    sb.reset()

def test_list_files_valid(tools_sandbox):
    files = tools_sandbox.list_files(".")
    assert isinstance(files, list)
    assert len(files) > 0
    assert any("src/flask/app.py" in f for f in files)

def test_list_files_malformed(tools_sandbox):
    # Malformed/non-existent path
    files = tools_sandbox.list_files("/nonexistent/path/that/does/not/exist")
    # git ls-files on a bad path will still exit 0 but return empty, OR if we specify a path outside repo it exits with error
    assert isinstance(files, list)
    if len(files) > 0:
        assert "Error" in files[0] or len(files) == 0
    else:
        assert len(files) == 0

def test_read_file_valid(tools_sandbox):
    content = tools_sandbox.read_file("src/flask/app.py", start_line=1, end_line=5)
    assert "   1 | " in content
    lines = content.splitlines()
    assert len(lines) == 5

def test_read_file_malformed(tools_sandbox):
    # Non-existent file
    content = tools_sandbox.read_file("src/flask/nonexistent_file.py")
    assert "Error reading file:" in content

def test_search_code_valid(tools_sandbox):
    results = tools_sandbox.search_code("class Flask", "src/flask/app.py")
    assert isinstance(results, list)
    assert len(results) > 0
    assert "file" in results[0]
    assert "line" in results[0]
    assert "match_text" in results[0]

def test_search_code_malformed(tools_sandbox):
    # Malformed regex query (unmatched bracket)
    results = tools_sandbox.search_code("class [unmatched", "src/flask/app.py")
    assert len(results) > 0
    assert "error" in results[0]
    assert "Search failed:" in results[0]["error"]

def test_apply_patch_valid(tools_sandbox):
    # Valid patch
    # First create a file
    tools_sandbox.sandbox.exec("echo 'hello' > /workspace/repo/test_patch.txt", timeout=5)
    tools_sandbox.sandbox.exec("git add test_patch.txt", timeout=5)
    
    diff = """--- a/test_patch.txt
+++ b/test_patch.txt
@@ -1 +1 @@
-hello
+world
"""
    result = tools_sandbox.apply_patch(diff)
    assert result["success"] is True

def test_apply_patch_malformed(tools_sandbox):
    # Malformed patch (garbage text, no headers)
    diff = "This is not a valid diff.\nJust some text."
    result = tools_sandbox.apply_patch(diff)
    assert result["success"] is False
    assert result["error"] == "Malformed unified diff"
    assert "details" in result
    assert "suggestion" in result

def test_run_tests_valid(tools_sandbox):
    # We run a very fast specific test
    result = tools_sandbox.run_tests(["tests/test_cli.py"])
    assert isinstance(result, dict)
    assert "passed" in result
    # We don't strictly assert True because tests might fail depending on flask environment,
    # but we assert the structure is correct.

def test_run_tests_malformed(tools_sandbox):
    # Test file that does not exist
    result = tools_sandbox.run_tests(["tests/nonexistent_test_file.py"])
    assert result["passed"] is False
    assert "ERROR" in result["output"] or "ERROR" in result["stderr"] or "not found" in result["stderr"] + result["output"]

def test_schemas_validity():
    # Verify the schemas file is well-formed JSON
    schema_path = os.path.join("src", "tool_schemas.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        schemas = json.load(f)
    assert isinstance(schemas, list)
    assert len(schemas) == 5
    for schema in schemas:
        assert "name" in schema
        assert "description" in schema
        assert "parameters" in schema
        assert schema["parameters"]["type"] == "OBJECT"
