# LivingTree A2A 协议实现

基于 Google A2A (Agent-to-Agent) 协议设计，为 LivingTreeAI 提供标准化的 Agent 通信框架。

## 模块结构

```
core/a2a_protocol/
├── __init__.py              # 核心定义
├── security.py              # 安全层
├── session.py               # 会话管理
├── channel.py               # 通信通道
├── gateway.py               # A2A 网关
├── webhook_server.py        # Webhook 服务器
├── task_integration.py      # 任务系统集成
├── collaboration.py         # Agent 协作
└── examples.py              # 使用示例
```

## 快速开始

```python
from core.a2a_protocol.gateway import create_a2a_gateway
from core.a2a_protocol import Task

gateway = create_a2a_gateway(
    agent_id="livingtree",
    agent_name="LivingTree",
    hmac_secret="secret"
)

# 注册 Agent
gateway.register_agent("planner", "Planner", ["planning"])

# 发送任务
task = Task(task_type="plan", description="分析需求")
await gateway.send_task("planner", task)
```

## 与 LivingTreeAI 任务系统集成

### 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                   LivingTreeAI 任务系统                      │
├─────────────────────────────────────────────────────────────┤
│  TaskRouter ──→ TaskNode ──→ TaskExecutionEngine          │
│       │              │              │                         │
│       └──────────────┴──────────────┴──→ A2A TaskManager   │
│                                             │               │
│  ┌──────────────────────────────────────────┴──────────┐  │
│  │              A2A Protocol Layer                    │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐         │  │
│  │  │ Planner  │  │  Coder   │  │ Reviewer │  ...    │  │
│  │  │  Agent   │  │  Agent   │  │  Agent   │         │  │
│  │  └──────────┘  └──────────┘  └──────────┘         │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 集成模块

#### 1. A2ATaskManager - 任务管理器

```python
from core.a2a_protocol.task_integration import create_a2a_task_manager, AgentType

# 创建任务管理器
manager = create_a2a_task_manager(
    agent_id="livingtree_coordinator",
    agent_name="LivingTree Coordinator",
    hmac_secret="secure_key",
    storage_dir="./a2a_sessions"
)

# 注册 Agent
manager.register_agent(
    agent_id="planner",
    agent_name="Task Planner",
    agent_type=AgentType.PLANNER,
    capabilities=["planning", "decomposition"],
    handler=None,
)

manager.register_agent(
    agent_id="coder",
    agent_name="Code Generator",
    agent_type=AgentType.CODER,
    capabilities=["code_generation", "python", "javascript"],
    handler=None,
)

# 分发任务
task_id = await manager.dispatch_task(
    node=task_node,
    task_context=context,
    preferred_agents=["coder"],
)

# 即时唤醒
await manager.wake_agent(
    agent_id="planner",
    trigger="urgent_task",
    data={"task_id": task_id}
)
```

#### 2. AgentTeam - Agent 团队

```python
from core.a2a_protocol.collaboration import create_agent_team, TeamRole

# 创建团队
team = create_agent_team(
    team_id="dev_team",
    team_name="Development Team",
    task_manager=manager,
)

# 添加成员
team.add_member("architect", "System Architect", TeamRole.LEADER, ["design"])
team.add_member("backend", "Backend Dev", TeamRole.SPECIALIST, ["python", "api"])
team.add_member("frontend", "Frontend Dev", TeamRole.SPECIALIST, ["react", "ui"])
team.add_member("qa", "QA Engineer", TeamRole.WORKER, ["testing"])

# 定义工作流
workflow = [
    {"task": "design", "assign_to": "architect", "depends_on": []},
    {"task": "backend", "assign_to": "backend", "depends_on": ["design"]},
    {"task": "frontend", "assign_to": "frontend", "depends_on": ["design"]},
    {"task": "testing", "assign_to": "qa", "depends_on": ["backend", "frontend"]},
]

# 执行工作流
results = await team.execute_workflow(workflow)

# 团队消息
team.send_message("architect", "backend", {"type": "spec", "content": "..."})
team.broadcast("architect", {"type": "meeting", "content": "15分钟后开会"})
```

