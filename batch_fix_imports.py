#!/usr/bin/env python3
"""WARNING: use with caution. Removes ALL try/except ImportError blocks.
Makes every import a hard dependency."""
import re
from pathlib import Path

ROOT = Path("livingtree")
count = 0

# Pattern: try:\n<whitespace>import/from ... \nexcept ImportError:\n<whitespace>(pass|X = None)
FULL_RE = re.compile(
    r'try:\s*\n(\s+)(?:import [^\n]+|from [^\n]+)\s*\n\s*except ImportError\s*:\s*\n\s*(?:pass|\w+\s*=\s*(?:None|False))\s*',
    re.MULTILINE
)

for pyfile in sorted(ROOT.rglob("**/*.py")):
    if "__pycache__" in str(pyfile):
        continue
    original = pyfile.read_text(encoding="utf-8")
    
    def replacer(m):
        body = m.group(0)
        # Extract the import line
        import_match = re.search(r'^\s+(import .+|from .+)', body, re.MULTILINE)
        if import_match:
            return import_match.group(1) + "\n"
        return body
    
    new_content = FULL_RE.sub(replacer, original)
    
    if new_content != original:
        pyfile.write_text(new_content, encoding="utf-8")
        count += 1
        print(f"OK {pyfile}")

print(f"\n{count} files modified")
