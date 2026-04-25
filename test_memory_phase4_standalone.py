#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Evolution Engine Phase 4 - 进化记忆层独立测试

直接测试 memory 模块，不依赖其他 EvolutionEngine 组件
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# 创建临时目录用于测试
test_dir = tempfile.mkdtemp(prefix="evolution_test_")
os.chdir(test_dir)

print(f"测试目录: {test_dir}")
print("=" * 60)

# 1. 测试 EvolutionLog
print("\n[1] 测试 EvolutionLog (SQLite 进化日志)")
print("-" * 40)

try:
    # 直接导入 memory 模块
    sys.path.insert(0, str(Path(__file__).parent))
    from core.evolution_engine.memory.evolution_log import EvolutionLog, get_evolution_log
    
    # 创建独立的日志实例
    db_path = os.path.join(test_dir, 'test_evolution.db')
    log = EvolutionLog(db_path)
    
    # 测试扫描记录
    scan_id = log.log_scan(
        sensor_type="performance",
        signals_count=5,
        signals_summary={
            'signals': [
                {'type': 'slow_query', 'severity': 'high', 'location': '/core/db.py', 'description': '查询超过1秒'},
                {'type': 'memory_leak', 'severity': 'critical', 'location': '/core/cache.py', 'description': '内存持续增长'},
            ]
        },
        duration_ms=150.5
    )
    print(f"✓ 扫描记录创建成功: scan_id={scan_id}")
    
    # 获取摘要
    summary = log.get_summary()
    print(f"✓ 日志摘要: total_scans={summary['total_scans']}")
    
    # 测试执行统计
    stats = log.get_execution_stats()
    print(f"✓ 执行统计: {stats}")
    
    print("\n✓ EvolutionLog 测试通过!")
    
