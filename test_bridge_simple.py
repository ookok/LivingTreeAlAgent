#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bridge Test - Simple Version
"""

import sys
print("[1] Starting...")

try:
    print("[2] Importing bridge module...")
    from core.evolution_engine.bridge import (
        EvolutionIntentBridge,
        IntentSignal,
        IntentSignalType,
        ExecutionFeedback,
        create_bridge,
    )
    print("[PASS] Import successful!")
except Exception as e:
    print(f"[FAIL] Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("[3] Creating bridge...")
try:
    bridge = create_bridge()
    print("[PASS] Bridge created!")
except Exception as e:
    print(f"[FAIL] Bridge creation failed: {e}")
    sys.exit(1)

print("[4] Testing IntentSignal...")
try:
    signal = IntentSignal(
        query="test query",
        intent_type=IntentSignalType.CODE_GENERATION,
        action="编写",
        target="登录接口",
        tech_stack=["fastapi"],
        confidence=0.9,
        completeness=0.8,
    )
    print(f"[PASS] Signal created: {signal.intent_type.value}")
except Exception as e:
    print(f"[FAIL] Signal test failed: {e}")
    sys.exit(1)

print("[5] Testing ExecutionFeedback...")
try:
    feedback = ExecutionFeedback(
        intent_id="test-001",
        success=True,
        duration_ms=1000,
        output="Done",
    )
    record = feedback.to_evolution_record()
    print(f"[PASS] Feedback created: success={record['success']}")
except Exception as e:
    print(f"[FAIL] Feedback test failed: {e}")
    sys.exit(1)

print("[6] Testing bridge status...")
try:
    status = bridge.get_bridge_status()
    print(f"[PASS] Status: {status}")
except Exception as e:
    print(f"[FAIL] Status test failed: {e}")
    sys.exit(1)

print("\n=== All Tests Passed! ===")
