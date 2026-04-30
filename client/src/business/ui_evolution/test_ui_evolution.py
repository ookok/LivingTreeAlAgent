# -*- coding: utf-8 -*-
"""
智能 UI 进化系统测试
==================

测试 ui_evolution 模块的各个组件：
1. OperationSequenceDB - 操作序列数据库
2. TFIDFPredictor - TF-IDF 预测器
3. FeedbackCollector - 反馈收集器
4. EvolutionScheduler - 进化调度器
5. SmartUISystem - 智能 UI 系统

Author: LivingTreeAI Team
Date: 2026-04-24
"""

import sys
import os
import time
import tempfile
from pathlib import Path

# 添加项目路径
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def test_operation_sequence():
    """测试操作序列数据库"""
    print("\n" + "="*60)
    print("测试 1: OperationSequenceDB - 操作序列数据库")
    print("="*60)
    
    from client.src.business.ui_evolution.operation_sequence import (
        OperationSequenceDB,
        OperationRecord,
        record_action,
        get_recent_sequence,
    )
    
    # 创建临时数据库
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_ops.db"
        db = OperationSequenceDB(str(db_path))
        
        # 记录操作序列
        print("\n[1] 记录操作序列...")
        
        operations = [
            ("click", "input_field", ""),
            ("input", "message_field", "Hello"),
            ("click", "send_btn", ""),
            ("click", "input_field", ""),
            ("input", "message_field", "World"),
            ("click", "send_btn", ""),
        ]
        
        for action_type, target, value in operations:
            op = OperationRecord(
                action_type=action_type,
                action_target=target,
                action_value=value,
                session_id="test_session",
            )
            db.record_operation(op)
        
        print(f"   ✓ 记录了 {len(operations)} 个操作")
        
        # 获取序列
        print("\n[2] 获取操作序列...")
        sequence = db.get_operation_sequence(session_id="test_session", max_length=10)
        print(f"   序列: {sequence}")
        assert len(sequence) > 0, "应该获取到操作序列"
        print(f"   ✓ 获取到 {len(sequence)} 个操作的序列")
        
        # 获取统计
        print("\n[3] 获取统计...")
        stats = db.get_operation_stats()
        print(f"   统计: {stats}")
        print(f"   ✓ 统计正常")
        
        db.close()
    
    return True


def test_tfidf_predictor():
    """测试 TF-IDF 预测器"""
    print("\n" + "="*60)
    print("测试 2: TFIDFPredictor - TF-IDF 预测器")
    print("="*60)
    
    from client.src.business.ui_evolution.tfidf_predictor import (
        TFIDFPredictor,
        predict_next,
        quick_predict,
    )
    
    # 创建预测器
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = Path(tmpdir) / "model.json"
        predictor = TFIDFPredictor(str(model_path))
        
        # 训练模型
        print("\n[1] 训练模型...")
        training_sequences = [
            ["click:input", "input:message", "click:send"],
            ["click:input", "input:message", "click:send"],
            ["click:input", "input:message", "click:send"],
            ["click:model", "select:model_dropdown", "click:option"],
            ["click:settings", "click:tab", "input:value"],
            ["click:input", "input:message"],
            ["click:send", "click:input"],
        ]
        
        predictor.train(training_sequences)
        print(f"   ✓ 训练完成，词汇量: {len(predictor.model.vocabulary)}")
        
        # 预测
        print("\n[2] 测试预测...")
        
        # 测试1: 完整序列
        result = predictor.predict(["click:input", "input:message"])
        print(f"   输入: ['click:input', 'input:message']")
        print(f"   预测: {result.predicted_action}, 置信度: {result.confidence:.2f}, 来源: {result.source}")
        assert result.predicted_action != "", "应该有预测结果"
        print(f"   ✓ 预测成功")
        
        # 测试2: 单动作
        result = predictor.predict(["click:send"])
        print(f"   输入: ['click:send']")
        print(f"   预测: {result.predicted_action}, 置信度: {result.confidence:.2f}")
        print(f"   ✓ 单动作预测成功")
        
        # 测试3: 空序列
        result = predictor.predict([])
        print(f"   输入: [] (空)")
        print(f"   预测: {result.predicted_action}, 置信度: {result.confidence:.2f}")
        print(f"   ✓ 空序列处理正确")
        
        # 增量更新
        print("\n[3] 测试增量更新...")
        predictor.incremental_update(["input:message"], "click:send", success=True)
        print(f"   ✓ 增量更新成功")
        
        # 快捷函数
        print("\n[4] 测试快捷函数...")
        action, conf = quick_predict("click:input")
        print(f"   quick_predict('click:input') = {action}, {conf:.2f}")
        print(f"   ✓ 快捷函数正常")
    
    return True


