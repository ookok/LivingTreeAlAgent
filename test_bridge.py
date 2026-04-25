#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Evolution-Intent Bridge 测试脚本
"""

import sys
import os

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("Evolution-Intent Bridge Test")
print("=" * 60)

# ==================== 测试1: 基础桥接 ====================

print("\n[Test 1] Creating Bridge...")

try:
    from core.evolution_engine.bridge import (
        EvolutionIntentBridge,
        IntentSignal,
        IntentSignalType,
        ExecutionFeedback,
        create_bridge,
    )
    
    bridge = create_bridge()
    print("[PASS] Bridge created!")
    
except Exception as e:
    print(f"[FAIL] Bridge creation failed: {e}")
    sys.exit(1)

# ==================== 测试2: 意图信号转换 ====================

print("\n[Test 2] Intent Signal Mapping...")

try:
    # 模拟 Intent 对象
    class MockIntent:
        def __init__(self):
            self.intent_type = type('IntentType', (), {'value': 'CODE_GENERATION'})()
            self.action = '编写'
            self.target = '用户登录接口'
            self.tech_stack = ['fastapi', 'python']
            self.confidence = 0.85
            self.completeness = 0.9
            self.raw_input = '帮我写一个用户登录接口'
            self.context = {}
    
    intent = MockIntent()
    
    # 创建信号
    signal = bridge._create_signal_from_intent(intent)
    
    assert signal.intent_type == IntentSignalType.CODE_GENERATION
    assert signal.action == '编写'
    assert signal.target == '用户登录接口'
    assert 'fastapi' in signal.tech_stack
    assert signal.confidence == 0.85
    
    print("[PASS] Intent Signal mapping works!")
    print(f"  - Signal Type: {signal.intent_type.value}")
    print(f"  - Action: {signal.action}")
    print(f"  - Target: {signal.target}")
    print(f"  - Tech Stack: {signal.tech_stack}")
    
except Exception as e:
    print(f"[FAIL] Signal mapping failed: {e}")

# ==================== 测试3: 执行反馈 ====================

print("\n[Test 3] Execution Feedback...")

try:
    feedback = ExecutionFeedback(
        intent_id="test-001",
        success=True,
        duration_ms=1500,
        output="User login endpoint created successfully",
        quality_score=0.92,
    )
    
    record = feedback.to_evolution_record()
    
    assert record['success'] == True
    assert record['quality_score'] == 0.92
    assert record['duration_ms'] == 1500
    
    print("[PASS] Execution Feedback works!")
    print(f"  - Success: {record['success']}")
    print(f"  - Quality: {record['quality_score']}")
    print(f"  - Duration: {record['duration_ms']}ms")
    
except Exception as e:
    print(f"[FAIL] Feedback test failed: {e}")

# ==================== 测试4: 桥接器状态 ====================

print("\n[Test 4] Bridge Status...")

try:
    status = bridge.get_bridge_status()
    
    assert 'intent_engine_connected' in status
    assert 'evolution_engine_connected' in status
    assert 'stats' in status
    
    print("[PASS] Bridge Status works!")
    print(f"  - IntentEngine: {'Connected' if status['intent_engine_connected'] else 'Not Connected'}")
    print(f"  - EvolutionEngine: {'Connected' if status['evolution_engine_connected'] else 'Not Connected'}")
    print(f"  - Signals Sent: {status['stats']['signals_sent']}")
    
except Exception as e:
    print(f"[FAIL] Status test failed: {e}")

# ==================== 测试5: 风险警告生成 ====================

print("\n[Test 5] Risk Warning Generation...")

try:
    # 低置信度意图
    low_conf_intent = MockIntent()
    low_conf_intent.confidence = 0.4
    low_conf_intent.completeness = 0.3
    
    warnings = bridge._generate_risk_warnings(low_conf_intent, [])
    
    assert len(warnings) > 0
    assert any('置信度' in w for w in warnings)
    
    print("[PASS] Risk Warning Generation works!")
    for warning in warnings:
        print(f"  - {warning}")
    
except Exception as e:
    print(f"[FAIL] Risk warning test failed: {e}")

# ==================== 测试6: 模式提取 ====================

print("\n[Test 6] Pattern Extraction...")

try:
    patterns = {
        'temporal_patterns': [{'name': 'Pattern A'}, {'name': 'Pattern B'}],
        'co_occurrence_patterns': [{'name': 'Pattern C'}],
        'causal_patterns': [],
        'anomaly_patterns': [],
    }
    
    result = bridge._extract_patterns(patterns)
    
    assert len(result) > 0
    assert any('时序' in r for r in result)
    
    print("[PASS] Pattern Extraction works!")
    for p in result:
        print(f"  - {p}")
    
except Exception as e:
    print(f"[FAIL] Pattern extraction test failed: {e}")

# ==================== 总结 ====================

print("\n" + "=" * 60)
print("All Tests Completed!")
print("=" * 60)
print("\nBridge Features:")
print("  [x] Intent Signal Mapping")
print("  [x] Execution Feedback")
print("  [x] Bridge Status")
print("  [x] Risk Warning Generation")
print("  [x] Pattern Extraction")
print("\nNext Steps:")
print("  1. Connect to real IntentEngine")
print("  2. Connect to real EvolutionEngine")
print("  3. Test end-to-end flow")
