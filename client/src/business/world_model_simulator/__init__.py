"""
世界模型模拟器 (World Model Simulator)

在执行前模拟环境，预测结果并验证

核心功能:
1. 世界状态管理 - 维护模拟世界的实体和状态
2. 状态转移规则 - 定义动作如何改变世界
3. 结果预测 - 预测动作执行结果
4. 多轨迹模拟 - 探索多种执行路径
5. 预测验证 - 验证预测与实际结果的一致性

快速开始:
```python
from client.src.business.world_model_simulator import (
    WorldModel,
    SimulationEngine,
    SimulationConfig,
    Entity,
    EntityType,
    State
)

# 1. 创建世界模型
world = WorldModel()

# 2. 添加实体
file_entity = Entity(
    entity_id="file1",
    name="test.txt",
    entity_type=EntityType.OBJECT,
    properties={"exists": True, "content": ""}
)
world.add_entity(file_entity)

# 3. 设置初始状态
state = State(state_id="initial")
state.set_entity_state("file1", "exists", True)
state.set_entity_state("file1", "content", "")
world.set_initial_state(state)

# 4. 创建模拟引擎
engine = SimulationEngine()

# 5. 注册执行器
async def write_executor(params):
    return {"success": True, "bytes_written": len(params.get("content", ""))}

engine.register_executor("write_file", write_executor)

# 6. 模拟执行
trajectory = await engine.simulate_and_execute(
    task="写入文件",
    action_sequence=[("write_file", {"path": "test.txt", "content": "Hello"})],
    initial_state=state
)

print(f"预测成功: {trajectory.predicted_outcome}")
print(f"置信度: {trajectory.confidence}")
```

架构:
    SimulationEngine
        ├── WorldModel           (世界状态和转移)
        ├── OutcomePredictor     (结果预测)
        └── SimulationModels     (数据结构)

Author: LivingTreeAI
Version: 1.0.0
"""

# 数据模型
from .simulation_models import (
    EntityType,
    StateType,
    Entity,
    State,
    StateTransition,
    SimulationStep,
    SimulationTrajectory,
    SimulationResult
)

# 世界模型
from .world_model import WorldModel, WorldModelConfig

# 预测器
from .predictors import (
    Prediction,
    OutcomePredictor,
    LLMPredictor,
    EnsemblePredictor,
    RuleBasedPredictor
)

# 模拟引擎
from .simulation_engine import (
    SimulationConfig,
    ExecutorConfig,
    SimulationEngine,
    SafeSimulationEngine
)

# 版本信息
__version__ = "1.0.0"
__author__ = "LivingTreeAI"

# 公开的类列表
__all__ = [
    # 数据模型
    "EntityType",
    "StateType",
    "Entity",
    "State",
    "StateTransition",
    "SimulationStep",
    "SimulationTrajectory",
    "SimulationResult",
    
    # 世界模型
    "WorldModel",
    "WorldModelConfig",
    
    # 预测器
    "Prediction",
    "OutcomePredictor",
    "LLMPredictor",
    "EnsemblePredictor",
    "RuleBasedPredictor",
    
    # 模拟引擎
    "SimulationConfig",
    "ExecutorConfig",
    "SimulationEngine",
    "SafeSimulationEngine",
]
