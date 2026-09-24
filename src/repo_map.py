import os
import ast
import re
import tiktoken

def extract_keywords(text: str) -> set:
    """Extract word tokens from text for simple heuristic scoring."""
    words = re.findall(r'\b[a-zA-Z_]{3,}\b', text.lower())
    stopwords = {"this", "that", "with", "from", "import", "class", "return", "def", "the", "and", "for"}
    return set(w for w in words if w not in stopwords)

def _get_python_files(repo_path: str):
    py_files = []
    for root, dirs, files in os.walk(repo_path):
        # Ignore hidden directories like .git, and common virtual envs/caches
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', '__pycache__', 'node_modules')]
        for f in files:
            if f.endswith('.py'):
                py_files.append(os.path.join(root, f))
    return py_files

def parse_file(filepath: str, repo_path: str):
    rel_path = os.path.relpath(filepath, repo_path).replace("\\", "/")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return rel_path, "", ""
        
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return rel_path, "", ""
        
    signatures = []
    docstrings = []
    
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            signatures.append(f"def {node.name}(...):")
            if ast.get_docstring(node):
                docstrings.append(ast.get_docstring(node))
        elif isinstance(node, ast.ClassDef):
            signatures.append(f"class {node.name}:")
            if ast.get_docstring(node):
                docstrings.append(ast.get_docstring(node))
            # Include methods inside classes
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    signatures.append(f"    def {item.name}(...):")
                    
    mod_doc = ast.get_docstring(tree)
    if mod_doc:
        docstrings.append(mod_doc)
        
    sig_str = "\n".join(signatures)
    doc_str = "\n".join(docstrings)
    
    return rel_path, sig_str, doc_str

def build_repo_map(repo_path: str, problem_statement: str = "") -> str:
    """
    Produces a compact text summary of a repository: file tree plus top-level 
    function/class signatures per Python file.
    
    Note: This uses a simple keyword overlap heuristic for ranking relevance.
    Embeddings-based retrieval (RAG) is a possible future improvement for better 
    semantic matching and robustness.
    """
    enc = tiktoken.get_encoding("cl100k_base")
    MAX_TOKENS = 1000
    
    keywords = extract_keywords(problem_statement)
    py_files = _get_python_files(repo_path)
    
    file_data = []
    for f in py_files:
        rel_path, sigs, docs = parse_file(f, repo_path)
        if not sigs and not docs:
            continue
            
        score = 0
        if keywords:
            # Score based on simple keyword overlap in path and docstrings
            text_to_score = (rel_path + " " + docs).lower()
            for kw in keywords:
                if kw in text_to_score:
                    score += 1
                    
        file_data.append({
            "rel_path": rel_path,
            "sigs": sigs,
            "score": score
        })
        
    # Sort by score descending, then by path length ascending
    file_data.sort(key=lambda x: (-x["score"], len(x["rel_path"])))
    
    repo_map = "Repository Map:\n\n"
    
    for data in file_data:
        file_summary = f"### {data['rel_path']}\n{data['sigs']}\n\n"
        
        # Check token count if we add this file
        current_tokens = len(enc.encode(repo_map + file_summary))
        if current_tokens > MAX_TOKENS:
            # If we hit the limit, stop adding more files
            repo_map += f"... (repo map truncated due to token limits. Use list_files or search_code to explore further) ...\n"
            break
            
        repo_map += file_summary
        
    return repo_map
