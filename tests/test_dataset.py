import pytest
from src.dataset import load_tasks

def test_no_overlap_between_splits():
    dev_tasks = load_tasks(split="dev", n=30, seed=42)
    eval_tasks = load_tasks(split="eval", n=100)
    
    dev_ids = {t.instance_id for t in dev_tasks}
    eval_ids = {t.instance_id for t in eval_tasks}
    
    intersection = dev_ids.intersection(eval_ids)
    
    assert len(intersection) == 0, f"Found overlapping instance IDs: {intersection}"
    
    # Also verify lengths
    assert len(dev_tasks) == 30
    assert len(eval_tasks) == 100
    
    # Verify stratification (at least 4 repos)
    dev_repos = {t.repo for t in dev_tasks}
    eval_repos = {t.repo for t in eval_tasks}
    assert len(dev_repos) >= 4, f"Dev set only spans {len(dev_repos)} repos"
    assert len(eval_repos) >= 4, f"Eval set only spans {len(eval_repos)} repos"
