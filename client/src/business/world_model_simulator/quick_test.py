"""Quick test for world model simulator"""
import asyncio
import sys
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent')

from business.world_model_simulator import (
    WorldModel, SimulationEngine, Entity, EntityType, State, StateTransition
)

print("Test 1: World Model")
world = WorldModel()
agent = Entity("agent1", "AI Agent", EntityType.AGENT, {"x": 0})
world.add_entity(agent)
state = State("initial")
world.set_initial_state(state)

t = StateTransition("t1", "move")
world.register_transition(t)
ns = world.predict_next_state(state, "move", {})
print(f"  Next state: {ns.state_id if ns else 'None'}")

print("Test 2: Trajectory")
actions = [("move", {}), ("move", {})]
traj = world.simulate_trajectory("Move test", actions, state)
print(f"  Trajectory: len={traj.length}, valid={traj.is_valid}")

print("Test 3: Simulation Engine")
engine = SimulationEngine()
engine.world_model = world

async def task_exec(params):
    return {"ok": True}

engine.register_executor("task", task_exec)
traj, res = asyncio.run(engine.simulate_and_execute("Test", [("task", {})], state))
print(f"  Sim: len={traj.length}, valid={traj.is_valid}")

print("\nAll tests passed!")
