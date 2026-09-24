with open("src/agent.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("tracer.record_run(AgentStatus.MODEL_ERROR.value, step+1, total_in, total_out, total_thoughts)",
                          "tracer.record_run(AgentStatus.MODEL_ERROR.value, step+1, total_in, total_out, total_thoughts, provider=provider_used or 'unknown')")
                          
content = content.replace("tracer.record_run(AgentStatus.TOOL_LOOP.value, step+1, total_in, total_out, total_thoughts)",
                          "tracer.record_run(AgentStatus.TOOL_LOOP.value, step+1, total_in, total_out, total_thoughts, provider=provider_used or 'unknown')")
                          
content = content.replace("tracer.record_run(AgentStatus.SUCCESS.value, step+1, total_in, total_out, total_thoughts)",
                          "tracer.record_run(AgentStatus.SUCCESS.value, step+1, total_in, total_out, total_thoughts, provider=provider_used or 'unknown')")
                          
content = content.replace("tracer.record_run(AgentStatus.TIMEOUT.value, max_steps, total_in, total_out, total_thoughts)",
                          "tracer.record_run(AgentStatus.TIMEOUT.value, max_steps, total_in, total_out, total_thoughts, provider=provider_used or 'unknown')")
                          
content = content.replace("tracer.record_run(AgentStatus.COMPLETED.value, step+1, total_in, total_out, total_thoughts)",
                          "tracer.record_run(AgentStatus.COMPLETED.value, step+1, total_in, total_out, total_thoughts, provider=provider_used or 'unknown')")

with open("src/agent.py", "w", encoding="utf-8") as f:
    f.write(content)
