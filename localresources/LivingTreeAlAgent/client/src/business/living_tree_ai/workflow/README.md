# 工作流模块文档

## 1. 模块概述

工作流模块是 LivingTreeAI 的核心功能之一，提供了可视化的 AI 工作流构建、执行和管理能力。该模块允许用户通过拖拽方式创建复杂的 AI 工作流，支持多种节点类型和执行方式。

## 2. 核心功能

- **可视化工作流编辑**：通过拖拽方式创建和管理工作流
- **丰富的节点类型**：内置多种节点类型，包括控制流、AI、工具、知识库等
- **实时执行可视化**：实时显示工作流执行进度和状态
- **模板管理**：支持工作流模板的导入、导出和管理
- **画布辅助功能**：支持缩放、网格、对齐等辅助功能

## 3. 目录结构

```
workflow/
├── __init__.py              # 模块初始化文件
├── README.md                # 文档
├── ARCHITECTURE.md          # 架构设计文档
├── models/                  # 数据模型
│   ├── __init__.py
│   ├── workflow.py          # 工作流模型
│   ├── node.py              # 节点模型
│   ├── connection.py        # 连接模型
│   └── types.py             # 类型定义
├── registry/                # 节点注册表
│   ├── __init__.py
│   ├── node_registry.py     # 节点注册表实现
│   └── builtin_nodes.py     # 内置节点定义
├── engine/                  # 执行引擎
│   ├── __init__.py
│   ├── converter.py         # 任务链转换器
│   ├── executor.py          # 工作流执行器
│   └── validator.py         # 工作流验证器
├── template_manager.py      # 模板管理器
└── dify_tools.py            # Dify 工具适配器
```

## 4. 核心组件

### 4.1 工作流模型 (Workflow)

工作流是由节点和连接组成的有向图，用于定义 AI 任务的执行流程。

**主要功能**：
- 创建和管理工作流
- 添加和删除节点
- 添加和删除连接
- 保存和加载工作流

**使用示例**：
```python
from living_tree_ai.workflow import Workflow, WorkflowNodeModel, NodeConnection, NodeType

# 创建工作流
workflow = Workflow(
    workflow_id="test_workflow",
    name="测试工作流",
    description="用于测试的工作流"
)

# 添加节点
start_node = WorkflowNodeModel(
    node_id="start",
    node_type=NodeType.START,
    name="开始",
    position={"x": 100, "y": 200}
)
workflow.add_node(start_node)

# 添加连接
connection = NodeConnection(
    connection_id="conn1",
    source_node_id="start",
    source_port="output",
    target_node_id="llm",
    target_port="prompt"
)
workflow.add_connection(connection)
```

### 4.2 节点模型 (WorkflowNodeModel)

节点是工作流的基本组成单元，代表一个具体的任务或操作。

**主要类型**：
- **控制流节点**：开始、结束、条件分支、循环等
- **AI 节点**：大语言模型、嵌入生成、文本分类、摘要生成等
- **工具节点**：文件操作、网络请求等
- **数据处理节点**：数据过滤、数据聚合等
- **输入输出节点**：输入、输出

**使用示例**：
```python
from living_tree_ai.workflow import WorkflowNodeModel, NodeType

# 创建 LLM 节点
llm_node = WorkflowNodeModel(
    node_id="llm",
    node_type=NodeType.LLM,
    name="大语言模型",
    position={"x": 300, "y": 200},
    config={
        "model": "gpt-4",
        "temperature": 0.7
    }
)
```

### 4.3 执行引擎 (WorkflowExecutor)

执行引擎负责执行工作流，处理节点的执行顺序和状态管理。

**主要功能**：
- 执行工作流
- 管理执行状态
- 处理节点执行结果
- 支持异步执行

**使用示例**：
```python
from living_tree_ai.workflow import WorkflowExecutor

# 创建执行器
executor = WorkflowExecutor()

# 执行回调
def execution_callback(node_id, status, result):
    print(f"节点 {node_id} 状态: {status}")
    if result:
        print(f"  结果: {result}")

# 执行工作流
import asyncio
async def run():
    result = await executor.execute(
        workflow,
        callback=execution_callback
    )
    print(f"执行结果: {'成功' if result.success else '失败'}")

asyncio.run(run())
```

### 4.4 模板管理器 (TemplateManager)

模板管理器负责工作流模板的管理，包括保存、加载、导入和导出。

**主要功能**：
- 保存工作流为模板
- 加载模板
- 导入模板
- 导出模板
- 管理模板列表

**使用示例**：
```python
from living_tree_ai.workflow import WorkflowTemplate, TemplateManager

# 创建模板
template = WorkflowTemplate(
    template_id="test_template",
    name="测试模板",
    description="用于测试的模板",
    workflow=workflow,
    tags=["test", "demo"]
)

# 保存模板
manager = TemplateManager()
template_path = manager.save_template(template)

# 导出模板
export_path = "test_template_export.json"
success = manager.export_template("test_template", export_path)

# 导入模板
imported_template = manager.import_template(export_path)
```

