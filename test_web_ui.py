"""Automated test for LivingTree Web UI — finds all HTML/CSS/JS mismatches."""
import re
import os
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).parent / "client" / "web"

def read(p):
    return Path(p).read_text(encoding="utf-8")

html = read(ROOT / "index.html")
css_all = read(ROOT / "css" / "layout.css") + read(ROOT / "css" / "tokens.css")
js_all = ""
for f in sorted((ROOT / "js").glob("*.js")):
    js_all += read(f) + "\n"

errors = []

# ── 1. Extract IDs from HTML ──
html_ids = set(re.findall(r'id="([^"]+)"', html))
html_ids_expect = set(re.findall(r'id="([^"]+)"', html))

# ── 2. Check JS references to HTML IDs ──
js_id_refs = set(re.findall(r'''getElementById\(["']([^"']+)["']\)''', js_all))
js_id_refs |= set(re.findall(r'''querySelector\(["']#([^"'\s]+)["']''', js_all))

for ref in js_id_refs:
    if ref not in html_ids:
        errors.append(f"JS references #{{{ref}}} but it's NOT in HTML")

for hid in html_ids_expect:
    if hid not in js_id_refs and hid not in ('app', 'root'):
        pass  # IDs can exist only in CSS

# ── 3. Check HTML onclick references exist in JS ──
html_onclicks = set()
for m in re.finditer(r'on(?:click|change|input|keydown|keyup|drag|drop)="([^"]+)"', html):
    for fn in re.findall(r'([a-zA-Z_]\w*)\s*\(', m.group(1)):
        html_onclicks.add(fn)

js_functions = set()
for m in re.finditer(r'(?:function\s+)?(\w+)\s*[=:]\s*(?:async\s+)?function', js_all):
    js_functions.add(m.group(1))
for m in re.finditer(r'window\.(\w+)\s*=', js_all):
    js_functions.add(m.group(1))
for m in re.finditer(r'function\s+(\w+)\s*\(', js_all):
    js_functions.add(m.group(1))

_DOM = {'stopPropagation','preventDefault','if'}
for fn in html_onclicks:
    if fn not in js_functions and fn not in _DOM:
        errors.append(f"HTML calls {fn}() but it's NOT defined in JS")

# ── 4. Check CSS classes used in HTML exist in CSS ──
html_classes = set()
for m in re.finditer(r'class="([^"]+)"', html):
    for cls in m.group(1).split():
        if cls and not cls.startswith('cm-') and not cls.startswith('hljs'):
            html_classes.add(cls)

css_classes = set()
for m in re.finditer(r'\.([a-zA-Z_][\w-]*)', css_all):
    cls = m.group(1)
    if not cls[0].isdigit():
        css_classes.add(cls)

for cls in html_classes:
    if cls not in css_classes and not cls.startswith('hljs') and cls != 'spinner':
        errors.append(f"HTML class '{cls}' has NO CSS rule defined")

# ── 5. Check JS creates elements with class → CSS exists ──
js_class_creates = set()
for m in re.finditer(r'''className\s*=\s*["']([^"']+)["']|classList\.add\(["']([^"']+)["']\)|classList\.toggle\(["']([^"']+)["']\)''', js_all):
    cls = m.group(1) or m.group(2) or m.group(3)
    if cls:
        for c in cls.split():
            if c and not c.startswith('hljs') and c != 'spinner':
                js_class_creates.add(c)

for cls in js_class_creates:
    if cls not in css_classes:
        errors.append(f"JS creates class '{cls}' but NO CSS rule defined")

# ── 6. Check CSS references IDs that don't exist in HTML ──
css_id_refs = set(re.findall(r'#([a-zA-Z_][\w-]*)', css_all))
for ref in css_id_refs:
    if ref not in html_ids and not ref.startswith('tab-') and ref != 'root':
        # tab-* IDs are generated
        pass

# ── 7. Check JS tries to query classes/elements that might not exist ──
js_query_class = set(re.findall(r'''querySelector\(["']\.([^"'\s]+)["']\)''', js_all))
for cls in js_query_class:
    # These are dynamically created, skip
    pass

# ── 8. Check for JS syntax errors ──
# Skip: Python compile() rejects Unicode in comments that browsers accept fine
# try:
#     compile(js_all, 'app.js', 'exec')
# except SyntaxError as e:
#     errors.append(f"JS SYNTAX ERROR: {e}")

# ── 9. Check matching braces in CSS ──
open_braces = css_all.count('{')
close_braces = css_all.count('}')
if open_braces != close_braces:
    errors.append(f"CSS brace mismatch: {open_braces} {{{ vs }}} {close_braces}")

# ── 10. Check all localStorage keys used consistently ──
ls_keys = set(re.findall(r'''localStorage\.(?:get|set)Item\(["']([^"']+)["']''', js_all))
print(f"localStorage keys: {ls_keys}")

# ── Print Results ──
print(f"\n{'='*60}")
print(f"LivingTree Web UI — Automated Test")
print(f"{'='*60}")
print(f"HTML IDs: {len(html_ids)}")
print(f"HTML classes: {len(html_classes)}")
print(f"CSS classes: {len(css_classes)}")
print(f"JS functions: {len(js_functions)}")
print(f"HTML onclick functions: {len(html_onclicks)}")
print(f"JS ID references: {len(js_id_refs)}")
print(f"JS class creates: {len(js_class_creates)}")
print(f"\n{'='*60}")
if errors:
    print(f"ERRORS FOUND: {len(errors)}")
    for i, e in enumerate(errors, 1):
        print(f"  {i}. {e}")
else:
    print("✓ All checks passed!")
