# -*- coding: utf-8 -*-
"""
?????????

?? L1 ???? / L2 ???? / L3 ????
"""

import sys
import time

# ??????
exec(open('core/three_level_verification.py', encoding='utf-8').read())

print("=" * 60)
print("[TEST] Three Level Verification Pipeline")
print("=" * 60)

# ============================================================================
# ?? L1: ????
# ============================================================================
print("\n[DOC] L1 ??????")
print("-" * 40)

l1 = L1SyntaxValidator()

# ??1: ??????
good_context = """
# ??????

## ??

- ????
- ????
- ????

## ????

```python
class UserManager:
    def __init__(self, db):
        self.db = db
    
    async def register(self, username: str, email: str) -> User:
        pass
    
    async def login(self, username: str, password: str) -> Optional[User]:
        pass
```

## ????

?????????
"""

result = l1.validate(good_context, {})
print(f"  [OK] ?????: {result.status.value} - {result.message}")

# ??2: ???????
bad_context = """
```python
def broken_function(x
    return x * 2

[???????
"""

result = l1.validate(bad_context, {})
print(f"  [X] ?????: {result.status.value} - {result.message}")
if result.details.get('errors'):
    for err in result.details['errors']:
        print(f"     - {err}")

# ??3: ???????
warning_context = """
??????????

[???]()
[??????]()

```javascript
function test() {
    console.log('hello');
}
```

????: C:\\Users\\test\\
"""

result = l1.validate(warning_context, {})
print(f"  [!] ?????: {result.status.value} - {result.message}")

# ============================================================================
# ?? L2: ????
# ============================================================================
print("\n[STAT] L2 ??????")
print("-" * 40)

l2 = L2SemanticValidator()

# ????
intent_sig = {
    "type": "create",
    "action": "??",
    "target": "?????",
    "constraints": ["??", "??"],
    "code_signatures": []
}

# ??1: ??????????
good_semantic = """
?????????????
1. ?????
2. ?????

???????????
- register(username, email): ????
- login(username, password): ????
- logout(): ????

???????????
"""

result = l2.validate(good_semantic, intent_sig, "???????????????????????")
print(f"  [OK] ????: {result.status.value}")
print(f"     ?????: {result.details.get('intent_preservation', 0):.1%}")

# ??2: ????????
lost_semantic = """
??????????????

???????
- ??????
- ????
- ????
"""

result = l2.validate(lost_semantic, intent_sig, "???????????")
print(f"  [X] ????: {result.status.value}")
print(f"     ?????: {result.details.get('intent_preservation', 0):.1%}")
if result.details.get('issues'):
    for issue in result.details['issues']:
        print(f"     - {issue}")

# ============================================================================
# ?? L3: ????
# ============================================================================
print("\n[CHAIN] L3 ??????")
print("-" * 40)

l3 = L3IntegrationValidator()

# ??1: ?????
good_imports = """
```python
from typing import Optional, List
from dataclasses import dataclass
import json
import os

class UserService:
    def __init__(self):
        self.db = Database()
    
    def get_user(self, user_id: int) -> Optional[User]:
        pass
```
"""

result = l3.validate(good_imports, {})
print(f"  [OK] ????: {result.status.value} - {result.message}")

# ??2: ??????
bad_imports = """
```python
from flask import Flask
from sqlalchemy import create_engine
import pandas as pd
from custom_module import UserManager  # ??????
from another_missing import Service

def main():
    call_undefined_function()
"""
# ?? requirements.txt ??

result = l3.validate(bad_imports, {})
print(f"  [!] ????: {result.status.value}")
if result.details.get('issues'):
    for issue in result.details['issues']:
        print(f"     - {issue}")

# ============================================================================
# ???????
# ============================================================================
print("\n? ???????")
print("-" * 40)

pipeline = ThreeLevelVerificationPipeline()