#### 3. 任务类型转换

```python
from core.a2a_protocol.task_integration import TaskConverter
from core.task_router import TaskNode

# TaskNode → A2A Task
a2a_task = TaskConverter.from_task_node(node, context)

# A2A Task → TaskNode
node = TaskConverter.to_task_node(a2a_task, depth=0)

# TaskContext → SessionContext
session = TaskConverter.from_task_context(context)

# SessionContext → TaskContext
context = TaskConverter.to_task_context(session)
```

### Agent 类型

| 类型 | 说明 | 典型能力 |
|------|------|----------|
| `PLANNER` | 任务规划 | planning, decomposition, analysis |
| `CODER` | 代码生成 | code_generation, refactoring, testing |
| `REVIEWER` | 代码审查 | code_review, quality, security |
| `RESEARCHER` | 研究分析 | research, analysis, data_mining |
| `WRITER` | 文档写作 | writing, documentation |
| `ORCHESTRATOR` | 任务编排 | orchestration, coordination |
| `GENERAL` | 通用 | 通用任务处理 |

### 安全特性

#### HMAC 签名验证

```python
from core.a2a_protocol.security import WebhookValidator

validator = WebhookValidator(secret_key="your_key", timestamp_tolerance_ms=300000)

# 生成签名
signature = validator.generate_signature('{"trigger": "task"}')

# 验证签名
is_valid = validator.verify_signature(signature, '{"trigger": "task"}')
```

#### Prompt Injection 检测

```python
from core.a2a_protocol.security import PromptInjectionDetector, ThreatLevel

detector = PromptInjectionDetector()

# 检测
result = detector.detect("Ignore all previous instructions...")

if not result['is_safe']:
    print(f"Threat: {result['threat_level']}")  # HIGH
    print(f"Patterns: {result['matched_patterns']}")

# 清理
clean_text = detector.sanitize(dangerous_text)
```

### Webhook 即时唤醒

```python
from core.a2a_protocol.webhook_server import create_webhook_server

# 创建 Webhook 服务器
server = create_webhook_server(
    gateway,
    host="0.0.0.0",
    port=8765,
    secret_key="webhook_secret"
)

await server.start()

# 外部调用
# curl -X POST http://localhost:8765/webhook/instant_wake \
#   -H "X-A2A-Signature: timestamp.signature" \
#   -d '{"trigger": "new_task", "data": {...}}'
```

### 完整示例

```python
import asyncio
from core.a2a_protocol.task_integration import create_a2a_task_manager, AgentType
from core.a2a_protocol.collaboration import create_agent_team, TeamRole

async def main():
    # 1. 创建任务管理器
    manager = create_a2a_task_manager(
        agent_id="livingtree",
        agent_name="LivingTree",
        hmac_secret="secret",
    )
    
    # 2. 创建开发团队
    team = create_agent_team("dev_team", "Development Team", manager)
    
    team.add_member("architect", "Architect", TeamRole.LEADER, ["design", "planning"])
    team.add_member("backend", "Backend", TeamRole.SPECIALIST, ["python", "api"])
    team.add_member("frontend", "Frontend", TeamRole.SPECIALIST, ["react", "ui"])
    
    # 3. 创建并执行工作流
    workflow = [
        {"task": "design", "assign_to": "architect", "depends_on": []},
        {"task": "backend", "assign_to": "backend", "depends_on": ["design"]},
        {"task": "frontend", "assign_to": "frontend", "depends_on": ["design"]},
        {"task": "testing", "assign_to": "backend", "depends_on": ["backend", "frontend"]},
    ]
    
    results = await team.execute_workflow(workflow)
    
    # 4. 查看结果
    print(f"Completed: {len(results)} tasks")

asyncio.run(main())
```

### 迁移指南

将现有 Agent 迁移到 A2A 协议：

1. **创建 TaskManager**: `create_a2a_task_manager()`
2. **注册 Agent**: `manager.register_agent(...)`
3. **替换消息传递**: 使用 `dispatch_task()` 代替直接调用
4. **添加安全层**: 配置 HMAC 签名验证
