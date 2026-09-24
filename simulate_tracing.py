import os
from src.tracing import Tracer
from src.agent import AgentStatus

def simulate_runs():
    # Simulate a successful run
    tracer1 = Tracer("mock_task_1")
    tracer1.log_step(1, "list_files", "{'files': ['app.py']}", 1000, 50, 1200.5)
    tracer1.log_step(2, "read_file", "content...", 1050, 200, 2000.0)
    tracer1.log_step(3, "apply_patch", "{'success': True, 'test_result': {'passed': True}}", 1250, 50, 1500.0)
    tracer1.record_run(AgentStatus.SUCCESS.value, 3, 3300, 300)
    
    # Simulate a timeout run
    tracer2 = Tracer("mock_task_2")
    tracer2.log_step(1, "search_code", "{'matches': []}", 1000, 50, 1000.0)
    tracer2.log_step(2, "search_code", "{'matches': []}", 1050, 50, 1100.0)
    tracer2.record_run(AgentStatus.TIMEOUT.value, 15, 15000, 1000)
    
    print("Simulated runs created.")

if __name__ == "__main__":
    simulate_runs()
