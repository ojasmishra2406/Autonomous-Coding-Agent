
Remove-Item runs.db -ErrorAction SilentlyContinue
$env:FEATURE_SMART_TESTS = '1'
uv run python scripts/run_eval.py --max-tasks 5

