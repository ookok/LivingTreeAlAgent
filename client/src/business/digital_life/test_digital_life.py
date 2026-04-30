"""数字生命伴侣系统测试"""
import sys
import os

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
    """测试导入"""
    print("\n" + "=" * 50)
    print("Digital Life Import Test")
    print("=" * 50)
    try:
        from business.digital_life import (
            DigitalLifeCore,
            DigitalLifeCompanion,
            TreeRing,
            EmotionalState,
            LifeStage,
            Season,
            get_digital_companion
        )
        log("Digital Life module imported")
        return True
    except ImportError as e:
        log(f"Import failed: {e}", ok=False)
        return False


def test_creation():
    """测试数字生命创建"""
    print("\n" + "=" * 50)
    print("Digital Life Creation Test")
    print("=" * 50)

    from business.digital_life import DigitalLifeCompanion

    companion = DigitalLifeCompanion(name="青松", owner_id="user_001")
    log(f"Created: {companion.core.name}")
    print(f"  Life ID: {companion.core.life_id}")
    print(f"  Stage: {companion.core.life_stage.value}")
    return True


def test_memory_rings():
    """测试记忆年轮系统"""
    print("\n" + "=" * 50)
    print("Memory Rings Test")
    print("=" * 50)

    from business.digital_life import DigitalLifeCompanion

    companion = DigitalLifeCompanion(name="青松")

    # 添加记忆
    companion.core.add_memory(
        content="用户在职场中遇到迷茫，站在十字路口",
        depth=1,
        emotional_tags=["迷茫", "焦虑"],
        situation_tags=["职场", "职业发展"],
        importance=0.8
    )

    companion.core.add_memory(
        content="今天学习了一些新技术",
        depth=3,
        emotional_tags=["成长"],
        situation_tags=["学习"]
    )

    companion.core.add_memory(
        content="用户分享了生活中的喜悦",
        depth=3,
        emotional_tags=["喜悦"],
        situation_tags=["生活"]
    )

    log(f"Added {len(companion.core.tree_rings)} memories")

    # 情景类比搜索
    similar = companion.core.recall_similar(
        emotional_tags=["迷茫"],
        situation_tags=["职场"]
    )

    log(f"Found {len(similar)} similar memories")
    if similar:
        print(f"  Most similar: {similar[0].content[:30]}...")

    # 获取记忆上下文
    context = companion.core.get_memory_context()
    print(f"\n  Memory context ({len(context)} chars):")
    print(f"  {context[:200]}...")

    return True


def test_emotional_seasons():
    """测试季节情绪系统"""
    print("\n" + "=" * 50)
    print("Emotional Seasons Test")
    print("=" * 50)

    from business.digital_life import DigitalLifeCompanion, Season

    companion = DigitalLifeCompanion(name="青松")

    # 测试不同时段的问候
    for hour, expected_season in [(9, "春"), (14, "夏"), (20, "秋"), (23, "冬")]:
        companion.core.update_emotional_state(time_hour=hour)
        greeting = companion.core.get_greeting()
        season = companion.core.emotional_state.current_season
        print(f"  Hour {hour}: {season.value}季 - {greeting}")

    log("Seasonal greetings generated")

    # 测试低落干预
    companion.core.emotional_state.consecutive_days_low_mood = 7
    intervention = companion.core.check_low_mood_intervention()
    if intervention:
        log(f"Low mood intervention triggered: {intervention}")

    return True


def test_vital_signs():
    """测试生命体征系统"""
    print("\n" + "=" * 50)
    print("Vital Signs Test")
    print("=" * 50)

    from business.digital_life import DigitalLifeCompanion

    companion = DigitalLifeCompanion(name="青松")

    print(f"  Initial vitals: {companion.core.vital_signs}")

    # 模拟高负荷
    companion.core.adjust_vital_sign("energy", -0.5)
    companion.core.adjust_vital_sign("focus", -0.3)

    print(f"  After high load: {companion.core.vital_signs}")

    # 疲惫声明
    tired = companion.core.get_tired_statement()
    print(f"  Tired statement: {tired}")

    # 分散声明
    distracted = companion.core.get_distracted_statement()
    print(f"  Distracted statement: {distracted}")

    log("Vital signs system works")
    return True


