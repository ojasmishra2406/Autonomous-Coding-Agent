# Autonomous Coding Agent Evaluation Framework

## 1. Problem
This project implements an autonomous AI coding agent designed to resolve real-world GitHub issues. It evaluates the agent's performance against a subset of the industry-standard **SWE-bench Lite** dataset. The goal was to build a robust, multi-provider execution pipeline capable of running completely isolated repository modifications, test executions, and self-correction loops.

## 2. Architecture
The framework operates on a standard ReAct-style agentic loop with custom tool-calling, sandboxing, and provider fallbacks.

```text
[ Task Payload (SWE-bench) ] ---> [ Agent LLM Router ]
                                      |      ^
       +------------------------------+      |
       |                                     |
       v                                     |
[ Tool Execution ]                           |
 1. list_files()                             |
 2. read_file()                              |
 3. search_code()                            |
 4. replace_file_content() [Primary]         |
 5. apply_patch() [Fallback]                 |
 6. run_tests() [Auto-trigger on edit]       |
       |                                     |
       v                                     |
[ Docker Sandbox ]                           |
 - Strict resource & network limits          |
 - 120-second hard timeout                   |
 - Django-aware test-runner detection        |
       |                                     |
       +------- (Result Output) -------------+
```

- **Docker Sandbox**: Ephemeral containerized execution of the target repository.
- **Multi-Provider Abstraction**: A highly resilient client-side architecture that automatically routes and falls back across Mistral, Gemini, Groq, and Cerebras to bypass free-tier rate limits.
- **Client-Side Token Limiting**: Custom token counting (`tiktoken`) to intelligently truncate file read outputs and maintain context windows.

## 3. Tech Stack
Built heavily on Python 3.11+ using the `uv` package manager. See `pyproject.toml` for exact configurations.
- `datasets==2.20.0`
- `docker==7.1.0`
- `google-genai==1.46.0`
- `openai==3.16.2`
- `pydantic==2.8.2`
- `pytest==8.2.2`
- `python-dotenv==1.2.3`
- `structlog==24.4.0`
- `tiktoken==0.7.0`
- `unidiff==0.7.5`

## 4. Results
The evaluation was executed in 5-task micro-batches due to strict free-tier API quota constraints across all providers. 

**Run Date**: September 22, 2026
**Pinned Provider**: `Mistral (codestral-latest)` with Groq/Gemini/Cerebras automatic failovers.

- **Resolved Rate**: 0.0% (0/5)
- **Timeout Rate**: 60.0%
- **Model/Infra Error Rate**: 20.0%
- **Average Steps (Unresolved)**: 12.60 steps

*Note: While infrastructure improvements vastly increased the agent's ability to navigate and edit the codebase without hallucinations, the ultimate resolved rate remained 0% due to deep test-harness timeout issues (documented below).*

## 5. Failure Taxonomy
Throughout the development of this framework, we discovered and isolated three distinct layers of failure.

| Layer | Failure Mode | Fix Status |
|-------|--------------|------------|
| 1. Model Formatting | Open-weight models severely hallucinate standard unified `diff` formatting, breaking `apply_patch`. | **FIXED:** Replaced with a highly-structured, whitespace-sensitive `replace_file_content` tool. |
| 2. Django Environments | Blindly running `pytest` on Django repos triggers catastrophic `ImproperlyConfigured` and multiprocessing pickling crashes. | **FIXED:** Implemented `FEATURE_SMART_TESTS=1` to auto-detect Django and swap to `runtests.py --parallel=1 --settings=test_sqlite`. |
| 3. Global Test Timeouts | `run_tests` auto-triggers the global test suite instead of targeted subsets, exceeding the 120s sandbox limit. | **UNRESOLVED:** Forms the current bottleneck preventing a non-zero resolve rate. |

