#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Evolution Engine Phase 4 - 进化记忆层完全独立测试
不依赖 core 模块的导入
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(r"F:\mhzyapp\LivingTreeAlAgent")
sys.path.insert(0, str(PROJECT_ROOT))

# 1. 导入 evolution_log
print("\n[1] 测试 EvolutionLog (SQLite 进化日志)")
print("-" * 40)

try:
    # 直接加载模块
    import importlib.util
    
    # 加载 evolution_log
    spec = importlib.util.spec_from_file_location(
        "evolution_log",
        PROJECT_ROOT / "core" / "evolution_engine" / "memory" / "evolution_log.py"
    )
    evolution_log = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evolution_log)
    
    # 创建实例
    db_path = os.path.join(tempfile.gettempdir(), 'test_evolution.db')
    log = evolution_log.EvolutionLog(db_path)
    
    # 测试扫描记录
    scan_id = log.log_scan(
        sensor_type="performance",
        signals_count=5,
        signals_summary={
            'signals': [
                {'type': 'slow_query', 'severity': 'high', 'location': '/core/db.py', 'description': '查询超过1秒'},
            ]
        },
        duration_ms=150.5
    )
    print(f"[PASS] 扫描记录创建成功: scan_id={scan_id}")
    
    # 获取摘要
    summary = log.get_summary()
    print(f"[PASS] 日志摘要: total_scans={summary['total_scans']}")
    
    print("\n[PASS] EvolutionLog 测试通过!")
    
except Exception as e:
    print(f"[FAIL] EvolutionLog 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 2. 测试 LearningEngine
print("\n[2] 测试 LearningEngine (强化学习引擎)")
print("-" * 40)

try:
    spec = importlib.util.spec_from_file_location(
        "learning_engine",
        PROJECT_ROOT / "core" / "evolution_engine" / "memory" / "learning_engine.py"
    )
    learning_engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(learning_engine)
    
    learning = learning_engine.get_learning_engine()
    
    # 模拟学习
    learning.learn_from_execution(
        proposal_type="performance_optimization",
        proposal_id="prop_001",
        signals=[{'type': 'slow_query', 'severity': 'high'}],
        execution_result={'status': 'success', 'steps_completed': 3, 'steps_total': 3}
    )
    print("[PASS] 学习记录成功")
    
    # 获取统计
    stats = learning.get_statistics()
    print(f"[PASS] 学习统计: {stats['total_samples']} 样本")
    
    # 提案评分
    score = learning.get_proposal_score("performance_optimization", 0.8, "medium", 5000)
    print(f"[PASS] 提案评分: {score:.3f}")
    
    print("\n[PASS] LearningEngine 测试通过!")
    
except Exception as e:
    print(f"[FAIL] LearningEngine 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 3. 测试 PatternMiner
print("\n[3] 测试 PatternMiner (模式挖掘器)")
print("-" * 40)

try:
    spec = importlib.util.spec_from_file_location(
        "pattern_miner",
        PROJECT_ROOT / "core" / "evolution_engine" / "memory" / "pattern_miner.py"
    )
    pattern_miner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pattern_miner)
    
    miner = pattern_miner.get_pattern_miner()
    
    # 添加事件
    for i in range(5):
        miner.add_event({
            'type': 'signal',
            'timestamp': f'2026-04-25T10:{i:02d}:00',
            'data': {'signal_type': 'slow_query', 'severity': 'high'}
        })
    
    print("[PASS] 事件流添加成功")
    
    # 挖掘模式
    patterns = miner.mine_patterns()
    print(f"[PASS] 模式挖掘: {len(patterns['temporal'])} 时序, {len(patterns['cooccurrence'])} 共现")
    
    print("\n[PASS] PatternMiner 测试通过!")
    
except Exception as e:
    print(f"[FAIL] PatternMiner 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 4. 测试 DecisionTracker
print("\n[4] 测试 DecisionTracker (决策追踪器)")
print("-" * 40)

try:
    spec = importlib.util.spec_from_file_location(
        "decision_tracker",
        PROJECT_ROOT / "core" / "evolution_engine" / "memory" / "decision_tracker.py"
    )
    decision_tracker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decision_tracker)
    
    tracker = decision_tracker.get_decision_tracker()
    
    # 创建决策链
    chain_id = tracker.create_chain("prop_001")
    print(f"[PASS] 决策链创建: {chain_id}")
    
    # 构建上下文
    context = decision_tracker.DecisionContext(
        signals=[{'type': 'slow_query', 'severity': 'high'}],
        proposals=[{'proposal_id': 'prop_001'}],
        risk_tolerance='medium'
    )
    
    # 构建因素
    factors = [
        decision_tracker.DecisionFactor(
            factor_type='severity', value=0.8, weight=0.3
        )
    ]
    
    # 记录决策
    node_id = tracker.record_decision(
        chain_id=chain_id,
        decision_type=decision_tracker.DecisionType.APPROVE,
        context=context,
        factors=factors,
        reasoning='测试决策',
        decision_maker='test'
    )
    print(f"[PASS] 决策记录: {node_id}")
    
    # 获取统计
    stats = tracker.get_statistics()
    print(f"[PASS] 追踪统计: total_chains={stats['total_chains']}")
    
    print("\n[PASS] DecisionTracker 测试通过!")
    
except Exception as e:
    print(f"[FAIL] DecisionTracker 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 总结
print("\n" + "=" * 60)
print("Evolution Engine Phase 4 进化记忆层测试完成!")
print("=" * 60)

print("""
Phase 4 进化记忆层 - 新增功能:

  1. EvolutionLog (SQLite 进化日志)
     - 记录扫描、提案、执行、决策历史
     - 支持时序查询和统计分析
     
  2. LearningEngine (强化学习引擎)
     - 从历史执行中学习
     - 提案评分和成功预测
     - 生成学习洞察
     
  3. PatternMiner (模式挖掘器)
     - 时序模式：发现信号周期性
     - 共现模式：发现信号关联性
     - 因果模式：发现决策因果
     - 异常模式：检测异常行为
     
  4. DecisionTracker (决策追踪器)
     - 追踪决策因果链
     - 根因分析
     - 决策解释和审计
""")
