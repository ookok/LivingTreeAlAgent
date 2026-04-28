"""
DRET L0-L4 集成测试（增强版）
测试内容:
1. 可配置递归深度（最高 20 层）
2. 专家角色查找系统集成
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ════════════════════════════════════════════════════════════════════════════
# Test 1: 递归深度配置
# ════════════════════════════════════════════════════════════════════════════

def test_recursion_depth_config():
    """测试递归深度配置"""
    print("\n[Test 1] 递归深度配置")
    print("-" * 40)
    
    from core.skill_evolution.dret_l04_integration import (
        RecursionDepthConfig,
        L04IntegratedGapDetector
    )
    
    # 测试预定义档位
    assert RecursionDepthConfig.get_depth("shallow") == 3
    assert RecursionDepthConfig.get_depth("medium") == 10
    assert RecursionDepthConfig.get_depth("deep") == 20
    assert RecursionDepthConfig.get_depth("training") == 20
    
    # 测试边界值
    assert RecursionDepthConfig.get_depth("xxx") == 10  # 默认值
    assert RecursionDepthConfig.get_depth(25) == 20     # 超过上限
    assert RecursionDepthConfig.get_depth(0) == 1       # 低于下限
    
    # 测试阶段深度
    stage_depths = RecursionDepthConfig.STAGE_DEPTHS
    assert stage_depths["gap_detection"] == 3
    assert stage_depths["recursive_fill"] == 20  # 最高 20
    
    # 测试 GapDetector 深度限制
    detector_3 = L04IntegratedGapDetector(enable_l04=False, max_depth=3)
    assert detector_3.max_depth == 3
    
    detector_20 = L04IntegratedGapDetector(enable_l04=False, max_depth=20)
    assert detector_20.max_depth == 20
    
    # 测试非法值自动限制
    detector_invalid = L04IntegratedGapDetector(enable_l04=False, max_depth=100)
    assert detector_invalid.max_depth == 20  # 自动限制到 20
    
    print("  [PASS] 递归深度配置验证通过")
    print(f"  - 预定义档位: shallow=3, medium=10, deep=20, training=20")
    print(f"  - 阶段深度: gap_detection=3, recursive_fill=20")
    print(f"  - 边界限制: 1 <= depth <= 20")
    
    return True


# ════════════════════════════════════════════════════════════════════════════
# Test 2: 专家角色系统集成
# ════════════════════════════════════════════════════════════════════════════

def test_expert_role_system():
    """测试专家角色查找系统"""
    print("\n[Test 2] 专家角色系统集成")
    print("-" * 40)
    
    from core.skill_evolution.dret_l04_integration import (
        ExpertRoleFinder,
        EXPERT_ROLES,
        L04IntegratedRecursiveLearner
    )
    
    # 创建专家角色查找器
    expert_finder = ExpertRoleFinder(enable_expert=True)
    
    # 检查是否成功加载
    if expert_finder.persona_dispatcher:
        print("  [OK] PersonaDispatcher 已加载")
    else:
        print("  [--] PersonaDispatcher 未加载（expert_system 可能不在路径中）")
    
    # 测试查找最佳人格
    topic = "企业需要进行成本控制和投资回报分析"
    context = "用户是企业管理者，关注 ROI"
    
    best_persona = expert_finder.find_best_persona(topic, context)
    if best_persona:
        print(f"  [OK] 最佳人格: {best_persona['persona_name']}")
        print(f"  [OK] 匹配度: {best_persona['match_score']}")
        print(f"  [OK] 领域: {best_persona['domain']}")
    else:
        print("  [--] 人格查找未返回结果（使用默认人格）")
        best_persona = expert_finder._get_default_persona()
    
    # 测试 Top-N 查找
    top_personas = expert_finder.get_top_personas(topic, context, n=3)
    print(f"\n  [OK] Top-3 匹配人格:")
    for i, p in enumerate(top_personas, 1):
        print(f"      {i}. {p['persona_name']} ({p['domain']}) - {p['match_score']}")
    
    # 测试角色搜索
    tech_experts = expert_finder.search_expert_by_role("技术")
    print(f"\n  [OK] 搜索'技术'相关人格: {len(tech_experts)} 个")
    for exp in tech_experts[:3]:
        print(f"      - {exp['persona_name']} ({exp['domain']})")
    
    # 测试按领域获取
    env_experts = expert_finder.get_expert_by_domain("environment")
    print(f"\n  [OK] 环境领域专家: {len(env_experts)} 个")
    for exp in env_experts:
        name = exp.get('name') or exp.get('persona_name') or exp.get('id', 'Unknown')
        desc = exp.get('description') or exp.get('persona_description', '')
        print(f"      - {name}: {desc}")
    
    # 测试角色列表
    all_personas = expert_finder.list_all_personas()
    print(f"\n  [OK] 人格库总数: {len(all_personas)}")
    
    # 打印内置角色
    print(f"\n  [OK] 内置专家角色库:")
    for role_id, role_info in EXPERT_ROLES.items():
        print(f"      - {role_info['name']} ({role_info['domain']})")
    
    return True


# ════════════════════════════════════════════════════════════════════════════
# Test 3: 递归深度限制测试
# ════════════════════════════════════════════════════════════════════════════

def test_recursion_depth_limiting():
    """测试递归深度限制"""
    print("\n[Test 3] 递归深度限制测试")
    print("-" * 40)
    
    from core.skill_evolution.dret_l04_integration import (
        L04IntegratedRecursiveLearner
    )
    
    # 测试不同递归深度
    test_depths = [1, 3, 10, 20, 25]  # 25 会被限制到 20
    
    for depth in test_depths:
        learner = L04IntegratedRecursiveLearner(
            max_depth=depth,
            enable_l04=False,
            enable_expert=False
        )
        
        expected = min(max(1, depth), 20)
        status = "PASS" if learner.max_depth == expected else "FAIL"
        print(f"  [{status}] 设置深度 {depth:2d} -> 实际 {learner.max_depth:2d} (期望 {expected})")
    
    # 测试动态修改深度
    learner = L04IntegratedRecursiveLearner(
        max_depth=3,
        enable_l04=False,
        enable_expert=False
    )
    
    print("\n  [Test] 动态修改递归深度:")
    
    # 修改为更高
    learner.set_recursion_depth(15)
    assert learner.max_depth == 15
    
    # 修改为更高（超过限制）
    learner.set_recursion_depth(25)
    assert learner.max_depth == 20
    
    # 修改为更低
    learner.set_recursion_depth(5)
    assert learner.max_depth == 5
    
    # 修改为更低（低于限制）
    learner.set_recursion_depth(0)
    assert learner.max_depth == 1
    
    print("  [PASS] 动态修改验证通过")
    
    return True


# ════════════════════════════════════════════════════════════════════════════
# Test 4: 完整流程测试（20 层递归）
# ════════════════════════════════════════════════════════════════════════════

def test_full_pipeline_20_layers():
    """测试完整流程（最高 20 层）"""
    print("\n[Test 4] 完整流程测试（20 层递归）")
    print("-" * 40)
    
    from core.skill_evolution.dret_l04_integration import (
        create_l04_dret_system
    )
    
    sample_doc = """
    OpenCode 是一个 AI 代码助手，支持以下功能：

    1. 安装: npm install -g opencode-ai
    2. 配置 oh-my-opencode: bunx oh-my-opencode install
    3. 使用 ultrawork 模式可以全自动完成任务

    特点：
    - 支持多 Agent 协同
    - 支持 Tab 切换 (plan/build)
    - 支持 /init 生成 AGENTS.md

    注意：需要先安装 Node.js 环境
    """
    
    # ════════════════════════════════════════════════════════════════════════════
    # 测试不同递归深度
    # ════════════════════════════════════════════════════════════════════════════
    
    test_configs = [
        ("浅层学习 (3层)", 3),
        ("中层学习 (10层)", 10),
        ("深层学习 (20层)", 20),
        ("训练模式 (20层)", 20),
    ]
    
    for config_name, depth in test_configs:
        print(f"\n  [{config_name}]")
        
        dret = create_l04_dret_system(
            max_recursion_depth=depth,
            enable_l04=False,
            enable_expert=True
        )
        
        report = dret.learn_from_document(
            sample_doc,
            doc_id="test_doc",
            recursion_depth=depth  # 动态覆盖
        )
        
        print(f"    最大深度: {report['max_depth_used']} 层")
        print(f"    空白发现: {report['gaps_found']}")
        print(f"    矛盾发现: {report['conflicts_found']}")
        print(f"    专家人格: {report.get('expert_persona', 'N/A')}")
        print(f"    耗时: {report['total_time']:.3f}s")
    
    return True


# ════════════════════════════════════════════════════════════════════════════
# Test 5: 专家角色查找高级功能
# ════════════════════════════════════════════════════════════════════════════

def test_expert_role_advanced():
    """测试专家角色高级功能"""
    print("\n[Test 5] 专家角色高级功能")
    print("-" * 40)
    
    from core.skill_evolution.dret_l04_integration import (
        ExpertRoleFinder,
        EXPERT_ROLES
    )
    
    expert_finder = ExpertRoleFinder(enable_expert=True)
    
    # ════════════════════════════════════════════════════════════════════════════
    # 场景测试
    # ════════════════════════════════════════════════════════════════════════════
    
    scenarios = [
        {
            "name": "企业管理者 - 成本控制",
            "topic": "我们需要控制项目成本，提高 ROI",
            "context": "企业管理者，关注投资回报"
        },
        {
            "name": "政府官员 - 合规审批",
            "topic": "这个项目需要符合环保法规要求",
            "context": "政府官员，关注合规审批"
        },
        {
            "name": "工程师 - 技术选型",
            "topic": "如何选择合适的技术方案",
            "context": "工程师，关注技术细节"
        },
        {
            "name": "研究人员 - 学术论文",
            "topic": "如何撰写高质量的学术论文",
            "context": "研究人员，关注学术质量"
        },
        {
            "name": "初学者 - 入门指导",
            "topic": "什么是机器学习，如何入门",
            "context": "初学者，需要通俗解释"
        },
        {
            "name": "环保专家 - 环境影响",
            "topic": "项目对环境的影响评估",
            "context": "关注环保问题"
        },
    ]
    
    print("\n  场景测试:")
    for scenario in scenarios:
        best = expert_finder.find_best_persona(
            scenario["topic"],
            scenario["context"]
        )
        
        if best:
            print(f"\n  [{scenario['name']}]")
            print(f"    话题: {scenario['topic'][:30]}...")
            print(f"    匹配: {best['persona_name']} ({best['domain']}) - {best['match_score']}")
            print(f"    描述: {best.get('persona_description', 'N/A')[:50]}...")
    
    return True


# ════════════════════════════════════════════════════════════════════════════
# 主函数
# ════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("DRET L0-L4 + 专家角色系统测试（增强版）")
    print("=" * 60)
    print(f"测试时间: 2026-04-23")
    print(f"功能: 可配置递归深度(最高20层) + 专家角色系统")
    
    tests = [
        ("递归深度配置", test_recursion_depth_config),
        ("专家角色系统", test_expert_role_system),
        ("递归深度限制", test_recursion_depth_limiting),
        ("完整流程(20层)", test_full_pipeline_20_layers),
        ("专家角色高级", test_expert_role_advanced),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, "[PASS]" if result else "[FAIL]"))
        except Exception as e:
            results.append((name, f"[ERROR]: {e}"))
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, result in results:
        print(f"  {result} - {name}")
    
    passed = sum(1 for _, r in results if "PASS" in r)
    print(f"\n通过: {passed}/{len(results)}")
    
    # ════════════════════════════════════════════════════════════════════════════
    # 功能总结
    # ════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("新增功能总结")
    print("=" * 60)
    print("""
    [1] 可配置递归深度 (最高 20 层)
        - 预定义档位: shallow(3), medium(10), deep(20), training(20)
        - 各阶段深度: gap_detection(3), recursive_fill(20)
        - 动态修改: set_recursion_depth()
        - 自动边界: 1 <= depth <= 20
    
    [2] 专家角色查找系统
        - find_best_persona(): 查找最佳匹配人格
        - get_top_personas(): Top-N 匹配
        - search_expert_by_role(): 角色关键词搜索
        - get_expert_by_domain(): 按领域获取
        - list_all_personas(): 列出所有人格
    
    [3] 内置专家角色
        - cost_focused_expert: 成本导向专家 (business)
        - compliance_focused_expert: 合规导向专家 (legal)
        - technical_expert: 技术专家 (engineering)
        - academic_expert: 学术专家 (academic)
        - beginner_friendly_expert: 入门友好专家 (education)
        - environmental_expert: 环保专家 (environment)
        - data_driven_expert: 数据驱动专家 (analytics)
        - general_expert: 通用专家 (general)
    
    [4] 深度学习训练支持
        - 最高 20 层递归深度
        - 循环访问检测
        - 专家角色引导辩论
    """)
    print("=" * 60)

if __name__ == "__main__":
    main()
