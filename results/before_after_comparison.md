# Phase 9: Before vs After Comparison (Iteration 2)

## Evaluation Set Baseline (5 Tasks)
**Target failure category:** Django test environments natively crashing (originally `ImproperlyConfigured` due to Pytest, then `TypeError: cannot pickle 'traceback' object` due to multiprocessing).

| Metric | Before (FEATURE_SMART_TESTS=0) | After (Iteration 2 Fixes) |
|--------|--------------------------------|---------------------------|
| Total Tasks | 5 | 5 |
| Resolved Rate | 0.0% (0/5) | 0.0% (0/5) |
| Timeout Rate | 80.0% (4/5) | 60.0% (3/5) |
| Model Error Rate | 20.0% (1/5) | 40.0% (2/5) |
| Avg Steps (Unresolved) | 13.80 | 14.80 |
| Targeted Failure Rate (Multiprocessing Crash) | 20.0% (1/5) | 0.0% (0/5) |

## Honest Results: A New Distinct Issue

Applying `--parallel=1` and `--settings=test_sqlite` to `sandbox.py` successfully resolved the multiprocessing pickling crashes. The environment is now perfectly stable. However, this surfaced a third, distinct issue that continues to prevent task resolution: **Test Suite Timeout Thrashing**.

Here is exactly what happens now:
1. When the agent uses `replace_file_content`, the framework automatically triggers `run_tests()` with no arguments to verify the fix.
2. Because no specific `test_ids` are provided, Django defaults to running its **entire** test suite (~14,000 tests).
3. With multiprocessing disabled (`--parallel=1`), the test suite takes over 15 minutes to run, immediately hitting our Sandbox's hard 120-second timeout.
4. The test process is killed, and our new harness crash detection logic correctly kicks in, prepending `[TEST HARNESS CRASH DETECTED. THE TESTS DID NOT RUN PROPERLY.]`.
5. The agent sees this, assumes its code edit broke the test environment, reverts its own (often correct) code, and tries again, eventually hitting the 15-step `TIMEOUT`.

*(Note: The other Django task, `django-11630`, timed out simply because Mistral got stuck in a `replace_file_content` whitespace hallucination loop for 15 steps and never even reached the test phase).*

## Conclusion
The fixes implemented in Iteration 2 were completely successful at stabilizing the Django environment (eliminating driver issues and multiprocessing faults). However, the overall architecture still fails because the framework auto-runs the global test suite after every edit, which inherently exceeds the sandbox timeout limit. 

To achieve a non-zero resolve rate, we would need to either radically extend the sandbox timeout, or update the system prompt/framework to force the agent to explicitly pass targeted `test_ids` rather than auto-running the global suite.
