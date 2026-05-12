"""Fix bare except blocks in high-risk files — replace silent swallows with logger.warning."""
import re

FILES = [
    ("livingtree/treellm/core.py", "TreeLLM core"),
    ("livingtree/capability/unified_visual_port.py", "UnifiedVisual"),
    ("livingtree/api/doc_routes.py", "DocRoutes"),
]

for filepath, label in FILES:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    counts = [0, 0]  # [pass+continue, return]

    # Fix 1: except Exception:\n<indent>pass  →  logger.warning
    def fix_pass(m, cnt=counts):
        indent = m.group(1)
        cnt[0] += 1
        return 'except Exception as e:\n' + indent + 'logger.warning("{}: {}".format("' + label + '", e))'

    content = re.sub(
        r'except Exception:\s*\n(\s+)pass\b',
        fix_pass,
        content
    )

    # Fix 2: except Exception:\n<indent>continue  →  logger.warning + continue
    def fix_cont(m, cnt=counts):
        indent = m.group(1)
        cnt[0] += 1
        return 'except Exception as e:\n' + indent + 'logger.warning("{}: {}".format("' + label + '", e))\n' + indent + 'continue'

    content = re.sub(
        r'except Exception:\s*\n(\s+)continue\b',
        fix_cont,
        content
    )

    # Fix 3: except Exception:\n<indent>return ...  →  logger.warning + return
    def fix_ret(m, cnt=counts):
        indent = m.group(1)
        stmt = m.group(2)
        cnt[1] += 1
        return 'except Exception as e:\n' + indent + 'logger.warning("{}: {}".format("' + label + '", e))\n' + indent + stmt

    content = re.sub(
        r'except Exception:\s*\n(\s+)(return .+)',
        fix_ret,
        content
    )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(filepath + ": " + str(counts[0]) + " pass/continue + " + str(counts[1]) + " return -> logger.warning")
