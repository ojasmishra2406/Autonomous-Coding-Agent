import re

with open('src/tools.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_func = '''    def run_tests(self, test_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Prevent: The agent assuming it fixed the issue just because it wrote a patch.
        Forces the agent to run the tests and observe real stderr before concluding.
        """
        if not test_ids:
            return {
                "passed": False,
                "error": "You must provide specific test_ids. Running the entire test suite is too slow and will crash the container. Find the relevant test files and pass their paths.",
                "stderr": "",
                "output": ""
            }
        result = self.sandbox.run_tests(test_ids)
        return {
            "passed": result.passed,
            "stderr": result.stderr,
            "output": result.output
        }'''

content = re.sub(r'    def run_tests\(self.*?result\.output\n        \}', new_func, content, flags=re.DOTALL)

with open('src/tools.py', 'w', encoding='utf-8') as f:
    f.write(content)