except Exception as e:
    print(f"✗ EvolutionLog 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 2. 测试 LearningEngine
print("\n[2] 测试 LearningEngine (强化学习引擎)")
print("-" * 40)

try:
    from core.evolution_engine.memory.learning_engine import LearningEngine, get_learning_engine
    
    learning = get_learning_engine()
    
    # 模拟学习数据
    learning.learn_from_execution(
        proposal_type="performance_optimization",
        proposal_id="prop_001",
        signals=[
            {'type': 'slow_query', 'severity': 'high', 'location': '/core/db.py'},
            {'type': 'memory_leak', 'severity': 'critical', 'location': '/core/cache.py'}
        ],
        execution_result={
            'status': 'success',
            'steps_completed': 3,
            'steps_total': 3,
            'duration_ms': 5000
        }
    )
    print("✓ 学习记录成功 (成功执行)")
    
    # 再次学习（失败案例）
    learning.learn_from_execution(
        proposal_type="refactoring",
        proposal_id="prop_002",
        signals=[
            {'type': 'god_class', 'severity': 'medium', 'location': '/core/main.py'}
        ],
        execution_result={
            'status': 'failed',
            'steps_completed': 1,
            'steps_total': 3,
            'duration_ms': 2000
        }
    )
    print("✓ 学习记录成功 (失败执行)")
    
    # 获取统计
    stats = learning.get_statistics()
    print(f"✓ 学习统计: {stats}")
    
    # 获取洞察
    insights = learning.get_insights()
    print(f"✓ 学习洞察: {len(insights)} 条")
    
    # 测试提案评分
    score = learning.get_proposal_score(
        proposal_type="performance_optimization",
        signal_strength=0.8,
        risk_level="medium",
        estimated_time_ms=5000
    )
    print(f"✓ 提案评分: {score:.3f}")
    
    print("\n✓ LearningEngine 测试通过!")
    
except Exception as e:
    print(f"✗ LearningEngine 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 3. 测试 PatternMiner
print("\n[3] 测试 PatternMiner (模式挖掘器)")
print("-" * 40)

try:
    from core.evolution_engine.memory.pattern_miner import PatternMiner, get_pattern_miner
    
    miner = get_pattern_miner()
    
    # 添加事件流
    for i in range(5):
        miner.add_event({
            'type': 'signal',
            'timestamp': f'2026-04-25T10:{i:02d}:00',
            'data': {
                'signal_type': 'slow_query',
                'severity': 'high',
                'location': '/core/db.py'
            }
        })
    
    for i in range(3):
        miner.add_event({
            'type': 'proposal',
            'timestamp': f'2026-04-25T10:{i:02d}:30',
            'data': {
                'proposal_type': 'performance_optimization',
                'status': 'pending'
            }
        })
    
    for i in range(2):
        miner.add_event({
            'type': 'execution',
            'timestamp': f'2026-04-25T10:{i:02d}:45',
            'data': {
                'proposal_id': f'prop_{i:03d}',
                'status': 'success'
            }
        })
    
    print("✓ 事件流添加成功")
    
    # 执行模式挖掘
    patterns = miner.mine_patterns()
    print(f"✓ 模式挖掘完成:")
    print(f"   - 时序模式: {len(patterns['temporal'])}")
    print(f"   - 共现模式: {len(patterns['cooccurrence'])}")
    print(f"   - 因果模式: {len(patterns['causal'])}")
    print(f"   - 异常模式: {len(patterns['anomalies'])}")
    
    # 获取摘要
    summary = miner.get_patterns_summary()
    print(f"✓ 模式摘要: temporal={summary['temporal_count']}, cooccurrence={summary['cooccurrence_count']}")
    
    # 获取预测
    predictions = miner.get_predictions()
    print(f"✓ 预测: {len(predictions)} 条")
    
    print("\n✓ PatternMiner 测试通过!")
    
except Exception as e:
    print(f"✗ PatternMiner 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 4. 测试 DecisionTracker
print("\n[4] 测试 DecisionTracker (决策追踪器)")
print("-" * 40)

try:
    from core.evolution_engine.memory.decision_tracker import (
        DecisionTracker, get_decision_tracker,
        DecisionType, DecisionContext, DecisionFactor,
        DecisionOutcome
    )
    
    tracker = get_decision_tracker()
    
    # 创建决策链
    chain_id = tracker.create_chain("prop_001")
    print(f"✓ 决策链创建: {chain_id}")
    
    # 构建决策上下文
    context = DecisionContext(
        signals=[
            {'type': 'slow_query', 'severity': 'high', 'location': '/core/db.py'},
            {'type': 'memory_leak', 'severity': 'critical', 'location': '/core/cache.py'}
        ],
        proposals=[{'proposal_id': 'prop_001', 'title': '性能优化'}],
        proposals_considered=2,
        risk_tolerance='medium'
    )
    
    # 构建决策因素
    factors = [
        DecisionFactor(
            factor_type='severity',
            value=0.8,
            weight=0.3,
            description='严重程度: high'
        ),
        DecisionFactor(
            factor_type='success_rate',
            value=0.75,
            weight=0.25,
            description='历史成功率: 75%'
        ),
        DecisionFactor(
            factor_type='risk',
            value=0.5,
            weight=0.3,
            description='风险等级: medium'
        )
    ]
    
    # 记录批准决策
    node_id = tracker.record_decision(
        chain_id=chain_id,
        decision_type=DecisionType.APPROVE,
        context=context,
        factors=factors,
        reasoning='提案通过安全检查，历史成功率高',
        decision_maker='user'
    )
    print(f"✓ 决策记录: {node_id}")
    
    # 关联执行
    tracker.link_execution(chain_id, 'exec_001')
    
    # 记录结果
    tracker.resolve_outcome(
        chain_id,
        DecisionOutcome.SUCCESS,
        reason='执行成功，所有步骤完成'
    )
    print("✓ 结果记录成功")
    
    # 获取链
    chain = tracker.get_chain(chain_id)
    print(f"✓ 链获取: {chain.chain_id}, 节点数: {len(chain.nodes)}")
    
    # 分析根因
    analysis = tracker.analyze_root_cause(chain_id)
    print(f"✓ 根因分析: outcome={analysis.get('final_outcome')}")
    
    # 解释决策
    if node_id:
        explanation = tracker.explain_decision(node_id)
        print(f"✓ 决策解释: {explanation.get('summary')}")
    
    # 获取统计
    stats = tracker.get_statistics()
    print(f"✓ 追踪统计: total_chains={stats['total_chains']}")
    
    print("\n✓ DecisionTracker 测试通过!")
    
except Exception as e:
    print(f"✗ DecisionTracker 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 5. 测试模块导出
print("\n[5] 测试模块导出")
print("-" * 40)

try:
    from core.evolution_engine.memory import (
        get_evolution_log,
        get_learning_engine,
        get_pattern_miner,
        get_decision_tracker
    )
    
    print("✓ 所有导出函数可用")
    print("\n✓ 模块导出测试通过!")
    
except Exception as e:
    print(f"✗ 模块导出测试失败: {e}")
    import traceback
    traceback.print_exc()

# 清理
print("\n" + "=" * 60)
print("Evolution Engine Phase 4 测试完成!")
print("=" * 60)

# 删除临时目录
try:
    shutil.rmtree(test_dir)
    print(f"\n已清理测试目录: {test_dir}")
except:
    print(f"\n注意: 保留测试目录 {test_dir} 用于检查")

print("""
Phase 4 进化记忆层功能摘要:
┌─────────────────────────────────────────────────────────────┐
│  组件            │  功能                                      │
├─────────────────────────────────────────────────────────────┤
│  EvolutionLog    │  SQLite 持久化存储（扫描/提案/执行/决策）     │
│  LearningEngine  │  强化学习（提案评分/成功预测/洞察生成）       │
│  PatternMiner    │  模式挖掘（时序/共现/因果/异常模式）          │
│  DecisionTracker │  决策追踪（因果链/根因分析/决策解释）         │
└─────────────────────────────────────────────────────────────┘
""")
