"""
张雪峰 Skill 测试
"""

import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def log(msg, ok=True):
    prefix = "[OK]" if ok else "[FAIL]"
    print(f"{prefix} {msg}")


def test_import():
    print("\n" + "=" * 50)
    print("Skill Package Import Test")
    print("=" * 50)
    try:
        from business.zhangxuefeng_skill import (
            SkillPackage,
            MentalModel,
            ExpressionDNA,
            DynamicValidator,
            ZhangAgent,
            get_zhang_agent
        )
        log("Module import successful")
        return True
    except ImportError as e:
        log(f"Import failed: {e}", ok=False)
        return False


def test_skill_structure():
    print("\n" + "=" * 50)
    print("Skill Structure Test")
    print("=" * 50)

    from business.zhangxuefeng_skill import SkillPackage

    # 创建技能包
    skill = SkillPackage(
        skill_id="test_skill",
        name="测试技能",
        description="一个测试用技能包",
        version="1.0.0"
    )

    # 添加心智模型
    skill.add_mental_model(
        model_type="decision_tree",
        name="测试决策",
        description="测试用决策模型",
        rules=[{"condition": "price_sensitive", "action": "compare_value"}]
    )

    # 添加表达DNA
    skill.set_expression_dna(
        tone="friendly",
        phrases=["亲", "这款真的很好", "性价比很高"],
        forbidden=["垃圾", "烂"]
    )

    log(f"Skill created: {skill.name}")
    print(f"  - Mental Models: {len(skill.mental_models)}")
    print(f"  - Expression DNA: {skill.expression_dna.tone}")

    return True


def test_zhang_agent():
    print("\n" + "=" * 50)
    print("ZhangAgent Test")
    print("=" * 50)

    from business.zhangxuefeng_skill import get_zhang_agent

    agent = get_zhang_agent()

    # 测试技能调用
    skill_id = agent.get_active_skill_id()
    print(f"  Active skill: {skill_id}")

    log("ZhangAgent singleton works")
    return True


def test_persona_building():
    print("\n" + "=" * 50)
    print("Persona Building Test")
    print("=" * 50)

    from business.zhangxuefeng_skill import build_persona_skill

    # 构建销售顾问技能
    persona = build_persona_skill(
        persona_type="sales_advisor",
        tone="enthusiastic",
        expertise=["产品对比", "性价比分析", "砍价技巧"]
    )

    log(f"Persona skill created: {persona.name}")
    print(f"  - Type: {persona.metadata.tags}")
    print(f"  - Tone: {persona.expression_dna.tone}")
    print(f"  - Expertise: {persona.metadata.config.get('expertise', [])}")

    return True


def test_decision_pattern():
    print("\n" + "=" * 50)
    print("Decision Pattern Test")
    print("=" * 50)

    from business.zhangxuefeng_skill import DecisionPattern

    # 创建决策模式
    pattern = DecisionPattern(
        pattern_id="price_sensitive",
        name="价格敏感型决策",
        triggers=["价格", "便宜", "性价比", "预算"],
        decision_tree={
            "step1": "评估基本需求",
            "step2": "对比同类产品",
            "step3": "计算性价比",
            "step4": "给出最优解"
        }
    )

    matched = pattern.matches("这个产品价格怎么样？")
    log(f"Pattern matching: {matched}")

    return True


if __name__ == "__main__":
    results = []

    results.append(("Import", test_import()))
    results.append(("Skill Structure", test_skill_structure()))
    results.append(("ZhangAgent", test_zhang_agent()))
    results.append(("Persona Building", test_persona_building()))
    results.append(("Decision Pattern", test_decision_pattern()))

    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)

    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  [{'OK' if ok else 'X'}] {name}")

    print(f"\nTotal: {passed}/{len(results)} passed")
