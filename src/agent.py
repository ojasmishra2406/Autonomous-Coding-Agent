import os
import json
import tempfile
import subprocess
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel
import time

from src.sandbox import Sandbox
from src.dataset import Task
from src.tools import AgentTools
from src.repo_map import build_repo_map
from src.tracing import Tracer

class AgentStatus(str, Enum):
    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    LOOP_DETECTED = "LOOP_DETECTED"
    MODEL_ERROR = "MODEL_ERROR"
    TOOL_LOOP = "TOOL_LOOP"

class AgentResult(BaseModel):
    status: AgentStatus
    steps_taken: int
    total_input_tokens: int
    total_output_tokens: int
    final_patch: str
    transcript: List[Dict[str, Any]]


def sanitize_message_history(history):
    """
    Ensures message history complies with Groq API constraints:
    - Orphaned tool_calls must be paired with a synthetic tool response.
    - Role interleaving must be strictly alternating (user/assistant) or correctly chained.
    """
    sanitized = []
    for i, msg in enumerate(history):
        sanitized.append(msg)
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            # Check if next message is a tool response
            if i + 1 < len(history) and history[i+1].get("role") == "tool":
                continue
            else:
                # Insert synthetic dummy tool response
                dummy_response = {
                    "role": "tool",
                    "content": "{ \"error\": \"Tool call interrupted or system state reset.\" }",
                    "name": msg["tool_calls"][0]["function"]["name"],
                    "tool_call_id": msg["tool_calls"][0]["id"]
                }
                sanitized.append(dummy_response)
    return sanitized

