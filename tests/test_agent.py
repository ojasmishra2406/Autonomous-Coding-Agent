import os
import json
import pytest
from dotenv import load_dotenv

load_dotenv()

from src.sandbox import Sandbox
from src.dataset import Task
from src.agent import CodingAgent, AgentStatus

@pytest.mark.skipif("GEMINI_API_KEY" not in os.environ, reason="Requires GEMINI_API_KEY")
def test_agent_integration():
    print(f"\\nHAS_API_KEY: {os.environ.get('GEMINI_API_KEY') is not None}")
    
    # Load one task from the dev set
    with open("data/dev_tasks.jsonl", "r") as f:
        task_data = json.loads(f.readline())
    task = Task(**task_data)
    
    sb = Sandbox()
    sb.start(repo_url=f"https://github.com/{task.repo}.git", commit_sha=task.base_commit)
    
    try:
        agent = CodingAgent()
        # We set max_steps=6 to ensure the integration test doesn't run forever or cost too much,
        # but it proves the loop, tool parsing, and Gemini API integration work end-to-end.
        result = agent.solve(task, sb, max_steps=6)
        
        import pprint
        print("TRANSCRIPT:")
        pprint.pprint(result.transcript)
        print("FINAL STATUS:", result.status)

        assert isinstance(result.status, AgentStatus)
        assert result.steps_taken > 0
        assert len(result.transcript) > 0
        assert result.total_input_tokens > 0
        assert result.total_output_tokens > 0
    finally:
        sb.reset()
