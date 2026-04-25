#!/usr/bin/env python3
"""验证 BaseIntentEngine 独立工作（模板方法模式）"""
import sys
sys.path.insert(0, "client/src")

from client.src.business.base_intent_engine import BaseIntentEngine, IntentResult, IntentType, IntentPriority

# 子类实现 do_parse
class MyIntentEngine(BaseIntentEngine):
    def do_parse(self, text):
        # 简单实现：检测关键词
        text_lower = text.lower()
        if "生成" in text or "create" in text_lower or "write" in text_lower:
            intent_type = IntentType.CODE_GENERATION
        elif "修复" in text or "fix" in text_lower or "debug" in text_lower:
            intent_type = IntentType.BUG_FIX
        elif "解释" in text or "explain" in text_lower:
            intent_type = IntentType.EXPLANATION
        else:
            intent_type = IntentType.UNKNOWN
        
        return IntentResult(
            intent_type=intent_type,
            confidence=0.85,
            priority=IntentPriority.P2_MEDIUM,
            raw_text=text,
        )

# 测试 1: 基本解析
engine = MyIntentEngine(enable_cache=True, cache_size=10)
result = engine.parse("帮我生成一个登录接口")
assert result is not None, "解析返回 None"
assert result.intent_type == IntentType.CODE_GENERATION, f"意图类型错误: {result.intent_type}"
print(f"[PASS] 测试1: 基本解析 ({result.intent_type.value})")

# 测试 2: 缓存
result2 = engine.parse("帮我生成一个登录接口")
assert engine.cache_hits == 1, f"缓存未命中: {engine.cache_hits}"
print(f"[PASS] 测试2: 缓存命中 (hits={engine.cache_hits})")

# 测试 3: 不同文本不走缓存
result3 = engine.parse("帮我修复一个 bug")
assert result3.intent_type == IntentType.BUG_FIX, f"意图类型错误: {result3.intent_type}"
print(f"[PASS] 测试3: 不同文本 ({result3.intent_type.value})")

# 测试 4: explain 意图
result4 = engine.parse("请解释一下这段代码")
assert result4.intent_type == IntentType.EXPLANATION, f"意图类型错误: {result4.intent_type}"
print(f"[PASS] 测试4: 解释意图 ({result4.intent_type.value})")

# 测试 5: 统计信息
stats = engine.get_stats()
assert "total_parsed" in stats, "统计信息缺失"
assert stats["total_parsed"] == 3, f"解析计数错误: {stats['total_parsed']}"
print(f"[PASS] 测试5: 统计信息 ({stats})")

# 测试 6: IntentResult.to_dict()
d = result.to_dict()
assert "intent_type" in d, "to_dict 缺失字段"
assert d["intent_type"] == "code_generation", f"to_dict 值错误: {d['intent_type']}"
print("[PASS] 测试6: IntentResult.to_dict()")

# 测试 7: 禁用缓存
engine_no_cache = MyIntentEngine(enable_cache=False)
result7 = engine_no_cache.parse("测试")
assert engine_no_cache.cache_hits == 0, "缓存未禁用"
print("[PASS] 测试7: 禁用缓存")

print("\n[OK] BaseIntentEngine 验证通过")
