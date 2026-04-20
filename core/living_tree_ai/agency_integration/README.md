# Agency-Agents 集成文档

## 1. 集成概述

本模块将 agency-agents 的 140+ 专业角色和工作流程集成到 LivingTreeAI 分布式系统中，实现以下目标：

- 丰富 LivingTreeAI 的专业能力覆盖
- 提供标准化的工作流程执行
- 实现角色知识的分布式共享
- 优化任务分配和执行效率

## 2. 目录结构

```
core/living_tree_ai/agency_integration/
├── __init__.py            # 模块初始化
├── README.md              # 本文档
├── ARCHITECTURE.md        # 架构设计文档
├── role_manager.py        # 角色管理器
├── workflow_mapper.py     # 工作流程映射器
├── knowledge_importer.py  # 知识导入器
├── knowledge_integration.py # 知识集成器
├── test_workflow_mapping.py # 工作流程映射测试
├── test_knowledge_integration.py # 知识集成测试
├── test_integration.py    # 集成功能测试
└── simple_test.py         # 简化测试
```

## 3. 核心组件

### 3.1 角色管理器 (RoleManager)

负责管理 agency-agents 角色模板，包括：

- 加载内置角色模板
- 创建角色节点
- 管理角色配置

**主要功能：**
- `load_builtin_templates()`: 加载内置角色模板
- `create_role_node(role_name)`: 根据角色创建专业节点
- `get_all_roles()`: 获取所有可用角色

### 3.2 工作流程映射器 (WorkflowMapper)

将 agency-agents 工作流程映射为 LivingTreeAI 任务链，包括：

- 加载工作流程定义
- 生成任务链
- 管理工作流程配置

**主要功能：**
- `load_builtin_workflows()`: 加载内置工作流程
- `map_to_task_chain(workflow_name, input_data)`: 将工作流程映射为任务链
- `get_all_workflows()`: 获取所有可用工作流程

### 3.3 知识导入器 (KnowledgeImporter)

负责导入 agency-agents 角色知识，包括：

- 加载角色知识
- 管理知识存储
- 提供知识查询

**主要功能：**
- `load_builtin_knowledge()`: 加载内置角色知识
- `import_role_knowledge(knowledge)`: 导入角色知识
- `get_role_knowledge(role_name)`: 获取角色知识

### 3.4 知识集成器 (KnowledgeIntegrator)

将角色知识集成到 LivingTreeAI 知识系统，包括：

- 集成角色知识到知识库
- 管理知识更新
- 提供知识统计

**主要功能：**
- `integrate_role_knowledge(role_name)`: 集成单个角色知识
- `integrate_all_roles()`: 集成所有角色知识
- `get_integrated_roles()`: 获取已集成的角色

## 4. 安装和配置

### 4.1 依赖安装

```bash
# 安装必要的依赖
pip install -r requirements.txt
```

### 4.2 配置文件

集成模块会在 `~/.living_tree_ai/agency/` 目录下存储配置和数据：

- `role_templates/`: 角色模板存储目录
- `workflows/`: 工作流程定义存储目录
- `knowledge/`: 角色知识存储目录

## 5. 使用方法

### 5.1 基本使用

```python
from core.living_tree_ai.agency_integration import RoleManager, WorkflowMapper, KnowledgeIntegrator
from core.living_tree_ai.knowledge import KnowledgeBase

# 初始化角色管理器
role_manager = RoleManager()

# 初始化工作流程映射器
workflow_mapper = WorkflowMapper()

# 初始化知识库
kb = KnowledgeBase("your_node_id")

# 初始化知识集成器
integrator = KnowledgeIntegrator(kb, "your_node_id")

# 创建角色节点
node = role_manager.create_role_node("Full Stack Engineer")

# 集成角色知识
integrator.integrate_role_knowledge("Full Stack Engineer")

# 映射工作流程为任务链
task_chain = workflow_mapper.map_to_task_chain("full_stack_dev", {
    "requirements": "创建一个待办事项应用"
})

# 启动节点
await node.start()

# 提交任务
for task in task_chain:
    task_id = node.submit_task(
        task_type=task.task_type,
        input_data=task.input_data,
        priority=task.priority
    )

# 等待任务执行
await asyncio.sleep(5)

# 查看节点状态
status = node.get_status()
print(f"已完成任务: {status['task_completed']}")

# 停止节点
await node.stop()
```

### 5.2 高级使用

#### 自定义角色

```python
from core.living_tree_ai.agency_integration.role_manager import RoleTemplate

# 创建自定义角色模板
template = RoleTemplate(
    name="DevOps Engineer",
    domain="engineering",
    skills=["Docker", "Kubernetes", "CI/CD", "Infrastructure as Code"],
    description="DevOps工程师，负责基础设施和部署",
    workflow="devops_workflow",
    deliverables=["部署配置", "CI/CD管道", "监控系统"]
)

# 保存角色模板
role_manager.save_role_template(template)

# 创建角色节点
node = role_manager.create_role_node("DevOps Engineer")
```

#### 自定义工作流程

