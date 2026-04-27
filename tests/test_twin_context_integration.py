# -*- coding: utf-8 -*-
"""
数字分身上下文集成测试
"""

import sys
import time

# Direct execution
exec(open('core/twin_context_integration.py', encoding='utf-8').read())

print("=" * 60)
print("[TEST] Twin Context Integration - Phase 2")
print("=" * 60)

# ============================================================================
# Test 1: Create Manager
# ============================================================================
print("\n[Test 1] Create Twin Context Manager")
print("-" * 40)

manager = TwinContextManager(twin_id="twin_001", user_id="user_001")
print(f"  Created manager for twin: {manager.twin_id}")
print(f"  Has compressor: {HAS_COMPRESSOR}")
print(f"  Has verifier: {HAS_VERIFIER}")
print(f"  Has indexer: {HAS_INDEXER}")

# ============================================================================
# Test 2: Memory Management
# ============================================================================
print("\n[Test 2] Memory Management")
print("-" * 40)

# Add memories
memory1 = manager.add_memory(
    memory_type="code_style",
    content="使用现代 Python 类型注解",
    context_pattern="python",
    tags=["python", "modern", "typing"]
)
print(f"  Added memory 1: {memory1.memory_id[:8]}...")

memory2 = manager.add_memory(
    memory_type="context_preference",
    content="简洁压缩优先",
    context_pattern="quick",
    tags=["compression", "fast"]
)
print(f"  Added memory 2: {memory2.memory_id[:8]}...")

# Get memories
all_memories = manager.get_memories()
print(f"  Total memories: {len(all_memories)}")

python_memories = manager.get_memories(memory_type="code_style")
print(f"  Code style memories: {len(python_memories)}")

# ============================================================================
# Test 3: Context Processing
# ============================================================================
print("\n[Test 3] Context Processing")
print("-" * 40)

test_context = """
# 用户认证系统

这是一个用户认证系统的实现文档。

## 功能
- 用户注册
- 用户登录
- 密码重置
- 权限管理

## 代码

```python
from typing import Optional
import bcrypt

class AuthService:
    def __init__(self, db):
        self.db = db
    
    async def authenticate(self, username: str, password: str) -> Optional[User]:
        '''用户认证'''
        pass
```
"""

query = "帮我创建一个用户认证系统"
result = manager.process_context(query, test_context, "")

print(f"  Processed context:")
print(f"    Intent type: {result['intent_signature'].get('type', 'unknown')}")
print(f"    Compressed length: {len(result['compressed'])} chars")
print(f"    Memories used: {len(result['memories_used'])}")
print(f"    Success: {result['success']}")

if result['verification_report']:
    print(f"    Verification: {result['verification_report']['status']}")

# ============================================================================
# Test 4: Quick Process
# ============================================================================
print("\n[Test 4] Quick Process")
print("-" * 40)

quick_result = manager.quick_process(
    "创建一个登录函数",
    "很长的上下文内容..." * 50
)
print(f"  Quick processed length: {len(quick_result)} chars")

# ============================================================================
# Test 5: Memory Recall
# ============================================================================
print("\n[Test 5] Memory Recall")
print("-" * 40)

# Add more specific memories
manager.add_memory(
    memory_type="intent_pattern",
    content="创建用户管理类",
    context_pattern="create_user_manager",
    tags=["create", "user", "class"]
)

# Record usage for some memories
for memory in manager.memories.values():
    memory.record_usage(True)
    memory.record_usage(True)
    memory.record_usage(False)

# Find relevant memories
relevant = manager._find_relevant_memories(
    "帮我创建一个用户管理类",
    {"type": "create"}
)
print(f"  Found {len(relevant)} relevant memories")
for m in relevant[:3]:
    print(f"    - {m.memory_type}: {m.success_rate:.1%} success")

# ============================================================================
# Test 6: Suggestions
# ============================================================================
print("\n[Test 6] Context Suggestions")
print("-" * 40)

suggestions = manager.suggest_context_improvements("创建一个新的模块")
print(f"  Suggestions ({len(suggestions)}):")
for s in suggestions:
    print(f"    - {s}")

# ============================================================================
# Test 7: Learning
# ============================================================================
print("\n[Test 7] Learning System")
print("-" * 40)

