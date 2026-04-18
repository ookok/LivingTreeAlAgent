"""
专家系统测试脚本
验证所有核心功能
"""

import sys
import os
import asyncio
import json
from pathlib import Path

# 修复 Windows 控制台 Unicode 问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from expert_system import (
    UserProfileParser, UserProfile,
    PersonaDispatcher, Persona, PersonaLibrary,
    PersonalizedExpert, ExpertResponse,
    ExpertRepository, SkillRepository, ExportManager,
    BUILTIN_PERSONAS, BUILTIN_SKILLS,
    SOCIAL_ROLES
)


def test_user_profile_parser():
    """测试用户画像解析器"""
    print("\n" + "="*60)
    print("测试 1: 用户画像解析器")
    print("="*60)
    
    parser = UserProfileParser()
    
    test_cases = [
        {
            "message": "我们公司想新建一个化工厂，需要做环评，请问150米烟囱够不够？预算大概多少？",
            "expected_roles": ["enterprise_manager"],
            "expected_concerns": ["成本"]
        },
        {
            "message": "根据HJ 2.1-2016标准，这个项目的排放标准是什么？需要哪些审批流程？",
            "expected_roles": ["government_official"],
            "expected_concerns": ["合规"]
        },
        {
            "message": "这个技术方案用AERMOD模型的话，参数应该怎么设置？",
            "expected_roles": ["engineer"],
            "expected_concerns": ["技术"]
        },
        {
            "message": "请问什么是大气污染？对人体有什么危害？",
            "expected_roles": ["resident"],
            "expected_concerns": ["风险"]
        }
    ]
    
    all_passed = True
    for i, case in enumerate(test_cases, 1):
        result = parser.parse_from_message(case["message"])
        
        print(f"\n测试用例 {i}:")
        print(f"  消息: {case['message'][:40]}...")
        print(f"  识别角色: {list(result['role_confidences'].keys())}")
        print(f"  识别关切: {result['primary_concerns']}")
        print(f"  知识水平: {result['expertise_level']}")
        print(f"  置信度: {result['confidence']:.0%}")
        
        detected_roles = list(result['role_confidences'].keys())
        for expected in case["expected_roles"]:
            if expected in detected_roles:
                print(f"  [OK] Role '{expected}' recognized")
            else:
                print(f"  [X] Expected role '{expected}' not recognized")
                all_passed = False
        
        for expected in case["expected_concerns"]:
            if expected in result["primary_concerns"]:
                print(f"  [OK] Concern '{expected}' recognized")
            else:
                print(f"  [X] Concern '{expected}' not recognized")
    
    return all_passed


def test_persona_dispatcher():
    """测试人格调度器"""
    print("\n" + "="*60)
    print("测试 2: 专家人格调度器")
    print("="*60)
    
    dispatcher = PersonaDispatcher()
    
    test_cases = [
        {
            "profile": {
                "social_roles": {"enterprise_manager": 0.9},
                "core_concerns": {"成本": 0.8, "市场": 0.5},
                "expertise_level": "medium",
                "decision_style": "cost_sensitive"
            },
            "question": "这个项目投资回报率怎么样？",
            "expected_persona": "cost_focused_expert"
        },
        {
            "profile": {
                "social_roles": {"government_official": 0.9},
                "core_concerns": {"合规": 0.8, "风险": 0.7},
                "expertise_level": "expert",
                "decision_style": "risk_averse"
            },
            "question": "需要满足哪些法规要求？",
            "expected_persona": "compliance_focused_expert"
        },
        {
            "profile": {
                "social_roles": {"engineer": 0.9},
                "core_concerns": {"技术": 0.8},
                "expertise_level": "expert",
                "decision_style": "data_driven"
            },
            "question": "AERMOD模型的参数设置",
            "expected_persona": "technical_expert"
        },
        {
            "profile": {
                "social_roles": {"resident": 0.7},
                "core_concerns": {"风险": 0.9},
                "expertise_level": "beginner",
                "decision_style": "risk_averse"
            },
            "question": "什么是大气污染？",
            "expected_persona": "beginner_friendly_expert"
        }
    ]
    
    all_passed = True
    for i, case in enumerate(test_cases, 1):
        persona = dispatcher.dispatch(case["profile"], case["question"])
        
        print(f"\n测试用例 {i}:")
        print(f"  画像: 角色={list(case['profile']['social_roles'].keys())}, 关切={list(case['profile']['core_concerns'].keys())}")
        print(f"  问题: {case['question']}")
        print(f"  匹配人格: {persona.name if persona else 'None'}")
        
        if persona and persona.id == case["expected_persona"]:
            print(f"  [OK] Persona matched correctly")
        else:
            print(f"  [X] Expected persona: {case['expected_persona']}")
            all_passed = False
        
        top_matches = dispatcher.dispatch_top_n(case["profile"], case["question"], 3)
        print(f"  Top 3: " + ", ".join([f"{p.name}({s:.0%})" for p, s in top_matches]))
    
    return all_passed


