#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智能诊断系统测试
================

测试模块：
1. StructuredLogger - 结构化日志
2. ErrorClassifier - 错误分类
3. DiagnosisEngine - 诊断引擎
4. AutoFixSystem - 自动修复
5. NLGGenerator - 自然语言生成
6. TaskMonitor - 任务监控
7. Dashboard - 仪表板

Usage:
    python test_intelligent_diagnosis.py
"""

import sys
import os
import time
import traceback

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.intelligent_diagnosis import (
    # 结构化日志
    StructuredLogger,
    LogLevel,
    ErrorCategory,
    get_logger,
    generate_trace_id,
    # 错误分类
    ErrorClassifier,
    classify_error,
    # 诊断引擎
    DiagnosisEngine,
    DiagnosisResult,
    get_diagnosis_engine,
    # 自动修复
    AutoFixSystem,
    FixStrategy,
    get_fix_system,
    # 自然语言生成
    NLGGenerator,
    UserLevel,
    generate_user_friendly_error,
    # 任务监控
    TaskMonitor,
    HealthStatus,
    get_task_monitor,
    # 仪表板
    DiagnosisDashboard,
    generate_dashboard_html,
)


class TestRunner:
    """测试运行器"""

    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0

    def test(self, name: str, func):
        """运行单个测试"""
        try:
            print(f"\n[Test] {name}")
            result = func()
            if result is None or result is True:
                print(f"  [PASS]")
                self.passed += 1
                return True
            elif isinstance(result, dict) and result.get("skip"):
                print(f"  [SKIP]: {result.get('reason', '')}")
                return None
            else:
                print(f"  [FAIL]: {result}")
                self.failed += 1
                return False
        except Exception as e:
            print(f"  [ERROR]: {e}")
            self.failed += 1
            return False

    def summary(self):
        """打印测试摘要"""
        total = self.passed + self.failed
        print("\n" + "=" * 60)
        print(f"测试结果: {self.passed}/{total} 通过")
        if self.failed > 0:
            print(f"失败: {self.failed}")
        print("=" * 60)
        return self.failed == 0


def test_structured_logger():
    """测试结构化日志"""
    logger = get_logger("test")

    # 基本日志
    logger.info("Test info message")
    logger.debug("Test debug message")
    logger.warn("Test warning message")

    # 错误日志
    logger.error(
        "Connection timeout",
        error_code="NET_001",
        error_category=ErrorCategory.NETWORK,
        diagnosis={
            "probable_cause": "网络不稳定",
            "confidence": 0.85,
            "suggested_fix": "检查网络连接",
            "auto_fix_possible": True
        }
    )

    # 用户层日志
    logger.log_user(
        level="ERROR",
        user_message="无法连接到AI服务，请检查网络连接",
        system_context={"host": "127.0.0.1"},
        recovery_action="系统将自动尝试重连"
    )

    # 追踪ID
    trace_id = generate_trace_id()
    print(f"  Generated trace_id: {trace_id}")

    return True


def test_error_classifier():
    """测试错误分类"""
    classifier = ErrorClassifier()

    test_cases = [
        ("Connection timeout after 5000ms", ErrorCategory.NETWORK, "timeout"),
        ("Out of memory error", ErrorCategory.RESOURCE, "memory"),
        ("Permission denied: /etc/config", ErrorCategory.PERMISSION, "permission"),
        ("Model load failed", ErrorCategory.AI_MODEL, "model"),
        ("Context length exceeded", ErrorCategory.AI_CONTEXT, "context"),
    ]

    all_passed = True
    for msg, expected_cat, expected_sub in test_cases:
        result = classifier.classify(msg)
        if result.category != expected_cat:
            print(f"    Expected {expected_cat.value}, got {result.category.value}")
            all_passed = False
        else:
            print(f"  ✓ '{msg[:30]}...' -> {result.category.value}/{result.subcategory}")

    # 统计
    stats = classifier.get_statistics()
    print(f"  Classification stats: {stats}")

    return all_passed


def test_diagnosis_engine():
    """测试诊断引擎"""
    engine = get_diagnosis_engine()

    # 测试诊断
    error_entry = {
        "message": "Connection timeout after 5000ms",
        "error_code": "NET_001",
        "error_category": "NETWORK",
        "context": {"host": "127.0.0.1", "port": 11434}
    }

    result = engine.diagnose(error_entry)

    print(f"  Error Code: {result.error_code}")
    print(f"  Category: {result.error_category.value}")
    print(f"  Cause: {result.probable_cause}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Suggested Fix: {result.suggested_fix}")
    print(f"  Auto-fix: {result.auto_fix_possible}")
    print(f"  Pattern Match: {result.pattern_match}")

    # 学习
    engine.learn_from_fix(error_entry, "retry", True)

    # 统计
    stats = engine.get_statistics()
    print(f"  Engine stats: {stats}")

    return True


def test_auto_fix_system():
    """测试自动修复系统"""
    fix_system = get_fix_system()

    # 创建诊断结果
    from .diagnosis_engine import ConfidenceLevel
    diagnosis = DiagnosisResult(
        error_code="RES_003",
        error_category=ErrorCategory.RESOURCE,
        probable_cause="磁盘空间不足",
        confidence=0.85,
        confidence_level=ConfidenceLevel.HIGH,
        suggested_fix="清理缓存文件",
        auto_fix_possible=True
    )

    # 检查是否可自动修复
    can_fix = fix_system.can_auto_fix(diagnosis)
    print(f"  Can auto fix: {can_fix}")

    needs_confirm, risk = fix_system.needs_confirmation(diagnosis)
    print(f"  Needs confirm: {needs_confirm}, Risk: {risk}")

    # 获取建议的修复动作
    actions = fix_system.get_fix_actions(diagnosis)
    print(f"  Suggested actions: {[a.strategy.value for a in actions]}")

    # 执行修复
    result = fix_system.fix(diagnosis, skip_confirmation=True)
    print(f"  Fix success: {result.success}")
    print(f"  Action taken: {result.action_taken}")
    print(f"  Duration: {result.fix_duration:.2f}s")

    return True


def test_nlg_generator():
    """测试自然语言生成"""
    generator = NLGGenerator()

    error_entry = {
        "message": "Connection timeout after 5000ms to 127.0.0.1:11434",
        "error_code": "NET_001",
        "error_category": "NETWORK",
        "trace_id": "tr_abc123",
        "context": {"host": "127.0.0.1", "port": 11434},
        "diagnosis": {
            "probable_cause": "网络不稳定",
            "suggested_fix": "检查网络连接",
            "auto_fix_possible": True
        }
    }

    print("\n  --- 不同用户级别的描述 ---")

    for level in UserLevel:
        desc = generator.generate(error_entry, level)
        print(f"\n  [{level.value.upper()}]")
        for line in desc.split('\n')[:3]:  # 只显示前3行
            print(f"    {line}")

    # 恢复消息
    recovery_msg = generator.generate_recovery_message(True, "Retry succeeded", UserLevel.NOVICE)
    print(f"\n  Recovery message: {recovery_msg}")

    return True


def test_task_monitor():
    """测试任务监控"""
    monitor = TaskMonitor()
    monitor.start()

    # 注册任务
    task_id = monitor.register_task(
        "test_task_1",
        "测试任务",
        expected_duration=5
    )
    print(f"  Registered task: {task_id}")

    # 模拟任务执行
    for i in range(6):
        monitor.update_progress(task_id, i * 20)
        time.sleep(0.3)

    # 创建检查点
    monitor.create_checkpoint(task_id, b"checkpoint_data")
    checkpoint = monitor.get_latest_checkpoint(task_id)
    print(f"  Checkpoint created: {checkpoint is not None}")

    # 获取健康状态
    status = monitor.get_health_status(task_id)
    print(f"  Health status: {status.status.value}")
    print(f"  Progress: {status.metrics.current_progress}%")
    print(f"  Message: {status.message}")

    # 完成任务
    monitor.complete_task(task_id)

    # 获取统计
    stats = monitor.get_statistics()
    print(f"  Monitor stats: {stats}")

    return True


def test_dashboard():
    """测试仪表板"""
    dashboard = DiagnosisDashboard()

    # 生成 HTML
    html = dashboard.generate_html()
    print(f"  Generated HTML: {len(html)} bytes")

    # 保存
    output_path = dashboard.save_html()
    print(f"  Saved to: {output_path}")

    return True


def test_integration():
    """集成测试"""
    print("\n  --- 完整流程测试 ---")

    # 1. 记录错误
    logger = get_logger("integration_test")
    logger.error(
        "AI model inference timeout",
        error_code="INF_001",
        error_category=ErrorCategory.AI_INFERENCE,
        context={"model": "llama-7b", "timeout": 30}
    )
    print("  ✓ Step 1: Error logged")

    # 2. 分类错误
    result = classify_error("AI model inference timeout")
    print(f"  ✓ Step 2: Classified as {result.category.value}/{result.subcategory}")

    # 3. 诊断错误
    engine = get_diagnosis_engine()
    error_entry = {
        "message": "AI model inference timeout",
        "error_code": result.error_code,
        "error_category": result.category.value
    }
    diagnosis = engine.diagnose(error_entry)
    print(f"  ✓ Step 3: Diagnosed - {diagnosis.probable_cause}")

    # 4. 生成用户友好消息
    user_msg = generate_user_friendly_error(error_entry, UserLevel.NOVICE)
    print(f"  ✓ Step 4: User message generated")

    # 5. 尝试自动修复
    fix_system = get_fix_system()
    if diagnosis.auto_fix_possible:
        fix_result = fix_system.fix(diagnosis, skip_confirmation=True)
        print(f"  ✓ Step 5: Auto-fix {'succeeded' if fix_result.success else 'failed'}")

    return True


def main():
    """主函数"""
    print("=" * 60)
    print("智能诊断系统测试套件")
    print("LivingTreeAI Intelligent Diagnosis System")
    print("=" * 60)

    runner = TestRunner()

    # 运行测试
    runner.test("1. StructuredLogger", test_structured_logger)
    runner.test("2. ErrorClassifier", test_error_classifier)
    runner.test("3. DiagnosisEngine", test_diagnosis_engine)
    runner.test("4. AutoFixSystem", test_auto_fix_system)
    runner.test("5. NLGGenerator", test_nlg_generator)
    runner.test("6. TaskMonitor", test_task_monitor)
    runner.test("7. Dashboard", test_dashboard)
    runner.test("8. Integration", test_integration)

    # 总结
    success = runner.summary()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
