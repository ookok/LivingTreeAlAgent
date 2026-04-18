import sys, ast
sys.path.insert(0, '.')
with open('core/ai_reasoning_engine.py', 'r', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print('[OK] ai_reasoning_engine.py syntax')
except SyntaxError as e:
    print(f'[FAIL] line {e.lineno}: {e.msg}')

from core.ai_reasoning_engine import AIReasoningEngine, ReasoningResult, _fast_match
print('[OK] module import')

# Test fast_match
test_cases = [
    'OPENAI_API_KEY is missing',
    'ANTHROPIC_API_KEY not set',
    'connection refused to localhost:11434',
    'no .env file found',
    'model.provider is not configured',
    'random unrelated error',
]
print('Fast Match Tests:')
for tc in test_cases:
    r = _fast_match(tc)
    if r:
        print(f'  "{tc[:40]}" -> {r.inferred_config_key} (conf={r.confidence})')
    else:
        print(f'  "{tc[:40]}" -> NO MATCH')

# Test AIReasoningEngine (without SystemBrain - will use fast_match only)
engine = AIReasoningEngine()
result = engine.reason_about_error('OPENAI_API_KEY is missing')
print(f'\nEngine test: {result.inferred_config_key}, mode={result.reasoning_mode}, conf={result.confidence}')

print('\nAll tests passed')