full_context = """
# ??????

## ??
???????????????

## ??
- ??????? < 100ms
- ????? bcrypt ??
- ????????

## ??

```python
from typing import Optional
import bcrypt
from dataclasses import dataclass

@dataclass
class User:
    username: str
    email: str

class AuthService:
    def __init__(self, db):
        self.db = db
    
    async def authenticate(self, username: str, password: str) -> Optional[User]:
        '''????'''
        pass
    
    def hash_password(self, password: str) -> str:
        '''????'''
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
```

## ??

?? `config.json`:
```json
{
    "database": "sqlite:///auth.db",
    "secret_key": "${SECRET_KEY}"
}
```
"""

intent_sig = {
    "type": "create",
    "action": "??",
    "target": "??????",
    "constraints": ["??", "??", "??"],
    "code_signatures": ["AuthService", "User"]
}

report = pipeline.verify(
    context=full_context,
    intent_signature=intent_sig,
    original_query="?????????????????????"
)

print(f"\n  [REPORT] ????:")
print(f"     ????: {report.overall_status.value}")
print(f"     ???: {report.total_duration_ms:.1f}ms")
print(f"     ??: {report.get_summary()}")

print(f"\n  [STAT] ????:")
for level, results in report.level_results.items():
    print(f"     [{level.value}]")
    for r in results:
        icon = {"PASSED": "[OK]", "FAILED": "[X]", "WARNING": "[!]"}.get(r.status.value, "?")
        print(f"        {icon} {r.name}: {r.message} ({r.duration_ms:.1f}ms)")

if report.recommendations:
    print(f"\n  [IDEA] ??:")
    for rec in report.recommendations:
        print(f"     - {rec}")

# ============================================================================
# Mock Compression Pipeline Test
# ============================================================================
print("\n[COMPRESS+VERIFY PIPELINE]")
print("-" * 40)

# Simple mock compressor
class MockCompressor:
    def __init__(self, max_tokens=300):
        self.max_tokens = max_tokens
    
    def compress(self, query, context, code):
        # Simple compression: just return a summary
        return {
            "compressed": f"Compressed context for: {query[:50]}...\n\nCode signatures extracted.\n\nContext summary: {context[:100]}",
            "intent_signature": {
                "type": "create",
                "action": "create",
                "target": "user_manager",
                "constraints": ["performance", "security"],
                "code_signatures": ["UserManager", "register", "login"]
            }
        }

compressor = MockCompressor(max_tokens=300)
verifier = ThreeLevelVerificationPipeline()
verified_pipeline = VerifiedCompressionPipeline(compressor, verifier)

# ????
original_code = """
class UserManager:
    def __init__(self, db_connection):
        self.db = db_connection
        self.cache = {}
        self.logger = Logger()
    
    async def register(self, username: str, email: str, password: str) -> User:
        # 100?????...
        user = User(username, email)
        hashed = self.hash_password(password)
        # ??????...
        self.cache[user.id] = user
        return user
    
    async def login(self, username: str, password: str) -> Optional[User]:
        # 50?????...
        user = self.db.find_user(username)
        if self.verify_password(password, user.password_hash):
            return user
        return None
    
    def _internal_cache_update(self, user_id: int):
        # 20?????...
        pass
"""

result = verified_pipeline.compress_and_verify(
    query="???????????????????",
    context="??????????",
    code=original_code
)

print(f"  [OK] ??????:")
print(f"     ??: {result['success']}")
print(f"     ?????: {len(result['compressed'])} ??")
print(f"     ????: {result['verification_report']['overall_status']}")

if result['intent_signature']:
    print(f"     ????: {result['intent_signature'].get('type', 'unknown')}")
    print(f"     ??: {result['intent_signature'].get('action', 'unknown')}")

print(f"\n  [FILE] ??????:")
print(f"  {result['compressed'][:200]}...")

# ============================================================================
# ??????
# ============================================================================
print("\n[FAST] ??????")
print("-" * 40)

is_valid, msg = quick_verify("????????")
print(f"  ????: {'[OK]' if is_valid else '[X]'} {msg}")

is_valid, msg = quick_verify("```python\ndef broken(")
print(f"  ????: {'[OK]' if is_valid else '[X]'} {msg}")

print("\n" + "=" * 60)
print("[OK] ??????!")
print("=" * 60)