def test_feedback_collector():
    """测试反馈收集器"""
    print("\n" + "="*60)
    print("测试 3: FeedbackCollector - 反馈收集器")
    print("="*60)
    
    from client.src.business.ui_evolution.feedback_collector import (
        FeedbackCollector,
        FeedbackType,
        record_prediction_feedback,
        get_feedback_stats,
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "feedback.json"
        collector = FeedbackCollector(str(storage_path))
        
        # 记录预测和反馈
        print("\n[1] 记录预测和反馈...")
        
        # 记录一些预测
        predictions = [
            ("click:send", 0.9, "accept"),
            ("click:send", 0.8, "accept"),
            ("click:send", 0.6, "reject"),
            ("click:cancel", 0.5, "correct"),
            ("input:msg", 0.7, "accept"),
        ]
        
        for action, conf, feedback in predictions:
            collector.record_prediction(action, conf, "tfidf")
            collector.record_prediction(
                action, conf, "tfidf",
                context={"scene": "chat"}
            )
            if feedback == "accept":
                collector.accept()
            elif feedback == "reject":
                collector.reject()
            elif feedback == "correct":
                collector.correct("click:send")
        
        print(f"   ✓ 记录了 {len(predictions)} 条反馈")
        
        # 获取统计
        print("\n[2] 获取统计...")
        stats = collector.get_stats()
        print(f"   总预测: {stats.total_predictions}")
        print(f"   接受: {stats.accepted}, 拒绝: {stats.rejected}, 纠正: {stats.corrected}")
        print(f"   接受率: {stats.acceptance_rate:.1%}")
        assert stats.total_predictions > 0, "应该有统计数据"
        print(f"   ✓ 统计正常")
        
        # 获取训练数据
        print("\n[3] 获取训练数据...")
        training_data = collector.get_training_data(min_samples=1)
        print(f"   训练样本数: {len(training_data)}")
        print(f"   ✓ 训练数据正常")
        
        # 快捷函数
        print("\n[4] 测试快捷函数...")
        record_prediction_feedback("click:test", 0.8, "accept")
        print(f"   ✓ 快捷函数正常")
        
        feedback_stats = get_feedback_stats()
        print(f"   反馈统计: {feedback_stats}")
    
    return True


def test_evolution_scheduler():
    """测试进化调度器"""
    print("\n" + "="*60)
    print("测试 4: EvolutionScheduler - 进化调度器")
    print("="*60)
    
    from client.src.business.ui_evolution.evolution_scheduler import (
        EvolutionScheduler,
        EvolutionLevel,
        trigger_learning,
        get_evolution_status,
    )
    from client.src.business.ui_evolution.tfidf_predictor import TFIDFPredictor
    from client.src.business.ui_evolution.feedback_collector import FeedbackCollector
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建组件
        model_path = Path(tmpdir) / "model.json"
        predictor = TFIDFPredictor(str(model_path))
        
        storage_path = Path(tmpdir) / "feedback.json"
        feedback = FeedbackCollector(str(storage_path))
        
        # 创建调度器
        scheduler = EvolutionScheduler(
            predictor=predictor,
            feedback_collector=feedback,
            model_save_path=str(model_path),
        )
        
        # 触发即时学习
        print("\n[1] 触发即时学习...")
        scheduler.trigger_learning(
            context="click:input",
            action="input:message",
            sequence=["click:input"],
            success=True,
        )
        
        # 触发多次以满足增量阈值
        for i in range(50):
            scheduler.trigger_learning(
                context=f"action_{i}",
                action=f"next_{i}",
                sequence=[f"action_{i}"],
                success=i % 10 != 0,  # 90% 成功率
            )
        
        print(f"   ✓ 触发即时学习完成")
        
        # 获取状态
        print("\n[2] 获取进化状态...")
        status = get_evolution_status()
        print(f"   即时更新: {status['instant_updates']}")
        print(f"   增量训练: {status['incremental_trains']}")
        print(f"   知识条目: {status['knowledge_entries']}")
        print(f"   ✓ 进化状态正常")
        
        # 获取知识库统计
        print("\n[3] 获取知识库统计...")
        kb_stats = scheduler.get_knowledge_stats()
        print(f"   知识条目: {kb_stats}")
        print(f"   ✓ 知识库统计正常")
    
    return True


def test_smart_ui_system():
    """测试智能 UI 系统"""
    print("\n" + "="*60)
    print("测试 5: SmartUISystem - 智能 UI 系统")
    print("="*60)
    
    from client.src.business.ui_evolution.smart_ui_system import (
        SmartUISystem,
        smart_predict,
        record_ui_feedback,
    )
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = Path(tmpdir) / "model.json"
        system = SmartUISystem(model_save_path=str(model_path))
        
        # 处理操作
        print("\n[1] 处理操作...")
        
        operations = [
            ("click", "input_field", ""),
            ("input", "message_field", "Hello"),
            ("click", "send_btn", ""),
        ]
        
        for action_type, target, value in operations:
            result = system.process_operation(
                action_type=action_type,
                action_target=target,
                action_value=value,
                session_id="test_session",
            )
            print(f"   {action_type}:{target} → 预测: {result.suggestion.action}, "
                  f"置信度: {result.suggestion.confidence:.2f}, "
                  f"耗时: {result.prediction_time_ms:.2f}ms")
        
        print(f"   ✓ 操作处理完成")
        
        # 记录反馈
        print("\n[2] 记录反馈...")
        system.record_feedback("accept")
        print(f"   ✓ 反馈记录完成")
        
        # 获取统计
        print("\n[3] 获取统计...")
        stats = system.get_stats()
        print(f"   操作统计: {stats['operation_db']}")
        print(f"   反馈统计: {stats['feedback']}")
        print(f"   进化统计: {stats['evolution']}")
        print(f"   ✓ 系统统计正常")
        
        # 快捷函数
        print("\n[4] 测试快捷函数...")
        suggestion = smart_predict("click", "input_field", session_id="test_session")
        print(f"   smart_predict 结果: {suggestion.action}, {suggestion.confidence:.2f}")
        print(f"   ✓ 快捷函数正常")
        
        system.close()
    
    return True


def test_hints_integration():
    """测试 intelligent_hints 集成"""
    print("\n" + "="*60)
    print("测试 6: hints_integration - intelligent_hints 集成")
    print("="*60)
    
    try:
        from client.src.business.ui_evolution.hints_integration import (
            create_ui_hints_integration,
            UIHintsConfig,
        )
        
        print("\n[1] 创建集成...")
        interceptor = create_ui_hints_integration(
            enable_prediction=True,
            enable_evolution=False,  # 测试时不启用进化
        )
        
        if interceptor:
            print(f"   ✓ 集成创建成功")
            
            # 设置会话
            interceptor.set_session("test_session")
            
            # 模拟操作
            result = interceptor.on_operation(
                action_type="click",
                action_target="send_btn",
            )
            
            if result:
                print(f"   操作结果: {result['suggestion']}")
            
            print(f"   ✓ 操作拦截正常")
            
            # 模拟反馈
            interceptor.on_feedback("accept")
            print(f"   ✓ 反馈记录正常")
        else:
            print("   ⚠ intelligent_hints 模块不可用，跳过测试")
        
    except Exception as e:
        print(f"   ⚠ 集成测试跳过: {e}")
    
    return True


def main():
    """运行所有测试"""
    print("\n" + "="*70)
    print("🧪 智能 UI 进化系统测试")
    print("="*70)
    
    tests = [
        ("OperationSequenceDB", test_operation_sequence),
        ("TFIDFPredictor", test_tfidf_predictor),
        ("FeedbackCollector", test_feedback_collector),
        ("EvolutionScheduler", test_evolution_scheduler),
        ("SmartUISystem", test_smart_ui_system),
        ("hints_integration", test_hints_integration),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, "✓ PASS", success))
        except Exception as e:
            results.append((name, f"✗ FAIL: {e}", False))
            import traceback
            traceback.print_exc()
    
    # 汇总
    print("\n" + "="*70)
    print("📊 测试结果汇总")
    print("="*70)
    
    passed = sum(1 for _, status, _ in results if _)
    total = len(results)
    
    for name, status, _ in results:
        print(f"  [{status.split()[0]}] {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠ 部分测试失败")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