# Process some contexts to trigger learning
for i in range(6):
    manager.process_context(
        f"任务 {i}",
        f"上下文内容 {i}...",
        ""
    )

print(f"  Learning records: {len(manager.learning_records)}")
print(f"  Memory count: {len(manager.memories)}")

# ============================================================================
# Test 8: Feedback Learning
# ============================================================================
print("\n[Test 8] Feedback Learning")
print("-" * 40)

# Get initial preference
initial_ratio = manager.preference.preferred_compression_ratio

# Learn from feedback
manager.learn_from_feedback(
    manager.learning_records[0].record_id if manager.learning_records else "",
    "context was too verbose",
    "partial"
)

new_ratio = manager.preference.preferred_compression_ratio
print(f"  Compression ratio: {initial_ratio:.2f} -> {new_ratio:.2f}")

# ============================================================================
# Test 9: Stats
# ============================================================================
print("\n[Test 9] Statistics")
print("-" * 40)

summary = manager.get_context_summary()
print(f"  Total processed: {summary['stats']['total_processed']}")
print(f"  Successful: {summary['stats']['successful_compressions']}")
print(f"  Memory hits: {summary['stats']['memory_hits']}")
print(f"  Learning updates: {summary['stats']['learning_updates']}")

# ============================================================================
# Test 10: Factory
# ============================================================================
print("\n[Test 10] Twin Context Factory")
print("-" * 40)

factory = TwinContextFactory()

# Create multiple managers
m1 = factory.create_manager("twin_A", "user_X")
m2 = factory.create_manager("twin_B", "user_Y")
m3 = factory.get_or_create("twin_A", "user_X")  # Should return existing

print(f"  Created managers: {len(factory.list_managers())}")
print(f"  twin_A is same instance: {m1 is m3}")

# Delete one
factory.delete_manager("twin_B")
print(f"  After delete: {len(factory.list_managers())}")

# ============================================================================
# Test 11: Serialization
# ============================================================================
print("\n[Test 11] Serialization")
print("-" * 40)

# Add some data
factory.get_or_create("twin_saved", "user_saved")
factory.get_or_create("twin_saved", "user_saved").add_memory(
    "code_style", "Test style", "test", ["test"]
)

# Export to dict
data = factory.get_or_create("twin_saved", "user_saved").to_dict()
print(f"  Exported data keys: {list(data.keys())}")
print(f"  Memory count: {len(data['memories'])}")
print(f"  Stats: {data['stats']['total_processed']}")

# Recreate from dict
restored = TwinContextManager.from_dict(data)
print(f"  Restored twin_id: {restored.twin_id}")
print(f"  Restored memories: {len(restored.memories)}")

# ============================================================================
# Test 12: Convenience Functions
# ============================================================================
print("\n[Test 12] Convenience Functions")
print("-" * 40)

# Reset factory
_twin_context_factory = TwinContextFactory()

result = quick_process("quick_twin", "测试查询", "测试上下文...")
print(f"  quick_process result length: {len(result)}")

full = full_process("full_twin", "创建用户类", "代码上下文...", "class Code: pass")
print(f"  full_process success: {full['success']}")
print(f"  full_process intent: {full['intent_signature'].get('type', 'N/A')}")

add_twin_memory("memory_twin", "test_type", "test content", "test_pattern", ["tag1"])
print(f"  Added memory via convenience function")

final_manager = get_twin_context_factory().get_manager("memory_twin")
print(f"  Found memory twin: {final_manager is not None}")
print(f"  Memory twin memories: {len(final_manager.memories)}")

# ============================================================================
# Test 13: Preferences
# ============================================================================
print("\n[Test 13] Preferences")
print("-" * 40)

pref = manager.preference
print(f"  Compression ratio: {pref.preferred_compression_ratio}")
print(f"  Intent preservation: {pref.min_intent_preservation}")
print(f"  Enable syntax check: {pref.enable_syntax_check}")
print(f"  Preferred languages: {pref.preferred_languages}")

# Modify preferences
pref.preferred_compression_ratio = 0.6
pref.preferred_languages = ["python", "go"]
print(f"  Updated compression ratio: {pref.preferred_compression_ratio}")

print("\n" + "=" * 60)
print("[OK] All tests completed!")
print("=" * 60)
