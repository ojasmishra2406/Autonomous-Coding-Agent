import re

with open("src/agent.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove evaluate_patch_with_critic
content = re.sub(
    r'def evaluate_patch_with_critic.*?def sanitize_message_history',
    r'def sanitize_message_history',
    content,
    flags=re.DOTALL
)

# 2. Replace the critic block with the original error block
old_critic_block = '''            tool_calls = response.function_calls
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

reverted_block = '''            tool_calls = response.function_calls
            if not tool_calls:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    tracer.record_run(AgentStatus.MODEL_ERROR.value, step+1, total_in, total_out, total_thoughts)
                    return AgentResult(status=AgentStatus.MODEL_ERROR, steps_taken=step+1, total_input_tokens=total_in, total_output_tokens=total_out, final_patch=get_final_patch(), transcript=transcript)
                history.append({"role": "user", "content": "You must call a tool to proceed. Please formulate a plan and use a tool."})
                continue'''

content = content.replace(old_critic_block, reverted_block)

with open("src/agent.py", "w", encoding="utf-8") as f:
    f.write(content)
