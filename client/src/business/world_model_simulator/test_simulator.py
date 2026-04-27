"""
世界模型模拟器测试

测试模拟执行的核心功能
"""

import asyncio
import sys
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent')

from client.src.business.world_model_simulator import (
    WorldModel,
    SimulationEngine,
    Entity,
    EntityType,
    State,
    StateTransition,
    SimulationConfig,
    RuleBasedPredictor,
    Prediction
)


def test_world_model():
    """Test 1: World Model Basic"""
    print("\n" + "="*50)
    print("Test 1: World Model Basic")
    print("="*50)
    
    # 创建世界模型
    world = WorldModel()
    
    # 添加实体
    agent = Entity(
        entity_id="agent1",
        name="AI Agent",
        entity_type=EntityType.AGENT,
        properties={"x": 0, "y": 0, "energy": 100}
    )
    world.add_entity(agent)
    
    file_entity = Entity(
        entity_id="file1",
        name="test.txt",
        entity_type=EntityType.OBJECT,
        properties={"exists": False, "content": ""}
    )
    world.add_entity(file_entity)
    
    print(f"Entities added: {len(world._entities)}")
    
    # 设置初始状态
    state = State(state_id="initial")
    state.set_entity_state("agent1", "x", 0)
    state.set_entity_state("agent1", "y", 0)
    state.set_entity_state("agent1", "energy", 100)
    state.set_entity_state("file1", "exists", False)
    
    world.set_initial_state(state)
    print(f"Initial state set: {state.state_id}")
    
    # 注册转移规则
    move_transition = StateTransition(
        transition_id="move",
        action="move",
        effects=[
            {"type": "increment", "entity_id": "agent1", "key": "x", "delta": 1}
        ]
    )
    world.register_transition(move_transition)
    
    # 预测下一步
    next_state = world.predict_next_state(state, "move", {"dx": 1})
    
    if next_state:
        print(f"Predicted next state: agent1.x = {next_state.get_entity_state('agent1', 'x')}")
    
    # 模拟轨迹
    actions = [
        ("move", {"dx": 1}),
        ("move", {"dx": 1}),
        ("move", {"dx": 1})
    ]
    
    trajectory = world.simulate_trajectory("Move agent", actions, state)
    
    print(f"\nTrajectory:")
    print(f"  Length: {trajectory.length}")
    print(f"  Valid: {trajectory.is_valid}")
    print(f"  Score: {trajectory.score:.3f}")
    
    return True


def test_prediction():
    """Test 2: Outcome Prediction"""
    print("\n" + "="*50)
    print("Test 2: Outcome Prediction")
    print("="*50)
    
    predictor = RuleBasedPredictor()
    
    # 创建测试状态
    state = State(state_id="test")
    state.set_entity_state("file1", "exists", True)
    state.set_entity_state("file1", "content", "original")
    
    # 预测搜索
    pred = predictor.predict("search", state, {"query": "test"})
    print(f"\nSearch prediction:")
    print(f"  Success: {pred.success}")
    print(f"  Confidence: {pred.confidence:.2f}")
    print(f"  Uncertainty: {pred.uncertainty:.2f}")
    
    # 预测读取文件
    pred = predictor.predict("read_file", state, {"file_path": "test.txt"})
    print(f"\nRead file prediction:")
    print(f"  Success: {pred.success}")
    print(f"  Confidence: {pred.confidence:.2f}")
    
    # 预测写入文件
    pred = predictor.predict("write_file", state, {"file_path": "test.txt", "content": "new content"})
    print(f"\nWrite file prediction:")
    print(f"  Success: {pred.success}")
    print(f"  Confidence: {pred.confidence:.2f}")
    
    return True


