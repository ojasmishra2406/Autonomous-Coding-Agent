import tempfile
import subprocess
import os
import tiktoken
from src.repo_map import build_repo_map

def test_repo_map_token_limit_and_relevance():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Clone a real repo for the test
        repo_url = "https://github.com/pallets/flask.git"
        # We can just clone a specific branch or depth to make it fast
        subprocess.check_call(["git", "clone", "--depth", "1", repo_url, tmpdir])
        
        # A sample issue problem statement
        problem_statement = "The routing in Flask app fails when defining a route with a specific HTTP method."
        
        repo_map_str = build_repo_map(tmpdir, problem_statement)
        
        # Check token count
        enc = tiktoken.get_encoding("cl100k_base")
        token_count = len(enc.encode(repo_map_str))
        
        # The limit is 2000, but adding the truncation message might push it slightly over,
        # though our logic checks `if len > 2000` BEFORE adding the last file.
        # So it should be close to 2000 + length of truncation message.
        assert token_count <= 2100, f"Token count {token_count} exceeded budget!"
        
        # Check relevance
        # Because we mention "route" and "app", src/flask/app.py should score highly and be included
        assert "src/flask/app.py" in repo_map_str
