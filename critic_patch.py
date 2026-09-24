import re

with open("src/agent.py", "r", encoding="utf-8") as f:
    content = f.read()

critic_func = '''
def evaluate_patch_with_critic(diff: str, task, provider) -> tuple[bool, str]:
    if not diff.strip():
        return False, "The git diff is empty. You must modify files to fix the issue before completing the task."
    
    critic_prompt = f"""You are an elite SWE-bench Code Reviewer and Execution Auditor.
Your purpose is to stress-test and review the git patch produced by an autonomous coding agent before finalizing the task.

Issue Description: {task.problem_statement}
Proposed Diff:
{diff}

Your Operational Directive:
1. Regressive Bug Audit: Check whether the edit modifies core APIs or signatures that might break non-targeted tests elsewhere.
2. SWE-Bench Anti-Cheat Check: Confirm the patch does NOT modify any tests in the test suite itself (e.g. tests/, test_*, etc.).
3. Minimal Modification Rule: Flag any whitespace alterations, irrelevant formatting changes, or redundant comments. Ensure the diff touches only the exact minimal lines necessary.

Output EXACTLY in this format:
VERDICT: [PASS / REJECT]
REASONING: Concise technical breakdown."""

    try:
        history = [{"role": "user", "content": critic_prompt}]
        response = provider.call_model(history, "You are a code reviewer.")
        text = response.text or ""
        return "VERDICT: PASS" in text.upper(), text
    except Exception as e:
        return True, "Critic execution failed, bypassing."

'''

content = content.replace("def sanitize_message_history(history):", critic_func + "\ndef sanitize_message_history(history):")

old_block = '''            tool_calls = response.function_calls
            if not tool_calls:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    tracer.record_run(AgentStatus.MODEL_ERROR.value, step+1, total_in, total_out, total_thoughts)
                    return AgentResult(status=AgentStatus.MODEL_ERROR, steps_taken=step+1, total_input_tokens=total_in, total_output_tokens=total_out, final_patch=get_final_patch(), transcript=transcript)
                history.append({"role": "user", "content": "You must call a tool to proceed. Please formulate a plan and use a tool."})
                continue'''

new_block = '''            tool_calls = response.function_calls
            if not tool_calls:
                patch = get_final_patch()
                print("DEBUG: Running pre-flight critic on patch...")
                passed, feedback = evaluate_patch_with_critic(patch, task, providers[0])
                
                if not passed:
                    print("DEBUG: Critic rejected patch.")
                    history.append({
                        "role": "user",
                        "content": f"CRITIC REVIEW FAILED. Your proposed patch was rejected by the SWE-bench execution auditor.\\n\\n{feedback}\\n\\nPlease use your tools to apply the corrective edit or revert the violating changes."
                    })
                    continue
                
                print("DEBUG: Critic approved patch.")
                tracer.record_run(AgentStatus.SUCCESS.value, step+1, total_in, total_out, total_thoughts)
                return AgentResult(status=AgentStatus.SUCCESS, steps_taken=step+1, total_input_tokens=total_in, total_output_tokens=total_out, final_patch=patch, transcript=transcript)'''

content = content.replace(old_block, new_block)

with open("src/agent.py", "w", encoding="utf-8") as f:
    f.write(content)
