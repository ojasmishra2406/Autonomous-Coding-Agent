import json
from src.sandbox import Sandbox
from src.tools import AgentTools

def run_verification():
    print("--- VALIDATING tool_schemas.json ---")
    with open("src/tool_schemas.json", "r") as f:
        schemas = json.load(f)
        print("tool_schemas.json is valid JSON. Loaded", len(schemas), "schemas.")

    print("\n--- INITIALIZING SANDBOX ---")
    sb = Sandbox()
    repo_url = "https://github.com/pallets/flask.git"
    commit_sha = "d73fa1cdcbd8b1465c151db8924ba58b1dd14e35"
    sb.start(repo_url, commit_sha)
    tools = AgentTools(sb)
    
    print("\n--- TESTING list_files ---")
    print("VALID:", tools.list_files("src/flask")[0:3], "...")
    print("MALFORMED:", tools.list_files("/nonexistent/path"))

    print("\n--- TESTING read_file ---")
    print("VALID:\n", tools.read_file("src/flask/app.py", 1, 3))
    print("MALFORMED:\n", tools.read_file("src/flask/nonexistent.py"))

    print("\n--- TESTING search_code ---")
    valid_search = tools.search_code("class Flask", "src/flask/app.py")
    print("VALID:", valid_search[0] if valid_search else "No match")
    print("MALFORMED (empty/bad regex):", tools.search_code("class [unmatched", "src/flask/app.py"))

    print("\n--- TESTING apply_patch ---")
    tools.sandbox.exec("echo 'hello' > /workspace/repo/test_patch.txt", 5)
    tools.sandbox.exec("git add test_patch.txt", 5)
    
    valid_diff = """--- a/test_patch.txt
+++ b/test_patch.txt
@@ -1 +1 @@
-hello
+world
"""
    print("VALID DIFF RESULT:", tools.apply_patch(valid_diff))
    
    garbage_diff = "This is literally just garbage text."
    print("CORRUPTED SYNTAX RESULT:", tools.apply_patch(garbage_diff))

    nonexistent_file_diff = """--- a/does_not_exist.txt
+++ b/does_not_exist.txt
@@ -1 +1 @@
-hello
+world
"""
    print("NONEXISTENT FILE RESULT:", tools.apply_patch(nonexistent_file_diff))

    print("\n--- TESTING run_tests ---")
    print("VALID (fast test):", tools.run_tests(["tests/test_cli.py"])["passed"])
    malformed_test = tools.run_tests(["tests/does_not_exist.py"])
    print("MALFORMED (nonexistent test): passed =", malformed_test["passed"], "stderr =", malformed_test["stderr"].splitlines()[0] if malformed_test["stderr"] else "None")

    sb.reset()

if __name__ == "__main__":
    run_verification()
