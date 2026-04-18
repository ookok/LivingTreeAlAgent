import sys
sys.path.insert(0, '.')
import ast

with open('core/config_missing_detector.py', 'r', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print('[OK] config_missing_detector.py syntax')
except SyntaxError as e:
    print(f'[FAIL] line {e.lineno}: {e.msg}')
    lines = src.split('\n')
    for i in range(max(0, e.lineno-2), min(len(lines), e.lineno+2)):
        print(f'  {i+1}: {lines[i]}')

from core.config_missing_detector import check_config_missing, ConfigMissingDetector

# Test regex-only mode (no SystemBrain)
test_cases = [
    ('OPENAI_API_KEY is missing', 'OPENAI_API_KEY', 0.95),
    ('ANTHROPIC_API_KEY not set', 'ANTHROPIC_API_KEY', 0.95),
    ('model.provider is not configured', 'model.provider', 0.85),
    ('connection refused ECONNREFUSED', None, 0.0),  # network issue, not config
    ('random unknown error', None, 0.0),
]

print('\nConfigMissingDetector Tests:')
all_pass = True
for msg, expected_key, expected_conf in test_cases:
    r = check_config_missing(msg)
    if expected_key is None:
        ok = not r.is_missing_config
    else:
        ok = r.is_missing_config and r.config_key == expected_key
    status = 'PASS' if ok else 'FAIL'
    if not ok:
        all_pass = False
    print(f'  {status}: "{msg[:35]}" -> key={r.config_key}, conf={r.confidence}, mode={r.reasoning_mode}')

if all_pass:
    print('\nAll detector tests passed')
else:
    print('\nSome tests failed')