### 4.5 节点注册表 (NodeRegistry)

节点注册表管理所有可用的节点类型，包括内置节点和自定义节点。

**主要功能**：
- 注册节点类型
- 获取节点类型
- 按类别获取节点

**使用示例**：
```python
from living_tree_ai.workflow import register_builtin_nodes, get_registry

# 注册内置节点
register_builtin_nodes()

# 获取注册表
registry = get_registry()

# 列出所有节点
nodes = registry.get_all()
print(f"注册的节点数量: {len(nodes)}")

# 按类别列出节点
categories = registry.get_categories()
for category in categories:
    category_nodes = registry.get_by_category(category)
    print(f"  {category}: {[node.name for node in category_nodes]}")
```

## 5. 工作流编辑器 UI

工作流编辑器提供了可视化的界面，用于创建和管理工作流。

**主要功能**：
- 节点拖拽和放置
- 节点连接
- 节点属性编辑
- 工作流执行和监控
- 模板管理

**使用方法**：
1. 从节点调色板拖拽节点到画布
2. 点击源节点的输出端口，拖拽到目标节点的输入端口创建连接
3. 选中节点，在属性面板中编辑节点属性
4. 点击运行按钮执行工作流
5. 在执行面板中查看执行状态和日志
6. 通过文件菜单管理模板

## 6. 内置节点类型

### 6.1 控制流节点
- **开始**：工作流的起始点
- **结束**：工作流的结束点
- **条件分支**：根据条件选择执行分支
- **循环**：循环执行节点内容
- **并行执行**：并行执行多个子任务
- **延迟**：延迟执行

### 6.2 AI 节点
- **大语言模型**：调用大语言模型进行推理
- **嵌入生成**：生成文本嵌入向量
- **文本分类**：对文本进行分类
- **摘要生成**：生成文本摘要

### 6.3 工具节点
- **工具**：调用工具执行特定功能
- **文件操作**：执行文件读写操作
- **网络请求**：发送 HTTP 请求

### 6.4 数据处理节点
- **数据过滤**：根据条件过滤数据
- **数据聚合**：聚合数据计算统计值
- **数据转换**：转换和格式化数据

### 6.5 输入输出节点
- **输入**：定义工作流输入参数
- **输出**：定义工作流输出结果

## 7. 模板管理

模板管理功能允许用户保存、加载、导入和导出工作流模板，方便复用和分享工作流。

**使用方法**：
1. **保存为模板**：在文件菜单中选择"保存为模板"，输入模板名称和描述
2. **导入模板**：在文件菜单中选择"导入模板"，选择模板文件
3. **导出模板**：在文件菜单中选择"导出模板"，选择要导出的模板和保存位置
4. **管理模板**：在文件菜单中选择"管理模板"，查看、加载和删除模板

## 8. 执行可视化

执行可视化功能实时显示工作流执行进度和状态，帮助用户了解工作流的执行情况。

**主要功能**：
- 实时显示节点执行状态
- 显示执行进度条
- 显示执行日志
- 显示执行结果

## 9. 画布辅助功能

画布辅助功能帮助用户更方便地创建和管理工作流。

**主要功能**：
- **网格显示**：显示网格，方便对齐节点
- **对齐功能**：启用节点对齐，使节点排列更整齐
- **缩放功能**：放大和缩小画布，查看工作流的不同细节
- **重置缩放**：将画布恢复到默认缩放级别

## 10. 最佳实践

1. **工作流设计**：
   - 保持工作流简洁明了
   - 使用适当的节点类型
   - 合理规划节点连接

2. **性能优化**：
   - 避免过多的节点和连接
   - 使用并行执行节点提高效率
   - 合理设置节点配置

3. **错误处理**：
   - 添加错误处理节点
   - 监控执行状态
   - 查看执行日志

4. **模板管理**：
   - 保存常用工作流为模板
   - 定期更新模板
   - 分享有用的模板

## 11. 常见问题

### 11.1 工作流执行失败
- **原因**：节点配置错误、依赖缺失、网络问题等
- **解决方法**：检查节点配置、安装依赖、检查网络连接

### 11.2 模板导入失败
- **原因**：模板文件损坏、版本不兼容
- **解决方法**：使用正确的模板文件、确保版本兼容

### 11.3 节点拖拽失败
- **原因**：画布缩放比例过大、节点类型不支持
- **解决方法**：调整画布缩放比例、使用支持的节点类型

## 12. 未来规划

- **更多节点类型**：添加更多内置节点类型
- **自定义节点**：支持用户自定义节点
- **工作流版本控制**：支持工作流的版本管理
- **工作流共享**：支持工作流的在线共享和协作
- **高级执行策略**：支持更复杂的执行策略和调度

## 13. 结论

工作流模块为 LivingTreeAI 提供了强大的可视化工作流构建和执行能力，使用户能够更方便地创建和管理 AI 工作流。通过丰富的节点类型、实时执行可视化和模板管理功能，用户可以快速构建复杂的 AI 工作流，提高 AI 应用的开发效率。