class CodingAgent:

    def __init__(self):
        pass

    def solve(self, task: Task, sandbox: Sandbox, max_steps: int = 15, allow_fallback: bool = False) -> AgentResult:
        def get_final_patch():
            stdout, _, _ = sandbox.exec("git -C /workspace/repo diff", timeout=10)
            return stdout or ""
            
        print("DEBUG: Creating sandbox tools...")
        tools_instance = AgentTools(sandbox)
        
        
        with open(os.path.join("src", "prompts", "system.txt"), "r", encoding="utf-8") as f:
            system_prompt = f.read()
            system_prompt += "\n\nOPERATIONAL INVARIANTS:\n1. ALWAYS use the provided tools to explore, read, search, edit, and test files.\n2. NEVER apologize, output conversational chit-chat, or claim 'I am an AI and cannot use tools'.\n3. If a test crashes, dependencies fail, or a tool throws an error, DO NOT give up. Analyze stderr, inspect the repository structure, read the code, and apply a fix.\n4. When finished, ensure all modified files are clean, your targeted tests pass, and call apply_patch or verify changes before concluding.\n5. All code modifications MUST be precise and targeted."

            
        from dotenv import load_dotenv
        load_dotenv(override=True)
        tracer = Tracer(task.instance_id)
        
        # We need the repo map. Since Sandbox isolates the repo, we temporarily clone it locally
        # to generate the map using our python AST parsing logic.
        repo_map = ""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_url = f"https://github.com/{task.repo}.git"
            print(f"DEBUG: Cloning {repo_url}...")
            # Full clone to ensure we can checkout the exact commit
            subprocess.check_call(["git", "clone", repo_url, tmpdir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("DEBUG: Checking out commit...")
            subprocess.check_call(["git", "-C", tmpdir, "checkout", task.base_commit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("DEBUG: Building repo map...")
            repo_map = build_repo_map(tmpdir, task.problem_statement)
            print("DEBUG: Repo map built.")
            
        full_system = f"{system_prompt}\n\n=== ISSUE ===\n{task.problem_statement}\n\n=== REPO MAP ===\n{repo_map}"
        SYSTEM_PROMPT = full_system
        
        # Determine providers
        print("DEBUG: Initializing providers...")
        from src.providers import GeminiProvider, GroqProvider, CerebrasProvider, MistralProvider
        providers = []
        if allow_fallback:
            # Fallback chain
            print("DEBUG: Loading fallback providers (Mistral, Gemini, Groq, Cerebras)")
            providers = [MistralProvider(), GeminiProvider(), GroqProvider(), CerebrasProvider()]
        else:
            provider_name = os.environ.get("MODEL_PROVIDER", "gemini").lower()
            if provider_name == "groq":
                providers = [GroqProvider()]
            elif provider_name == "cerebras":
                providers = [CerebrasProvider()]
            else:
                providers = [GeminiProvider()]
                
        print("DEBUG: Providers initialized.")
            
        # Standardized history format
        prompt = "Please start the task."
        history = [{"role": "user", "content": prompt}]
        transcript = []
        
        total_in = 0
        total_out = 0
        total_thoughts = 0
        consecutive_errors = 0
        consecutive_same_calls = 0
        last_tool_call = ""

        
        # 1. Initialize conversation with system prompt and tools
        for step in range(max_steps):
            history = sanitize_message_history(history)
            # 2. Each turn, call the model
            step_start = time.time()
            
            # Print exact payload token count
            try:
                import tiktoken
                enc = tiktoken.get_encoding("cl100k_base")
                
                # Pruning logic:
                # history[0] = original user prompt "Please start the task." — NEVER pruned.
                # All subsequent entries are [assistant, tool, assistant, tool, ...] pairs.
                # We must always remove a full pair (2 entries) to avoid breaking message structure.
                # The problem_statement is safely in SYSTEM_PROMPT, not in history, so it's always preserved.
                system_tokens = len(enc.encode(SYSTEM_PROMPT))
                while True:
                    history_str = json.dumps(history)
                    payload_tokens = system_tokens + len(enc.encode(history_str))
                    if payload_tokens <= 7500:
                        break
                    # history[0] is "Please start the task." — protect it.
                    # Find the oldest complete assistant+tool pair starting at index 1.
                    # A pair is: history[1]=assistant, history[2]=tool
                    if len(history) >= 4:  # [user, asst, tool, ...] — need at least 1 full pair + something after
                        # Check if indices 1 and 2 form a valid pair
                        if history[1].get("role") == "assistant" and history[2].get("role") == "tool":
                            history.pop(1)  # remove assistant turn
                            history.pop(1)  # remove tool turn (now at index 1)
                        else:
                            # Orphaned entry — just pop it
                            history.pop(1)
                    else:
                        # Can't prune further without destroying the only user turn
                        break
                        
                history_str = json.dumps(history)
                payload_tokens = system_tokens + len(enc.encode(history_str))
                print(f"\n--- PRE-FLIGHT TOKEN CHECK ---")
                print(f"Payload (System + History) Tokens: ~{payload_tokens}")
                print(f"Groq model: {os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')} | TPM ceiling: ~12,000")
                print("------------------------------")
            except Exception as e:
                pass
                
            print(f"\n--- HISTORY AT STEP {step} ---")
            for h in history:
                print(f"Role: {h['role']}, Content: {str(h)[:100]}...")
            print("------------------------------")
            provider_used = None
            response = None
            latency_ms = 0
            call_exc = None
            
            # If all fail, wait and retry the chain (up to 3 times total for the turn)
            for turn_attempt in range(3):
                for p in providers:
                    try:
                        response = p.call_model(history, SYSTEM_PROMPT)
                        latency_ms = (time.time() - step_start) * 1000
                        time.sleep(2)
                        provider_used = p.__class__.__name__.replace('Provider', '').lower()
                        call_exc = None
                        break
                    except Exception as e:
                        call_exc = e
                        err_str = str(e).lower()
                        if any(k in err_str for k in ("rate_limit", "429", "quota", "overloaded", "timeout")):
                            print(f"[{p.__class__.__name__}] Rate limited, falling back...")
                            continue # Try next provider
                        else:
                            # Not a rate limit, break out of provider loop to handle as real error
                            break
                            
                if response is not None or (call_exc is not None and not any(k in str(call_exc).lower() for k in ("rate_limit", "429", "quota", "overloaded", "timeout"))):
                    break
                
                # If we get here, ALL providers returned 429
                if turn_attempt < 2:
                    wait = 10 * (2 ** turn_attempt)
                    print(f"All providers rate-limited. Waiting {wait}s and retrying...")
                    time.sleep(wait)
                    
            if call_exc is not None and response is None:
                e = call_exc
                consecutive_errors += 1
                transcript.append({"step": step, "role": "system", "content": f"API Error: {str(e)}"})
                if consecutive_errors >= 3:
                    tracer.record_run(AgentStatus.MODEL_ERROR.value, step+1, total_in, total_out, total_thoughts, provider=provider_used or 'unknown')
                    return AgentResult(status=AgentStatus.MODEL_ERROR, steps_taken=step+1, total_input_tokens=total_in, total_output_tokens=total_out, final_patch=get_final_patch(), transcript=transcript)
                # If last assistant message had tool_calls, we MUST respond with a tool message
                # (not a user message) or Groq will reject the sequence on the next call.
                last = history[-1] if history else {}
                if last.get("role") == "assistant" and last.get("tool_calls"):
                    tc = last["tool_calls"][0]
                    history.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id") or "call_0",
                        "name": tc.get("name", "unknown"),
                        "content": {"error": f"API Error: {str(e)}. Please retry with a different approach."}
                    })
                else:
                    history.append({"role": "user", "content": f"API Error occurred. Please call a tool to continue."})
                continue
                
            total_in += response.input_tokens
            total_out += response.output_tokens
            total_thoughts += response.thoughts_tokens
            
            tool_calls = response.function_calls
            if not tool_calls:
                if not response.text or "apologize" in response.text.lower() or "as an ai" in response.text.lower():
                    history.append({"role": "assistant", "content": response.text or ""})
                    history.append({"role": "user", "content": "Notice: Apologies or blank messages are prohibited. You must use tools to solve the issue."})
                    continue

                
            history.append({
                "role": "assistant",
                "content": response.text,
                "tool_calls": response.function_calls
            })
            
            transcript.append({
                "role": "model",
                "text": response.text,
                "tool_calls": response.function_calls
            })
            
            tool_calls = response.function_calls
            if not tool_calls:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    tracer.record_run(AgentStatus.MODEL_ERROR.value, step+1, total_in, total_out, total_thoughts, provider=provider_used or 'unknown')
                    return AgentResult(status=AgentStatus.MODEL_ERROR, steps_taken=step+1, total_input_tokens=total_in, total_output_tokens=total_out, final_patch=get_final_patch(), transcript=transcript)
                history.append({"role": "user", "content": "You must call a tool to proceed. Please formulate a plan and use a tool."})
                continue
                
            consecutive_errors = 0 
            
            # We process the first tool call for simplicity
            func_call = tool_calls[0]
            name = func_call["name"]
            args = func_call["args"]
            
            # Stop condition: 3 consecutive identical tool calls
            # Reasoning: If the model is trapped calling the exact same tool with the exact same arguments repeatedly,
            # it is in a degenerate loop and will never progress. We stop to save tokens.
            current_call_str = f"{name}:{sorted(args.items())}"
            if current_call_str == last_tool_call:
                consecutive_same_calls += 1
            else:
                consecutive_same_calls = 0
            last_tool_call = current_call_str
            
            if consecutive_same_calls >= 3:
                tracer.record_run(AgentStatus.TOOL_LOOP.value, step+1, total_in, total_out, total_thoughts, provider=provider_used or 'unknown')
                return AgentResult(status=AgentStatus.TOOL_LOOP, steps_taken=step+1, total_input_tokens=total_in, total_output_tokens=total_out, final_patch=get_final_patch(), transcript=transcript)
            
            # Execute the tool
            tool_method = getattr(tools_instance, name, None)
            if not tool_method:
                result_data = {"error": f"Tool {name} not found"}
            else:
                try:
                    result_data = tool_method(**args)
                except Exception as e:
                    result_data = {"error": str(e)}
                    
            if name == "run_tests":
                if isinstance(result_data, dict) and result_data.get("passed"):
                    tracer.record_run(AgentStatus.SUCCESS.value, step+1, total_in, total_out, total_thoughts, provider=provider_used or 'unknown')
                    return AgentResult(status=AgentStatus.SUCCESS, steps_taken=step+1, total_input_tokens=total_in, total_output_tokens=total_out, final_patch=get_final_patch(), transcript=transcript)
                    

                            
            # Append the function response back in Provider's expected format
            history.append({
                "role": "tool",
                "tool_call_id": func_call.get("id"),
                "name": name,
                "content": result_data
            })
            
            # Log the step to JSONL
            tracer.log_step(
                step_number=step,
                tool_called=name,
                tool_result_summary=str(result_data)[:200], # truncate summary
                model_input_tokens=response.input_tokens,
                model_output_tokens=response.output_tokens,
                latency_ms=latency_ms,
                thoughts_token_count=response.thoughts_tokens,
                provider_used=provider_used
            )
            
            transcript.append({
                "role": "tool",
                "name": name,
                "result": result_data
            })
            
        # Stop condition: max_steps reached (TIMEOUT)
        # Reasoning: The agent failed to solve the issue within the allotted step budget, likely exploring down a dead end.
        tracer.record_run(AgentStatus.TIMEOUT.value, max_steps, total_in, total_out, total_thoughts, provider=provider_used or 'unknown')
        return AgentResult(status=AgentStatus.TIMEOUT, steps_taken=max_steps, total_input_tokens=total_in, total_output_tokens=total_out, final_patch=get_final_patch(), transcript=transcript)

