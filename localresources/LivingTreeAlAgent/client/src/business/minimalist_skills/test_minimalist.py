"""
Minimalist Skills 测试
"""

import sys
import os

# 添加项目根目录到 path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def log(msg, ok=True):
    prefix = "[OK]" if ok else "[FAIL]"
    try:
        print(f"{prefix} {msg}")
    except UnicodeEncodeError:
        safe_msg = msg.replace("\u2713", "OK").replace("\u2717", "X")
        print(f"{prefix} {safe_msg}")


def test_import():
    """测试模块导入"""
    print("\n" + "=" * 50)
    print("Module Import Test")
    print("=" * 50)
    try:
        from core.minimalist_skills import (
            MinimalistSkillLoader,
            MinimalistSkill,
            SkillCategory,
            get_skill_loader,
            clone_skills_repo
        )
        log("Module import successful")
        return True
    except ImportError as e:
        log(f"Module import failed: {e}", ok=False)
        return False


def test_loader():
    """测试加载器"""
    print("\n" + "=" * 50)
    print("Loader Test")
    print("=" * 50)

    from core.minimalist_skills import MinimalistSkillLoader

    # 创建加载器
    loader = MinimalistSkillLoader()
    count = loader.load_all()

    log(f"Loaded {count} skills")
    print("\n  Skills list:")
    for skill_id in sorted(loader.skills.keys()):
        skill = loader.skills[skill_id]
        print(f"    - {skill_id}: {skill.name} ({skill.category.value})")

    return count >= 8


def test_get_skill():
    """测试获取技能"""
    print("\n" + "=" * 50)
    print("Get Skill Test")
    print("=" * 50)

    from core.minimalist_skills import get_skill_loader

    loader = get_skill_loader()

    # 获取 validate-idea
    skill = loader.get_skill("validate-idea")
    if skill:
        log(f"Found skill: {skill.name}")
        print(f"\n  Description: {skill.description}")
        print(f"  Steps count: {len(skill.steps)}")
        print(f"  Checklist count: {len(skill.checklist)}")
        print(f"\n  Body preview (first 200 chars):")
        print(f"    {skill.body[:200]}...")
        return True
    else:
        log("Skill not found", ok=False)
        return False


def test_skill_prompt():
    """测试技能转 Prompt"""
    print("\n" + "=" * 50)
    print("Skill Prompt Test")
    print("=" * 50)

    from core.minimalist_skills import get_skill_loader

    loader = get_skill_loader()

    prompt = loader.get_skill_as_prompt(
        "validate-idea",
        user_context="我想做一个 AI 简历优化服务"
    )

    if prompt:
        log("Prompt generated successfully")
        print(f"\n  Prompt length: {len(prompt)} chars")
        print(f"\n  Preview (first 500 chars):\n")
        print(f"    {prompt[:500]}...")
        return True
    else:
        log("Prompt generation failed", ok=False)
        return False


def test_categories():
    """测试分类功能"""
    print("\n" + "=" * 50)
    print("Categories Test")
    print("=" * 50)

    from core.minimalist_skills import get_skill_loader, SkillCategory

    loader = get_skill_loader()

    categories = loader.get_all_categories()
    log(f"Found {len(categories)} categories")
    print("\n  Categories:")
    for cat in categories:
        skills = loader.list_skills(cat)
        print(f"    - {cat.value}: {len(skills)} skills")

    # 按分类查询
    print("\n  Validation skills:")
    for skill_id in loader.list_skills(SkillCategory.VALIDATION):
        print(f"    - {skill_id}")


def test_skill_info():
    """测试技能信息"""
    print("\n" + "=" * 50)
    print("Skill Info Test")
    print("=" * 50)

    from core.minimalist_skills import get_skill_loader

    loader = get_skill_loader()

    info = loader.get_skill_info("pricing")
    if info:
        log("Got skill info")
        print("\n  Info:")
        for k, v in info.items():
            print(f"    - {k}: {v}")
        return True
    else:
        log("Failed to get skill info", ok=False)
        return False


if __name__ == "__main__":
    results = []

    results.append(("Import", test_import()))
    results.append(("Loader", test_loader()))
    results.append(("Get Skill", test_get_skill()))
    results.append(("Skill Prompt", test_skill_prompt()))
    results.append(("Categories", test_categories()))
    results.append(("Skill Info", test_skill_info()))

    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    for name, ok in results:
        status = "OK" if ok else "X"
        print(f"  [{status}] {name}")

    print(f"\nTotal: {passed}/{total} passed")

    if passed == total:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed")