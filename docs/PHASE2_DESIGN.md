# LivingTreeAI Phase 2 设计文档

**版本**: v2.0  
**状态**: 进行中  
**日期**: 2026-04-26

---

## Phase 2 概述

Phase 2 聚焦于**智能代理高级功能**，实现多代理协作、动态任务分解、代理生命周期管理等核心能力。

### 核心目标

1. **多代理协作工作流** - 支持复杂的多智能体任务协作
2. **动态任务分解** - 将复杂任务自动分解为可执行的子任务
3. **代理生命周期管理** - 管理代理的创建、激活、休眠、销毁

---

## 核心模块

### 1. MultiAgentWorkflow

多代理协作工作流引擎，支持复杂的多智能体任务协作。

| 功能 | 说明 |
|------|------|
| 代理注册 | 注册多个代理到工作流 |
| 任务管理 | 创建、分配、执行任务 |
| 依赖管理 | 支持任务依赖关系 |
| 异步执行 | 支持异步执行工作流 |
| 结果收集 | 收集所有任务结果 |

**架构**:
```
MultiAgentWorkflow
├── agents: Dict[str, Agent]
├── tasks: Dict[str, Task]
├── steps: List[WorkflowStep]
└── status: str
```

### 2. DynamicTaskDecomposer

动态任务分解器，将复杂任务自动分解为可执行的子任务。

| 分解模式 | 说明 |
|----------|------|
| parallel | 并行分解，独立子任务 |
| sequential | 顺序分解，有先后顺序 |
| hierarchical | 分层分解，主任务+子任务 |
| dag | DAG分解，依赖图 |

### 3. AgentLifecycleManager

代理生命周期管理器，管理代理的创建、激活、休眠、销毁。

| 功能 | 说明 |
|------|------|
| 工厂模式 | 支持自定义代理工厂 |
| 代理池 | 支持代理池管理 |
| 生命周期钩子 | 支持创建/启动/停止/销毁钩子 |

---

## 使用示例

### 1. 多代理协作工作流

```python
from client.src.business.multi_agent import (
    MultiAgentWorkflow, AgentRole
)

# 创建工作流
workflow = MultiAgentWorkflow("wf1", "测试工作流")

# 注册代理
workflow.register_agent("coder", "代码代理", AgentRole.EXECUTOR, ["coding"])
workflow.register_agent("tester", "测试代理", AgentRole.EXECUTOR, ["testing"])

# 创建任务
task1 = workflow.create_task("编写登录功能")
task2 = workflow.create_task("编写测试用例", dependencies=[task1.id])
task3 = workflow.create_task("运行测试", dependencies=[task2.id])

# 分配任务
workflow.assign_task(task1.id, "coder")
workflow.assign_task(task2.id, "tester")
workflow.assign_task(task3.id, "tester")

# 执行工作流
result = workflow.execute_sync()
print(result)
```

### 2. 动态任务分解

```python
from client.src.business.multi_agent import DynamicTaskDecomposer

decomposer = DynamicTaskDecomposer()

# 自动检测模式
tasks = decomposer.decompose("写代码 和 测试代码 和 部署代码")

# 指定模式
tasks = decomposer.decompose("首先分析，然后实现，最后测试", mode='sequential')

for task in tasks:
    print(f"{task.id}: {task.description}")
```

### 3. 代理生命周期管理

```python
from client.src.business.multi_agent import AgentLifecycleManager, Agent, AgentRole

manager = AgentLifecycleManager()

# 注册工厂
def coder_factory(name, **kwargs):
    return Agent(id="1", name=name, role=AgentRole.EXECUTOR, capabilities=["coding"])

manager.register_factory("coder", coder_factory)

# 创建代理
agent = manager.create_agent("coder", "我的代码代理")

# 生命周期钩子
manager.register_hook('on_start', lambda a: print(f"启动: {a.name}"))
manager.register_hook('on_stop', lambda a: print(f"停止: {a.name}"))

# 启动/停止代理
manager.start_agent(agent.id)
manager.stop_agent(agent.id)

# 代理池
manager.add_to_pool("default", agent)
idle_agent = manager.get_from_pool("default")
```

---

## 文件结构

```
core/multi_agent/
├── __init__.py              # 模块入口
├── workflow_engine.py        # 核心引擎 (MultiAgentWorkflow, DynamicTaskDecomposer, AgentLifecycleManager)
└── ...

tests/
├── test_phase2_multi_agent.py  # 单元测试
└── ...
```

---

## 测试覆盖

| 测试类 | 覆盖功能 |
|--------|----------|
| TestMultiAgentWorkflow | 工作流创建、代理注册、任务管理、依赖关系 |
| TestDynamicTaskDecomposer | 并行/顺序分解、自动模式检测 |
| TestAgentLifecycleManager | 工厂注册、代理池、生命周期钩子 |

---

## 下一步

1. 集成 Phase 1 的 A2A 协议
2. 集成 Phase 1 的 AgentOrchestrator
3. 实现更复杂的任务分解算法
4. 添加性能监控和优化

---

**LivingTreeAI Phase 2 进行中... 🚀**
