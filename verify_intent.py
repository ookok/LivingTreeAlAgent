# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'F:\mhzyapp\LivingTreeAlAgent\core')
from intent_engine_core import IntentEngine, IntentType

engine = IntentEngine()

tests = [
    ("帮我写一个用户登录函数", IntentType.CODE_GENERATION),
    ("修复这个bug: index out of range", IntentType.BUG_FIX),
    ("重构这段代码", IntentType.REFACTORING),
    ("优化一下这个类", IntentType.REFACTORING),
    ("查找所有用户相关的函数", IntentType.QUERY),
]

passed = 0
for query, expected in tests:
    intent = engine.parse(query)
    ok = intent.intent_type == expected
    status = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    print(f"[{status}] {query}")
    print(f"  Expected: {expected.value}, Got: {intent.intent_type.value}")

print(f"\n{passed}/{len(tests)} passed")
