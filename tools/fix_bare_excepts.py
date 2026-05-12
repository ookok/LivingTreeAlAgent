import re

FILES = [
    ("livingtree/treellm/core.py", "TreeLLM core"),
    ("livingtree/capability/unified_visual_port.py", "UnifiedVisual"),
    ("livingtree/api/doc_routes.py", "DocRoutes"),
]

for filepath, label in FILES:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    count = 0
    # Pattern: except Exception:\n<indent>pass
    new_content = re.sub(
        r'except Exception:\s*\n(\s+)pass',
        rf'except Exception as e:\n\1logger.warning(f"{label}: {{e}}")',
        content,
        flags=re.MULTILINE,
    )
    count += len(re.findall(r'except Exception:\s*\n\s+pass', content))

    # Pattern: except Exception:\n<indent>return ...
    new_content = re.sub(
        r'(except Exception:\s*\n)(\s+)(return .+)',
        rf'except Exception as e:\n\2logger.warning(f"{label}: {{e}}")\n\2\3',
        new_content,
        flags=re.MULTILINE,
    )
    count += len(re.findall(r'except Exception:\s*\n\s+return', content))

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"{filepath}: fixed {count} bare excepts")
