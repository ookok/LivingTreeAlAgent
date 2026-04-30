"""
Test Dual Flywheel - 测试双数据飞轮

完整演示"双数据飞轮"工作流程：
1. 推理飞轮：从错题生成更难变体
2. 智能体飞轮：使用变体训练工具选择（支持多难度级别）

支持的难度级别：
- SIMPLE（简单）: 基础查询，无额外约束
- MEDIUM（中等）: 添加1-2个约束条件
- HARD（困难）: 添加多个约束、边界值、对抗条件
- EXPERT（专家）: 极端边界条件、复杂约束组合

支持的约束类型：
- TIME_LIMIT（时间限制）
- RESOURCE_LIMIT（资源限制）
- FORMAT_REQUIREMENT（格式要求）
- BOUNDARY_VALUE（边界值约束）
- PRECONDITION（前置条件）
- REJECTION_CONDITION（拒绝条件）
- ADVERSARIAL（对抗条件）
- OUTPUT_LIMIT（输出限制）

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import asyncio
import json
import os
from loguru import logger

from business.self_evolution.tool_self_repairer import (
    ToolSelfRepairer,
    RepairStrategy,
)
from business.self_evolution.hard_variant_generator import (
    HardVariantGenerator,
)
from business.self_evolution.train_with_variants import (
    VariantTrainer,
    DifficultyLevel,
    ConstraintType,
)


async def test_dual_flywheel():
    """测试双数据飞轮"""
    
    print("=" * 70)
    print("测试双数据飞轮（Dual Data Flywheel）")
    print("=" * 70)
    
    # =========================================================================
    # 步骤 1: 模拟工具执行失败，触发错题记录
    # =========================================================================
    print("\n[步骤 1] 模拟工具执行失败...")
    
    repairer = ToolSelfRepairer()
    
    # 模拟失败案例
    test_cases = [
        {
            "tool_name": "groundwater_tool",
            "error": "ModuleNotFoundError: No module named 'flopy'",
            "tool_input": {"model_type": "MODFLOW-6", "grid_type": "structured"}
        },
        {
            "tool_name": "aermod_tool",
            "error": "FileNotFoundError: [Errno 2] No such file or directory: 'aermod.exe'",
            "tool_input": {"project_name": "test", "meteo_file": "meteo.sfc"}
        },
        {
            "tool_name": "mike21_tool",
            "error": "ImportError: cannot import name 'Mesh' from 'mikecore'",
            "tool_input": {"operation": "create_mesh", "points": []}
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n  案例 {i}: {case['tool_name']}")
        print(f"    错误: {case['error'][:60]}...")
        
        # 调用 repair_tool（会记录错题）
        result = await repairer.repair_tool(
            tool_name=case['tool_name'],
            error=case['error'],
            tool_input=case.get('tool_input')
        )
        
        print(f"    修复结果: {'成功' if result.success else '失败'}")
        print(f"    策略: {result.strategy.value}")
        
        # 重要的是：错题已自动记录到 failed_cases.json
    
    print("\n  ✓ 错题记录完成，查看: .workbuddy/memory/failed_cases.json")
    
    # =========================================================================
    # 步骤 2: 推理飞轮 - 从错题生成更难变体
    # =========================================================================
    print("\n" + "=" * 70)
    print("[步骤 2] 推理飞轮：从错题生成更难变体...")
    print("=" * 70)
    
    generator = HardVariantGenerator()
    
    # 生成变体
    variants = await generator.generate_variants(max_cases=3)
    
    print(f"\n  生成了 {len(variants)} 个难题变体:")
    for v in variants:
        print(f"    - {v['variant_id']}: {v['variant_description'][:50]}...")
        print(f"      难度提升: {v.get('difficulty_increase', 'N/A')}")
    
    print("\n  ✓ 变体生成完成，查看: .workbuddy/memory/training_pool.json")
    
    # =========================================================================
    # 步骤 3: 使用变体进行训练（测试工具选择准确率）
    # =========================================================================
    print("\n" + "=" * 70)
    print("[步骤 3] 使用变体进行训练...")
    print("=" * 70)
    
    trainer = VariantTrainer()
    
    # 训练
    report = await trainer.train(max_variants=3)
    
    print(f"\n  训练报告:")
    print(f"    总变体数: {report.get('total_variants', 0)}")
    print(f"    正确数: {report.get('correct', 0)}")
    print(f"    准确率: {report.get('accuracy', 0):.1%}")
    
    # 显示详细结果
    print(f"\n  详细结果:")
    for detail in report.get('details', []):
        status = "✓" if detail.get('correct') else "✗"
        print(f"    {status} {detail.get('variant_id', 'N/A')}: {detail.get('query', '')[:40]}...")
    
    print("\n  ✓ 训练完成，查看: .workbuddy/memory/training_reports/")
    
    # =========================================================================
    # 步骤 4: 查看生成的文件
    # =========================================================================
    print("\n" + "=" * 70)
    print("[步骤 4] 查看生成的文件...")
    print("=" * 70)
    
    # 查看错题记录
    failed_cases_file = "d:/mhzyapp/LivingTreeAlAgent/.workbuddy/memory/failed_cases.json"
    if os.path.exists(failed_cases_file):
        with open(failed_cases_file, 'r', encoding='utf-8') as f:
            failed_cases = json.load(f)
        print(f"\n  错题记录: {len(failed_cases)} 条")
        for case in failed_cases[:3]:  # 只显示前3条
            print(f"    - ID {case['id']}: {case['tool_name']} ({case['error_message'][:40]}...)")
    
    # 查看训练池
    training_pool_file = "d:/mhzyapp/LivingTreeAlAgent/.workbuddy/memory/training_pool.json"
    if os.path.exists(training_pool_file):
        with open(training_pool_file, 'r', encoding='utf-8') as f:
            pool = json.load(f)
        print(f"\n  训练池: {len(pool)} 个变体")
        for variant in pool[:3]:  # 只显示前3条
            print(f"    - {variant['variant_id']}: {variant['variant_description'][:40]}...")
    
    # =========================================================================
    # 总结
    # =========================================================================
    print("\n" + "=" * 70)
    print("双数据飞轮测试完成")
    print("=" * 70)
    print("\n工作流程总结:")
    print("  1. ✓ 推理飞轮: 错题记录 → 生成更难变体")
    print("  2. ✓ 训练集成: 使用变体测试工具选择")
    print("\n下一步（智能体飞轮）:")
    print("  - 将线性工作流扩展为多分支行为树")
    print("  - 添加约束、拒绝条件、对抗条件")
    print("\n查看文件:")
    print(f"  - 错题记录: {failed_cases_file}")
    print(f"  - 训练池: {training_pool_file}")
    print("=" * 70)


async def test_simple_flywheel():
    """简化版双数据飞轮测试（无 LLM 调用）"""
    
    print("=" * 70)
    print("简化版双数据飞轮测试（演示数据结构）")
    print("=" * 70)
    
    # 1. 创建模拟错题
    print("\n[1] 创建模拟错题...")
    
    # 使用相对路径
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".workbuddy", "memory")
    os.makedirs(base_dir, exist_ok=True)
    
    failed_cases_file = os.path.join(base_dir, "failed_cases.json")
    
    mock_cases = [
        {
            "id": 1,
            "timestamp": "2026-04-28T10:00:00",
            "tool_name": "groundwater_tool",
            "error_message": "ModuleNotFoundError: No module named 'flopy'",
            "tool_input": {"model_type": "MODFLOW-6"},
            "repair_strategy": "install_dependency",
            "repair_success": False,
            "used_for_training": False
        },
        {
            "id": 2,
            "timestamp": "2026-04-28T10:05:00",
            "tool_name": "aermod_tool",
            "error_message": "FileNotFoundError: aermod.exe not found",
            "tool_input": {"project_name": "test"},
            "repair_strategy": "fix_config",
            "repair_success": False,
            "used_for_training": False
        },
        {
            "id": 3,
            "timestamp": "2026-04-28T10:10:00",
            "tool_name": "noise_model_tool",
            "error_message": "ValueError: Invalid frequency range",
            "tool_input": {"frequency": 20000},
            "repair_strategy": "fix_code",
            "repair_success": False,
            "used_for_training": False
        }
    ]
    
    with open(failed_cases_file, 'w', encoding='utf-8') as f:
        json.dump(mock_cases, f, ensure_ascii=False, indent=2)
    
    print(f"  ✓ 已创建 {len(mock_cases)} 条模拟错题")
    
    # 2. 创建模拟变体（包含不同难度级别）
    print("\n[2] 创建模拟变体（不同难度级别）...")
    
    training_pool_file = os.path.join(base_dir, "training_pool.json")
    
    mock_variants = [
        # SIMPLE（简单）: 无额外约束
        {
            "variant_id": "var_1_simple",
            "source_case_id": 1,
            "tool_name": "groundwater_tool",
            "generated_at": "2026-04-28T10:15:00",
            "used_for_training": False,
            "variant_description": "基础地下水建模任务",
            "difficulty_increase": "无额外约束，基础测试",
            "added_constraints": [],
            "test_case": {
                "query": "请使用 MODFLOW-6 建立地下水模型",
                "expected_tool": "groundwater_tool",
                "expected_params": {"model_type": "MODFLOW-6"}
            }
        },
        # MEDIUM（中等）: 1-2个约束条件
        {
            "variant_id": "var_1_medium",
            "source_case_id": 1,
            "tool_name": "groundwater_tool",
            "generated_at": "2026-04-28T10:20:00",
            "used_for_training": False,
            "variant_description": "添加时间约束：要求在 5 分钟内完成 MODFLOW 建模",
            "difficulty_increase": "增加时间限制，测试工具在压力下的表现",
            "added_constraints": ["时间限制：5分钟", "网格精度要求：≤1m"],
            "test_case": {
                "query": "请使用 MODFLOW-6 建立地下水模型，要求在 5 分钟内完成，网格精度≤1m",
                "expected_tool": "groundwater_tool",
                "expected_params": {"model_type": "MODFLOW-6", "time_limit": 300, "grid_precision": 1.0}
            }
        },
        # HARD（困难）: 多个约束，包含边界值
        {
            "variant_id": "var_2_hard",
            "source_case_id": 2,
            "tool_name": "aermod_tool",
            "generated_at": "2026-04-28T10:25:00",
            "used_for_training": False,
            "variant_description": "复杂大气扩散模拟，包含时间限制、边界值约束和格式要求",
            "difficulty_increase": "添加多个约束条件和边界值测试",
            "added_constraints": [
                "时间限制：10分钟",
                "边界值：风速范围 0-50m/s",
                "输出格式：CSV",
                "资源限制：CPU ≤ 2核"
            ],
            "test_case": {
                "query": "请使用 AERMOD 进行大气扩散模拟，要求在10分钟内完成，风速范围0-50m/s，输出CSV格式，限制2核CPU",
                "expected_tool": "aermod_tool",
                "expected_params": {"project_name": "complex", "wind_speed_range": [0, 50], "output_format": "csv", "cpu_limit": 2}
            }
        },
        # EXPERT（专家）: 极端边界条件、对抗条件
        {
            "variant_id": "var_3_expert",
            "source_case_id": 3,
            "tool_name": "noise_model_tool",
            "generated_at": "2026-04-28T10:30:00",
            "used_for_training": False,
            "variant_description": "极端噪声模型测试，包含对抗条件和复杂约束组合",
            "difficulty_increase": "极端边界条件、对抗条件、复杂约束组合",
            "added_constraints": [
                "时间限制：2分钟",
                "边界值：频率 0.1-20000Hz",
                "对抗条件：输入包含异常值需要过滤",
                "前置条件：必须先验证输入数据",
                "输出限制：结果文件 ≤ 10MB",
                "拒绝条件：超出频率范围时拒绝执行"
            ],
            "test_case": {
                "query": "请进行噪声模型计算，频率范围0.1-20000Hz，2分钟内完成，结果文件不超过10MB，需要先验证输入数据并过滤异常值，超出频率范围时拒绝执行",
                "expected_tool": "noise_model_tool",
                "expected_params": {"frequency_range": [0.1, 20000], "time_limit": 120, "output_limit_mb": 10, "validate_input": True, "filter_outliers": True}
            }
        }
    ]
    
    with open(training_pool_file, 'w', encoding='utf-8') as f:
        json.dump(mock_variants, f, ensure_ascii=False, indent=2)
    
    print(f"  ✓ 已创建 {len(mock_variants)} 个模拟变体（涵盖所有难度级别）")
    
    # 3. 使用 VariantTrainer 测试工具选择（按难度级别筛选）
    print("\n[3] 使用 VariantTrainer 测试工具选择...")
    
    trainer = VariantTrainer()
    
    # 测试所有难度级别
    print("\n  测试所有变体:")
    report_all = await trainer.train(max_variants=10, only_unused=False)
    print(f"    总准确率: {report_all.get('accuracy', 0):.1%} ({report_all.get('correct', 0)}/{report_all.get('total_variants', 0)})")
    
    # 按难度级别统计
    difficulty_stats = report_all.get('difficulty_stats', {})
    for level, stats in difficulty_stats.items():
        if stats.get('total', 0) > 0:
            print(f"    {level}: {stats.get('correct', 0)}/{stats.get('total', 0)} ({stats.get('accuracy', 0):.1%})")
    
    # 4. 显示文件内容
    print("\n[4] 查看生成的数据结构...")
    
    print(f"\n  错题记录 ({failed_cases_file}):")
    if os.path.exists(failed_cases_file):
        with open(failed_cases_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"    共 {len(data)} 条记录")
    else:
        print("    文件不存在")
    
    print(f"\n  训练池 ({training_pool_file}):")
    if os.path.exists(training_pool_file):
        with open(training_pool_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"    共 {len(data)} 个变体")
        for v in data:
            constraints_count = len(v.get('added_constraints', []))
            print(f"    - {v['variant_id']}: {v['variant_description'][:40]}... (约束数: {constraints_count})")
    else:
        print("    文件不存在")
    
    print("\n" + "=" * 70)
    print("简化版测试完成")
    print("=" * 70)


if __name__ == "__main__":
    import sys
    
    # 配置 loguru
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("\n选择测试模式:")
    print("  1. 完整测试（需要 LLM 调用）")
    print("  2. 简化测试（仅演示数据结构）")
    
    choice = input("\n请选择 (1/2): ").strip()
    
    if choice == "1":
        asyncio.run(test_dual_flywheel())
    else:
        asyncio.run(test_simple_flywheel())