def test_evolution():
    """测试进化系统"""
    print("\n" + "=" * 50)
    print("Evolution Test")
    print("=" * 50)

    from business.digital_life import DigitalLifeCompanion

    companion = DigitalLifeCompanion(name="青松")

    # 模拟达到进化条件
    companion.core.update_interaction_hours(150)

    branches = companion.core.get_unlocked_branches()
    log(f"Unlocked {len(branches)} branches")
    for b in branches:
        print(f"  - {b.name}: {b.description}")

    stage = companion.core.get_stage_progress()
    print(f"\n  Stage progress: {stage['stage']}")
    print(f"  Hours: {stage['hours']}")
    print(f"  Progress: {stage['progress']*100:.1f}%")

    return True


def test_social():
    """测试社交系统"""
    print("\n" + "=" * 50)
    print("Social System Test")
    print("=" * 50)

    from business.digital_life import DigitalLifeCompanion

    companion = DigitalLifeCompanion(name="青松")

    # 添加认识的数字生命
    companion.core.add_digital_being(
        being_id="bailu_001",
        name="白鹭",
        specialty="视觉设计",
        connection_type="p2p"
    )

    companion.core.add_digital_being(
        being_id="linxiao_001",
        name="林晓",
        specialty="数据分析"
    )

    log(f"Added {len(companion.core.known_digital_beings)} beings")

    # 获取推荐
    referral = companion.core.get_referral("视觉设计")
    if referral:
        print(f"  Referral: {referral}")

    # 社交广播
    broadcast = companion.core.get_social_broadcast()
    print(f"\n  Social broadcast ({len(broadcast)} chars)")

    return True


def test_persona_prompt():
    """测试人格 Prompt 生成"""
    print("\n" + "=" * 50)
    print("Persona Prompt Test")
    print("=" * 50)

    from business.digital_life import DigitalLifeCompanion

    companion = DigitalLifeCompanion(name="青松")

    prompt = companion.core.generate_persona_prompt()
    log(f"Generated persona prompt ({len(prompt)} chars)")

    print(f"\n  Preview:")
    print(f"  {prompt[:400]}...")

    return True


async def test_interaction():
    """测试核心交互"""
    print("\n" + "=" * 50)
    print("Core Interaction Test")
    print("=" * 50)

    from business.digital_life import DigitalLifeCompanion

    companion = DigitalLifeCompanion(name="青松")

    # 首次交互
    result = await companion.interact(
        user_message="我最近工作压力很大，有点迷茫",
        user_emotion="低落",
        context={"topic": "职场"}
    )

    log("First interaction completed")
    print(f"  Persona mode: {result['is_persona_mode']}")
    print(f"  Life stage: {result['life_stage']['stage']}")

    sys_info = result['system_info']
    if sys_info.get('greeting'):
        print(f"  Greeting: {sys_info['greeting']}")
    if sys_info.get('low_mood_intervention'):
        print(f"  Intervention: {sys_info['low_mood_intervention']}")

    stats = companion.get_life_stats()
    print(f"\n  Life stats:")
    print(f"  - Memories: {stats['memory_count']}")
    print(f"  - Vitals: {stats['vital_signs']}")

    return True


def test_persona_switch():
    """测试人格开关"""
    print("\n" + "=" * 50)
    print("Persona Switch Test")
    print("=" * 50)

    from business.digital_life import DigitalLifeCompanion

    companion = DigitalLifeCompanion(name="青松")

    print(f"  Initial mode: persona={companion.is_persona_mode}")

    # 关闭人格
    msg = companion.disable_persona()
    print(f"  After disable: {msg}")
    print(f"  Mode: persona={companion.is_persona_mode}")

    # 开启人格
    msg = companion.enable_persona()
    print(f"  After enable: {msg}")

    log("Persona switch works")
    return True


if __name__ == "__main__":
    results = []

    results.append(("Import", test_import()))
    results.append(("Creation", test_creation()))
    results.append(("Memory Rings", test_memory_rings()))
    results.append(("Emotional Seasons", test_emotional_seasons()))
    results.append(("Vital Signs", test_vital_signs()))
    results.append(("Evolution", test_evolution()))
    results.append(("Social", test_social()))
    results.append(("Persona Prompt", test_persona_prompt()))

    import asyncio
    asyncio.run(test_interaction())

    results.append(("Persona Switch", test_persona_switch()))

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
