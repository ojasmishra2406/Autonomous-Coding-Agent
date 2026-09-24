def path_similarity(src_dir, test_dir):
    src_parts = [p.lower() for p in src_dir.split('/') if p not in ('', '.', '..')]
    test_parts = [p.lower() for p in test_dir.split('/') if p not in ('', '.', '..', 'tests', 'test')]
    score = 0
    for sp in src_parts:
        if sp in ('src', 'lib', 'tests', 'test', 'django', 'astropy'): continue
        sp_base = sp.rstrip('s')
        if len(sp_base) < 3: continue
        for tp in test_parts:
            tp_base = tp.rstrip('s')
            if sp_base in tp_base or tp_base in sp_base:
                score += 1
    return score

print(path_similarity('django/db/models', 'tests/forms_tests/field_tests'))
print(path_similarity('django/db/models', 'tests/model_fields'))