```python
from core.living_tree_ai.agency_integration.workflow_mapper import Workflow, WorkflowStep

# 创建工作流程步骤
steps = [
    WorkflowStep(
        name="需求分析",
        description="分析部署需求",
        task_type="inference",
        required_skills=["需求分析", "基础设施设计"],
        input_schema={"requirements": "string"},
        output_schema={"analysis": "string", "infrastructure_plan": "string"}
    ),
    # 添加更多步骤...
]

# 创建工作流程
workflow = Workflow(
    name="devops_workflow",
    description="DevOps工作流程",
    steps=steps,
    input_schema={"requirements": "string"},
    output_schema={"deployment_config": "string"}
)

# 保存工作流程
workflow_mapper.save_workflow(workflow)
```

## 6. 示例应用

### 6.1 全栈开发工作流程

```python
# 初始化组件
role_manager = RoleManager()
workflow_mapper = WorkflowMapper()

# 创建全栈工程师节点
node = role_manager.create_role_node("Full Stack Engineer")

# 生成任务链
input_data = {
    "requirements": "创建一个简单的待办事项应用，包含添加、删除、标记完成功能"
}
task_chain = workflow_mapper.map_to_task_chain("full_stack_dev", input_data)

# 启动节点并执行任务
await node.start()
for task in task_chain:
    node.submit_task(
        task_type=task.task_type,
        input_data=task.input_data,
        priority=task.priority
    )

# 等待执行完成
await asyncio.sleep(10)

# 查看结果
status = node.get_status()
print(f"完成任务数: {status['task_completed']}")

await node.stop()
```

### 6.2 UI设计工作流程

```python
# 初始化组件
role_manager = RoleManager()
workflow_mapper = WorkflowMapper()

# 创建UI设计师节点
node = role_manager.create_role_node("UI Designer")

# 生成任务链
input_data = {
    "requirements": "为待办事项应用设计一个现代、简洁的用户界面"
}
task_chain = workflow_mapper.map_to_task_chain("ui_design", input_data)

# 启动节点并执行任务
await node.start()
for task in task_chain:
    node.submit_task(
        task_type=task.task_type,
        input_data=task.input_data,
        priority=task.priority
    )

# 等待执行完成
await asyncio.sleep(10)

# 查看结果
status = node.get_status()
print(f"完成任务数: {status['task_completed']}")

await node.stop()
```

## 7. 常见问题和解决方案

### 7.1 导入错误

**问题**：`ImportError: attempted relative import with no known parent package`

**解决方案**：确保在正确的目录中运行代码，或者添加正确的系统路径。

### 7.2 任务队列错误

**问题**：`TypeError: '<' not supported between instances of 'Task' and 'Task'`

**解决方案**：确保 Task 类实现了 `__lt__` 方法，用于优先级队列排序。

### 7.3 知识集成失败

**问题**：角色知识集成到知识库失败

**解决方案**：检查知识库初始化是否正确，确保知识导入器能够正常加载角色知识。

### 7.4 工作流程映射失败

**问题**：工作流程映射为任务链失败

**解决方案**：检查工作流程定义是否正确，确保工作流程名称存在。

## 8. 性能优化

### 8.1 任务分配优化

- **能力匹配**：基于节点能力和任务需求进行匹配
- **负载均衡**：考虑节点当前负载
- **网络延迟**：考虑节点网络延迟
- **历史表现**：考虑节点历史执行表现

### 8.2 知识管理优化

- **知识缓存**：缓存常用角色知识
- **知识更新**：定期更新角色知识
- **知识共享**：在节点间共享知识
- **知识压缩**：压缩存储知识

## 9. 扩展与维护

### 9.1 角色扩展

- **自定义角色**：支持用户自定义角色
- **角色组合**：支持角色能力组合
- **角色进化**：基于执行结果优化角色能力

### 9.2 工作流程扩展

- **自定义工作流程**：支持用户自定义工作流程
- **工作流程模板**：提供工作流程模板
- **工作流程优化**：基于执行结果优化工作流程

### 9.3 知识扩展

- **知识贡献**：支持用户贡献知识
- **知识验证**：验证知识质量
- **知识演进**：基于反馈改进知识

## 10. 未来展望

- **自组织角色网络**：角色节点自动形成专业网络
- **动态角色进化**：基于实际执行效果自动调整角色能力
- **跨领域协作**：不同专业角色节点协同完成复杂任务
- **智能工作流程**：基于 AI 优化工作流程
- **生态系统扩展**：构建角色和工作流程的生态系统

## 11. 结论

Agency-Agents 与 LivingTreeAI 的集成为分布式 AI 系统带来了丰富的专业能力和标准化的工作流程。通过角色系统、工作流程映射和知识集成，LivingTreeAI 不仅具备分布式计算能力，还拥有丰富的专业领域知识和标准化工作流程，从而能够处理更加复杂的实际应用场景。

这种集成将使 LivingTreeAI 成为一个更加全面、高效的 AI 协作平台，为用户提供从需求分析到解决方案的端到端服务。