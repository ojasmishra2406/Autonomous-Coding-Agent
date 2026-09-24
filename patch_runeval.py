import re

with open("scripts/run_eval.py", "r", encoding="utf-8") as f:
    content = f.read()

content = re.sub(
    r'(parser\.add_argument\("--max-tasks".*?\n)',
    r'\1    parser.add_argument("--task-id", type=str, default=None)\n    parser.add_argument("--provider", type=str, default=None)\n',
    content
)

content = re.sub(
    r'(tasks\.append\(Task\(\*\*data\)\)\n)',
    r'\1\n    if args.task_id:\n        tasks = [t for t in tasks if t.instance_id == args.task_id]\n    if args.provider:\n        import os\n        os.environ["MODEL_PROVIDER"] = args.provider\n',
    content
)

with open("scripts/run_eval.py", "w", encoding="utf-8") as f:
    f.write(content)