async def test_simulation_engine():
    """Test 3: Simulation Engine"""
    print("\n" + "="*50)
    print("Test 3: Simulation Engine")
    print("="*50)
    
    # 创建引擎
    config = SimulationConfig(max_simulations=5)
    engine = SimulationEngine(config=config)
    
    # 创建世界模型
    world = WorldModel()
    
    # 添加实体
    agent = Entity(
        entity_id="agent1",
        name="AI Agent",
        entity_type=EntityType.AGENT,
        properties={"tasks_completed": 0}
    )
    world.add_entity(agent)
    
    # 设置初始状态
    state = State(state_id="initial")
    state.set_entity_state("agent1", "tasks_completed", 0)
    world.set_initial_state(state)
    
    engine.world_model = world
    
    # 注册模拟执行器
    async def task_executor(params):
        await asyncio.sleep(0.01)  # 模拟执行
        return {"success": True, "task": params.get("task")}
    
    engine.register_executor("execute_task", task_executor)
    
    # 模拟任务序列
    task = "Complete multiple tasks"
    action_sequence = [
        ("execute_task", {"task": "task1"}),
        ("execute_task", {"task": "task2"}),
        ("execute_task", {"task": "task3"})
    ]
    
    # 执行模拟
    trajectory, result = await engine.simulate_and_execute(
        task=task,
        action_sequence=action_sequence,
        initial_state=state,
        verify=False
    )
    
    print(f"\nSimulation result:")
    print(f"  Trajectory ID: {trajectory.trajectory_id}")
    print(f"  Length: {trajectory.length}")
    print(f"  Valid: {trajectory.is_valid}")
    print(f"  Confidence: {trajectory.confidence:.3f}")
    print(f"  Score: {trajectory.score:.3f}")
    
    if result:
        print(f"  Execution results: {len(result)} steps")
    
    return trajectory.is_valid


async def test_multi_trajectory():
    """Test 4: Multi-Trajectory Exploration"""
    print("\n" + "="*50)
    print("Test 4: Multi-Trajectory Exploration")
    print("="*50)
    
    engine = SimulationEngine()
    
    # 定义不同的执行路径
    path1 = [("search", {"query": "AI"}), ("analyze", {})]
    path2 = [("search", {"query": "machine learning"}), ("analyze", {})]
    path3 = [("search", {"query": "deep learning"}), ("analyze", {})]
    
    action_sequences = [path1, path2, path3]
    
    # 探索
    result = await engine.explore_and_select(
        task="Research AI topic",
        action_sequences=action_sequences
    )
    
    print(f"\nExploration result:")
    print(f"  Total trajectories: {len(result.trajectories)}")
    print(f"  Best trajectory: {result.best_trajectory.trajectory_id if result.best_trajectory else None}")
    print(f"  Best score: {result.best_trajectory.score if result.best_trajectory else 0:.3f}")
    print(f"  Simulation time: {result.simulation_time:.3f}s")
    
    for i, traj in enumerate(result.trajectories):
        print(f"\n  Path {i+1}:")
        print(f"    Valid: {traj.is_valid}")
        print(f"    Confidence: {traj.confidence:.3f}")
        print(f"    Score: {traj.score:.3f}")
    
    return len(result.trajectories) == 3


async def test_state_transitions():
    """Test 5: State Transitions"""
    print("\n" + "="*50)
    print("Test 5: State Transitions")
    print("="*50)
    
    world = WorldModel()
    
    # 创建实体
    counter = Entity(
        entity_id="counter",
        name="Counter",
        entity_type=EntityType.OBJECT,
        properties={"value": 0}
    )
    world.add_entity(counter)
    
    # 设置状态
    state = State(state_id="start")
    state.set_entity_state("counter", "value", 0)
    
    # 注册转移
    increment = StateTransition(
        transition_id="inc",
        action="increment",
        effects=[
            {"type": "increment", "entity_id": "counter", "key": "value", "delta": 1}
        ]
    )
    world.register_transition(increment)
    
    print(f"Initial value: {state.get_entity_state('counter', 'value')}")
    
    # 应用转移
    new_state, success, unsatisfied = world.apply_transition(state, increment)
    
    print(f"After increment:")
    print(f"  Success: {success}")
    print(f"  New value: {new_state.get_entity_state('counter', 'value')}")
    
    # 连续增加
    current = state
    for i in range(5):
        current, success, _ = world.apply_transition(current, increment)
    
    print(f"\nAfter 5 more increments:")
    print(f"  Final value: {current.get_entity_state('counter', 'value')}")
    
    return current.get_entity_state('counter', 'value') == 6


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("[WORLD MODEL SIMULATOR TEST SUITE]")
    print("="*60)
    
    tests = [
        ("World Model Basic", test_world_model),
        ("Outcome Prediction", test_prediction),
        ("Simulation Engine", test_simulation_engine),
        ("Multi-Trajectory", test_multi_trajectory),
        ("State Transitions", test_state_transitions)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                success = await test_func()
            else:
                success = test_func()
            results.append((name, success))
            print(f"\n[PASS] {name}")
        except Exception as e:
            results.append((name, False))
            print(f"\n[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
    
    # 总结
    print("\n" + "="*60)
    print("[TEST SUMMARY]")
    print("="*60)
    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    for name, success in results:
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {name}")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
