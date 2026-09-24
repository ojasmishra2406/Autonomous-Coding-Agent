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
 5. run_tests() [Auto-trigger on edit]       |
       |                                     |
       v                                     |
[ Dynamic Docker Sandbox ]                   |
 - Auto-resolves Python 3.7/3.9/3.11 base    |
 - Bypasses legacy pytest fatal warnings     |
 - 120-second hard timeout & strict isolation|
       |                                     |
       +------- (Result Output) -------------+
```

- **Dynamic Docker Sandbox**: Ephemeral containerized execution of the target repository. It intelligently routes tasks to `python:3.7-slim`, `python:3.9-slim`, or `python:3.11-slim` based on historical requirements (avoiding legacy `numpy` and `collections` crashes in older 2017-era repositories).
- **Multi-Provider Abstraction**: A highly resilient client-side architecture that automatically routes across Groq, Mistral, Gemini, and Cerebras. Includes strict message history sanitization for API constraints.
- **Client-Side Metrics Tracker**: Comprehensive SQLite-based metrics tracking for latency, tokens, cost, steps, and tool usage per task.

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

## 4. Phase 9 Final Results
The evaluation was executed in 5-task micro-batches due to strict free-tier API quota constraints.

**Run Date**: September 24, 2026
**Tasks**: `astropy-12907`, `astropy-6938`, `astropy-7746`, `django-10914`, `django-11630`
**Pinned Provider**: `Mistral (codestral-latest)` / `Groq (gpt-oss-120b)`

- **Resolved Rate**: 0.0% (0/5)
- **Timeout Rate**: 60.0%
- **Tool Usage**: 112 edit attempts (`replace_file_content`)
- **Infrastructure Crash Rate**: 0.0% (Massive improvement over previous phases)

*Note: The core framework is now fully stabilized. The 0% resolution rate stems strictly from the agent's inability to perfectly format exact-match file replacements, consistently trapping it in `TOOL_LOOP` states.*

## 5. Overcoming Legacy Benchmark Hurdles (Sandbox Fixes)
Throughout development, we discovered and eliminated major infrastructure bottlenecks that historically prevented agent evaluation:

| Bottleneck | Fix Implemented |
|-------|------------|
| **Open-weight Diff Hallucination** | **FIXED:** Replaced `apply_patch` with a strict `replace_file_content` tool. |
| **Django Test Crashes** | **FIXED:** Implemented `FEATURE_SMART_TESTS=1` to auto-detect Django and swap to `runtests.py --parallel=1 --settings=test_sqlite`. |
| **Legacy Python 3.10 Incompatibilities** | **FIXED:** Tasks from ~2017 (e.g. early `astropy`) crash natively on modern Python due to `collections.Mapping` removals. The Sandbox now maps `instance_id` to `python:3.7-slim` dynamically. |
| **Pytest Deprecation Fatalities** | **FIXED:** Older repositories configured `pytest` to fail on `DeprecationWarning`, instantly crashing the test harness. Patched via `PYTHONWARNINGS=ignore pytest`. |
| **Debian Buster Archive Errors** | **FIXED:** Dynamically rewrites `/etc/apt/sources.list` to `archive.debian.org` during `python:3.7-slim` image builds to prevent hanging. |

## 6. Limitations & Future Work
While the underlying Docker execution engine is now rock-solid, the agent requires cognitive upgrades to improve its 0% resolution rate:
1. **Line-Range Editor**: Replace exact-match string replacement (`replace_file_content`) with line-number based edits (`edit_file(start, end, content)`) to mitigate whitespace sensitivity failures.
2. **Contextual Tool Errors**: Return fuzzy-matched line suggestions in the error message when an edit fails, rather than blindly failing, allowing the LLM to self-correct typos.
3. **Generic Terminal Access**: Replace hardcoded `search_code` and `list_files` with a generic `run_bash` tool, granting the agent full semantic exploration.

## 7. Reproduction Instructions
1. Clone the repository and initialize the virtual environment:
   ```bash
   git clone https://github.com/yourusername/coding-agent.git
   cd coding-agent
   uv venv
   uv pip install -e .
   ```
2. Export your available API keys:
   ```bash
   export MISTRAL_API_KEY="your_key"
   export GEMINI_API_KEY="your_key"
   export GROQ_API_KEY="your_key"
   ```
3. Run the evaluation micro-batch:
   ```bash
   uv run python scripts/run_dev.py --max-tasks 5
   ```
