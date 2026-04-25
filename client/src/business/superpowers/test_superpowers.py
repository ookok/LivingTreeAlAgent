"""Superpowers + HermesAgent 集成测试"""
import sys
import os
import asyncio

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


def test_superpowers_import():
    """测试 Superpowers 导入"""
    print("\n" + "=" * 50)
    print("Superpowers Import Test")
    print("=" * 50)
    try:
        from client.src.business.superpowers import (
            SuperpowerRegistry,
            WorkflowRecorder,
            WorkflowPlayer,
            Workflow,
            Superpower,
            StepType,
            get_superpower_registry
        )
        log("Superpowers module imported")
        return True
    except ImportError as e:
        log(f"Import failed: {e}", ok=False)
        return False


def test_hermes_agent_import():
    """测试 HermesAgent 导入"""
    print("\n" + "=" * 50)
    print("HermesAgent Import Test")
    print("=" * 50)
    try:
        from client.src.business.hermes_agent import (
            UserProfileManager,
            UserProfile,
            UserPreference,
            PreferenceType,
            get_profile_manager,
            get_current_user_context
        )
        log("HermesAgent module imported")
        return True
    except ImportError as e:
        log(f"Import failed: {e}", ok=False)
        return False


def test_superpowers_workflow():
    """测试工作流录制"""
    print("\n" + "=" * 50)
    print("Superpowers Workflow Test")
    print("=" * 50)

    from client.src.business.superpowers import (
        WorkflowRecorder,
        SuperpowerRegistry,
        Superpower,
        StepType,
        Workflow
    )

    # 录制工作流
    recorder = WorkflowRecorder("wf_test_001", "测试工作流")
    recorder.start_recording()

    recorder.record_step(
        StepType.INPUT,
        name="product_name",
        params={"required": True}
    )
    recorder.record_step(
        StepType.INPUT,
        name="price",
        params={"type": "number"}
    )
    recorder.record_step(
        StepType.ACTION,
        name="validate",
        params={"action": "validate_input"}
    )
    recorder.record_step(
        StepType.OUTPUT,
        name="result"
    )

    workflow = recorder.stop_recording()
    log(f"Workflow recorded: {workflow.name} ({len(workflow.steps)} steps)")

    # 测试注册表
    registry = SuperpowerRegistry()
    sp = Superpower(
        id="sp_test",
        name="测试技能",
        description="测试用超级能力",
        workflow=workflow,
        triggers=["测试", "test"]
    )
    registry.register(sp)

    found = registry.get("sp_test")
    log(f"Superpower registered and retrieved: {found is not None}")

    return True


def test_hermes_agent_profile():
    """测试用户画像"""
    print("\n" + "=" * 50)
    print("HermesAgent Profile Test")
    print("=" * 50)

    from client.src.business.hermes_agent import (
        UserProfileManager,
        PreferenceType,
        get_profile_manager
    )

    manager = get_profile_manager()

    # 创建测试用户
    profile = manager.get_or_create_profile("test_user_001", "测试用户")
    log(f"Profile created: {profile.name}")

    # 设置当前用户
    manager.set_current_user("test_user_001")

    # 记录交互
    record = manager.record_interaction(
        user_id="test_user_001",
        query="帮我设置一个满300减50的优惠活动",
        response="好的，已为您设置满减活动",
        context={"topic": "电商促销"},
        agents=["ecommerce_advisor"],
        tools=["relay_llm"]
    )
    log(f"Interaction recorded: {record.id}")

    # 学习事实
    manager.learn_fact("test_user_001", "主营类目", "数码产品")
    manager.learn_fact("test_user_001", "常用物流", "顺丰")

    # 记录反馈
    manager.record_feedback(record.id, "thumbs_up", rating=1.0)
    log("Feedback recorded")

    # 获取上下文
    ctx = manager.get_context_for_llm("test_user_001", max_history=5)
    log(f"Context generated ({len(ctx)} chars)")

    print("\n  Context Preview:")
    print(f"  {ctx[:300]}...")

    return True


async def test_superpowers_execution():
    """测试工作流执行"""
    print("\n" + "=" * 50)
    print("Superpowers Execution Test")
    print("=" * 50)

    from client.src.business.superpowers import (
        Workflow,
        WorkflowStep,
        WorkflowPlayer,
        StepType
    )

    # 创建测试工作流
    steps = [
        WorkflowStep(
            id="s1",
            type=StepType.INPUT,
            name="product_name",
            params={}
        ),
        WorkflowStep(
            id="s2",
            type=StepType.ACTION,
            name="mock_action",
            params={"action": "mock_action", "params": {}}
        )
    ]

    workflow = Workflow(
        id="wf_exec_test",
        name="执行测试工作流",
        steps=steps
    )

    # 执行
    async def mock_callback(**kwargs):
        print(f"    [Callback] Action executed with: {kwargs}")
        return {"status": "ok", "result": "mocked"}

    player = WorkflowPlayer(workflow)
    result = await player.execute(
        input_params={"product_name": "iPhone 15"},
        callbacks={"mock_action": mock_callback}
    )

    log(f"Workflow executed: {result}")
    return True


if __name__ == "__main__":
    results = []

    results.append(("Superpowers Import", test_superpowers_import()))
    results.append(("HermesAgent Import", test_hermes_agent_import()))
    results.append(("Superpowers Workflow", test_superpowers_workflow()))
    results.append(("HermesAgent Profile", test_hermes_agent_profile()))
    asyncio.run(test_superpowers_execution())

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