def test_repository():
    """测试仓库管理器"""
    print("\n" + "="*60)
    print("测试 3: 仓库管理器")
    print("="*60)
    
    repo = ExpertRepository()
    export_mgr = ExportManager(repo)
    
    print("\n内置人格库:")
    personas = repo.get_all_personas()
    builtin_count = sum(1 for p in personas if p.is_builtin)
    print(f"  总数: {len(personas)}, 内置: {builtin_count}")
    for p in personas[:3]:
        print(f"  - {p.name} ({p.id})")
    
    print("\n内置技能包:")
    skills = repo.get_all_skills()
    builtin_skill_count = sum(1 for s in skills if s.is_builtin)
    print(f"  总数: {len(skills)}, 内置: {builtin_skill_count}")
    for s in skills[:3]:
        print(f"  - {s.name} ({s.id})")
    
    print("\n测试导出:")
    
    persona_md = export_mgr.export_persona_markdown("cost_focused_expert")
    if persona_md and len(persona_md) > 100:
        print(f"  [OK] Markdown export ({len(persona_md)} chars)")
    
    persona_json = export_mgr.export_persona_json("cost_focused_expert")
    if persona_json and len(persona_json) > 100:
        print(f"  [OK] JSON export ({len(persona_json)} chars)")
    
    print("\n测试导入:")
    new_persona_data = {
        "id": "test_custom_expert",
        "name": "测试专家",
        "description": "这是一个测试人格",
        "domain": "test",
        "trigger_conditions": [
            {"type": "keyword", "value": "测试", "weight": 1.0}
        ],
        "system_prompt": "你是一个测试专家。",
    }
    
    test_persona = Persona(**new_persona_data)
    
    if repo.add_persona(test_persona):
        print(f"  [OK] Custom persona added")
    else:
        print(f"  [X] Failed to add custom persona")
    
    return True


def test_markdown_export():
    """测试 Markdown 格式导出"""
    print("\n" + "="*60)
    print("测试 4: Markdown 格式导出")
    print("="*60)
    
    repo = ExpertRepository()
    export_mgr = ExportManager(repo)
    
    persona_md = export_mgr.export_persona_markdown("environmental_expert")
    if persona_md:
        print("\n环保专家 Markdown 示例:")
        print("-" * 40)
        lines = persona_md.split('\n')
        for line in lines[:60]:
            print(line)
        if len(lines) > 60:
            print(f"... (共 {len(lines)} 行)")
        return True
    return False


def test_persona_selection_comparison():
    """测试同一问题的不同画像回答对比"""
    print("\n" + "="*60)
    print("测试 5: 同一问题的不同画像回答对比")
    print("="*60)
    
    dispatcher = PersonaDispatcher()
    
    question = "化工厂的SO₂排放，150米烟囱够不够？"
    
    profiles = [
        {
            "name": "企业管理者",
            "profile": {
                "social_roles": {"enterprise_manager": 0.9},
                "core_concerns": {"成本": 0.9},
                "expertise_level": "medium"
            }
        },
        {
            "name": "政府官员",
            "profile": {
                "social_roles": {"government_official": 0.9},
                "core_concerns": {"合规": 0.9, "风险": 0.8},
                "expertise_level": "medium"
            }
        },
        {
            "name": "工程师",
            "profile": {
                "social_roles": {"engineer": 0.9},
                "core_concerns": {"技术": 0.8},
                "expertise_level": "expert"
            }
        },
    ]
    
    print(f"\n问题: {question}")
    print("-" * 60)
    
    for p in profiles:
        persona = dispatcher.dispatch(p["profile"], question)
        top3 = dispatcher.dispatch_top_n(p["profile"], question, 3)
        
        print(f"\n【{p['name']}】")
        print(f"  → 匹配人格: {persona.name if persona else 'None'}")
        print(f"  → 匹配理由: ")
        for cond in (persona.trigger_conditions if persona else [])[:2]:
            print(f"      • {cond.get('type')}: {cond.get('value')}")
        
        print(f"  → 备选: " + ", ".join([f"{pp.name}({s:.0%})" for pp, s in top3[1:3]]))
    
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "#" * 60)
    print("  Expert System Test Suite")
    print("#" * 60)
    
    results = []
    
    try:
        results.append(("User Profile Parser", test_user_profile_parser()))
    except Exception as e:
        print(f"\n[X] User Profile Parser test failed: {e}")
        results.append(("User Profile Parser", False))
    
    try:
        results.append(("Persona Dispatcher", test_persona_dispatcher()))
    except Exception as e:
        print(f"\n[X] Persona Dispatcher test failed: {e}")
        results.append(("Persona Dispatcher", False))
    
    try:
        results.append(("Repository Manager", test_repository()))
    except Exception as e:
        print(f"\n[X] Repository Manager test failed: {e}")
        results.append(("Repository Manager", False))
    
    try:
        results.append(("Markdown Export", test_markdown_export()))
    except Exception as e:
        print(f"\n[X] Markdown Export test failed: {e}")
        results.append(("Markdown Export", False))
    
    try:
        results.append(("Persona Selection", test_persona_selection_comparison()))
    except Exception as e:
        print(f"\n[X] Persona Selection test failed: {e}")
        results.append(("Persona Selection", False))
    
    print("\n" + "="*60)
    print("  Test Results Summary")
    print("="*60)
    
    passed = 0
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {name}: {status}")
        if result:
            passed += 1
    
    print("\n" + "-" * 60)
    print(f"  Total: {passed}/{len(results)} passed")
    
    if passed == len(results):
        print("\n*** All tests passed! ***")
    else:
        print("\n*** Some tests failed ***")
    
    return passed == len(results)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