## 6. Before/After Improvement
During Phase 9, we iterated on the Django environment failures (Layer 2) and successfully eliminated the targeted failure categories, though it merely unmasked the next bottleneck (Layer 3). **The overall resolved rate remained 0% throughout all iterations.**

**Iteration 1: Fixing Pytest Hallucination**
| Metric | Before (FEATURE_SMART_TESTS=0) | After (Iteration 1) |
|--------|--------------------------------|---------------------|
| Resolved Rate | 0.0% | 0.0% |
| Targeted Failure (`ImproperlyConfigured`) | 40.0% | 0.0% |

**Iteration 2: Fixing Multiprocessing Crashes**
| Metric | Before (Iteration 1) | After (Iteration 2) |
|--------|----------------------|---------------------|
| Resolved Rate | 0.0% | 0.0% |
| Targeted Failure (`TypeError: traceback`) | 20.0% | 0.0% |

## 7. Deep Failure Case Study: `django__django-10914`
This specific task beautifully illustrates the Layer 3 global test timeout failure mode.

1. **Successful Edit**: The agent correctly diagnoses the issue and uses `replace_file_content` to apply a valid fix to Django's file upload permissions.
2. **Auto-Test Trigger**: Because the edit tool returned success, the framework automatically fires `run_tests()` behind the scenes.
3. **The Global Execution**: Because the agent didn't supply specific `test_ids`, the sandbox runs `python tests/runtests.py --parallel=1 --settings=test_sqlite`. This runs Django's *entire* 14,000+ test suite sequentially.
4. **The Timeout**: The test execution hits the hard 120-second Docker sandbox limit and is killed via `SIGKILL`.
5. **False Positive Detection**: Our crash detection logic intercepts the non-zero exit code (without an explicit AssertionError) and feeds the model:
   > `[TEST HARNESS CRASH DETECTED. THE TESTS DID NOT RUN PROPERLY.]\n[Sandbox] Command timed out.`
6. **Hallucination & Revert**: The agent interprets this as evidence that its code change fundamentally broke the test harness. It says: *"The replacement was successful, but the test suite still crashed... Let's revert the change"* and proceeds to undo its correct fix, thrashing until it hits the 15-step `TIMEOUT`.

## 8. Limitations
- **Global Test Timeouts**: The core unresolved bottleneck is that `run_tests` auto-runs the entire suite instead of accepting targeted `test_ids` from the model, causing legitimate timeouts on large monolithic test suites.
- **Free-Tier Quota Constraints**: Severe API limits across the four providers restricted evaluation sizes to 5-task micro-batches rather than the full 300-task SWE-bench dataset.
- **Whitespace Sensitivity**: While `replace_file_content` is significantly more reliable than `apply_patch` for open-weight models, it is deeply susceptible to indentation and whitespace hallucination, frequently causing the agent to waste steps retrying identical edits.

## 9. Future Work
The clear next step to unblock actual task resolution is to **force targeted test execution**. The `run_tests` tool signature must be updated to mandate `test_ids` as a required argument, or the framework must auto-discover the relevant test files based on the modified source files. This will reduce test execution time from 15+ minutes down to seconds, completely eliminating the Layer 3 sandbox timeouts.

## 10. Reproduction Instructions
1. Clone the repository and initialize the virtual environment:
   ```bash
   git clone https://github.com/yourusername/coding-agent.git
   cd coding-agent
   uv venv
   uv pip install -e .
   ```
2. Export your available API keys (the router will automatically fall back as limits are hit):
   ```bash
   export MISTRAL_API_KEY="your_key"
   export GEMINI_API_KEY="your_key"
   export GROQ_API_KEY="your_key"
   export CEREBRAS_API_KEY="your_key"
   ```
3. Enable the smart-test Django sandbox fixes:
   ```bash
   export FEATURE_SMART_TESTS="1"
   ```
4. Run the evaluation micro-batch:
   ```bash
   uv run python scripts/run_eval.py --max-tasks 5
   ```
