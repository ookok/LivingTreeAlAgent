# browser-use 集成使用文档

本文档介绍如何在 LivingTreeAlAgent 中使用 browser-use 集成功能，实现浏览器自动化任务。

## 1. 安装

### 1.1 安装 browser-use

```bash
pip install browser-use
```

### 1.2 配置环境变量

如果需要使用特定的 LLM 提供商，需要设置相应的环境变量：

- **OpenAI**：`OPENAI_API_KEY`
- **Google**：`GOOGLE_API_KEY`
- **Anthropic**：`ANTHROPIC_API_KEY`

## 2. 基本用法

### 2.1 直接使用浏览器适配器

```python
from core.living_tree_ai.browser_gateway.browser_use_adapter import create_browser_use_adapter

# 创建适配器
adapter = create_browser_use_adapter()

# 初始化
await adapter.initialize()

# 执行浏览器任务
result = await adapter.navigate("https://example.com")
print(result)

# 提取页面内容
result = await adapter.extract_content("https://example.com")
print(result)

# 搜索内容
result = await adapter.search("browser automation")
print(result)

# 关闭浏览器
await adapter.close()
```

### 2.2 通过 RPC 调用

在浏览器中，可以通过以下方式调用 browser-use 功能：

```javascript
// 导航到网站
const result = await window.hyperos.browserUse.navigate("https://example.com");
console.log(result);

// 提取内容
const content = await window.hyperos.browserUse.extractContent("https://example.com");
console.log(content);

// 搜索
const search = await window.hyperos.browserUse.search("browser automation");
console.log(search);
```

## 3. 工作流节点使用

### 3.1 在工作流编辑器中添加节点

1. 打开工作流编辑器
2. 在左侧节点调色板中找到 "浏览器" 类别
3. 拖拽 "浏览器自动化" 节点到画布

### 3.2 配置节点

1. 选中节点，在右侧属性面板中配置：

#### 3.2.1 基本信息
- **名称**：节点名称
- **描述**：节点描述

#### 3.2.2 浏览器自动化配置
- **任务类型**：选择要执行的浏览器任务类型
  - `execute`：执行自定义任务
  - `navigate`：导航到指定 URL
  - `extract_content`：提取页面内容
  - `fill_form`：填写表单
  - `search`：搜索内容
  - `screenshot`：截图页面

- **结果变量名**：执行结果存储的变量名

- **使用云浏览器**：是否使用云浏览器

#### 3.2.3 任务参数

根据选择的任务类型，配置相应的参数：

**execute**
- **任务描述**：详细的任务描述

**navigate**
- **目标 URL**：要导航的 URL

**extract_content**
- **目标 URL**：要提取内容的 URL
- **CSS 选择器**：要提取的元素选择器（可选）

**fill_form**
- **目标 URL**：表单所在的 URL
- **表单数据**：表单数据（JSON 格式）

**search**
- **搜索查询**：搜索关键词
- **搜索引擎**：使用的搜索引擎（默认 google）

**screenshot**
- **目标 URL**：要截图的 URL
- **保存路径**：截图保存路径

### 3.3 示例工作流

#### 3.3.1 网页数据采集工作流

1. **开始节点** → **浏览器自动化**（导航到网站） → **浏览器自动化**（提取内容） → **结束节点**

2. **配置**：
   - 第一个浏览器节点：任务类型 = navigate，目标 URL = "https://example.com"
   - 第二个浏览器节点：任务类型 = extract_content，目标 URL = "https://example.com"

#### 3.3.2 表单自动填写工作流

1. **开始节点** → **浏览器自动化**（填写表单） → **结束节点**

2. **配置**：
   - 浏览器节点：任务类型 = fill_form，目标 URL = "https://example.com/form"，表单数据 = `{"name": "John", "email": "john@example.com"}`

#### 3.3.3 搜索信息工作流

1. **开始节点** → **浏览器自动化**（搜索） → **结束节点**

2. **配置**：
   - 浏览器节点：任务类型 = search，搜索查询 = "browser automation tutorial"

## 4. 安全设置

### 4.1 域名白名单

可以通过安全管理器设置域名白名单，限制浏览器可以访问的域名：

```python
from core.living_tree_ai.browser_gateway.security_manager import get_security_manager

security_manager = get_security_manager()

# 添加白名单域名
security_manager.add_whitelist(["example.com", "google.com"])

# 添加黑名单域名
security_manager.add_blacklist(["malicious.com"])

# 检查 URL 是否允许访问
is_allowed = security_manager.is_allowed("https://example.com")
print(f"URL 是否允许访问: {is_allowed}")
```

### 4.2 内置安全保护

系统内置了以下安全保护：
- 禁止访问本地地址（localhost, 127.0.0.1, 0.0.0.0）
- 禁止访问文件协议（file://）

## 5. 性能优化

### 5.1 浏览器会话池

系统使用浏览器会话池管理浏览器实例，减少启动开销：

- 默认最大会话数：5
- 默认会话超时：5分钟
- 自动清理过期会话

### 5.2 会话池配置

可以通过以下方式配置会话池：

```python
from core.living_tree_ai.browser_gateway.browser_pool import create_browser_pool

# 创建自定义会话池
pool = create_browser_pool(
    max_sessions=10,  # 最大会话数
    session_timeout=600,  # 会话超时（秒）
    use_cloud=False  # 是否使用云浏览器
)
```

## 6. 高级用法

### 6.1 执行复杂任务

```python
# 执行复杂的浏览器任务
task = "导航到 https://github.com 并搜索 'browser-use' 仓库，返回前 3 个结果"
result = await adapter.execute_task(task)
print(result)
```

### 6.2 截图功能

```python
# 截取网页截图
result = await adapter.screenshot("https://example.com", "example_screenshot.png")
print(result)
```

### 6.3 表单填写

```python
# 填写表单
form_data = {
    "username": "test",
    "password": "password123"
}
result = await adapter.fill_form("https://example.com/login", form_data)
print(result)
```

## 7. 故障排除

### 7.1 常见问题

1. **浏览器启动失败**：
   - 检查网络连接
   - 确保 browser-use 已正确安装

2. **访问被拒绝**：
   - 检查域名是否在白名单中
   - 确保 URL 格式正确

3. **执行超时**：
   - 检查网络速度
   - 简化任务描述

4. **会话池满**：
   - 增加最大会话数
   - 减少任务执行时间

### 7.2 日志查看

可以通过以下方式查看 browser-use 相关日志：

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("browser-use")
```

## 8. 示例代码

### 8.1 基本示例

```python
"""browser-use 基本示例"""

import asyncio
from core.living_tree_ai.browser_gateway.browser_use_adapter import create_browser_use_adapter

async def main():
    # 创建适配器
    adapter = create_browser_use_adapter()
    
    # 初始化
    await adapter.initialize()
    
    try:
        # 导航到网站
        print("导航到 example.com...")
        result = await adapter.navigate("https://example.com")
        print(f"导航结果: {result}")
        
        # 提取内容
        print("\n提取页面内容...")
        result = await adapter.extract_content("https://example.com")
        print(f"内容提取结果: {result}")
        
        # 搜索
        print("\n搜索 browser automation...")
        result = await adapter.search("browser automation")
        print(f"搜索结果: {result}")
        
    finally:
        # 关闭浏览器
        await adapter.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### 8.2 工作流示例

```python
"""browser-use 工作流示例"""

from core.workflow import Workflow, WorkflowNodeModel, NodeType, create_browser_use_node

# 创建工作流
workflow = Workflow(
    workflow_id="browser_demo",
    name="浏览器自动化演示",
    description="演示 browser-use 浏览器自动化功能"
)

# 添加开始节点
start_node = WorkflowNodeModel(
    node_id="start",
    node_type=NodeType.START,
    name="开始",
    position={"x": 100, "y": 200}
)
workflow.add_node(start_node)

# 添加浏览器自动化节点（导航）
navigate_node = create_browser_use_node(
    name="导航到示例网站",
    task_type="navigate",
    task_params={"url": "https://example.com"},
    result_variable="navigate_result"
)
navigate_node.node_id = "navigate"
navigate_node.position = {"x": 300, "y": 150}
workflow.add_node(navigate_node)

# 添加浏览器自动化节点（提取内容）
extract_node = create_browser_use_node(
    name="提取页面内容",
    task_type="extract_content",
    task_params={"url": "https://example.com"},
    result_variable="content_result"
)
extract_node.node_id = "extract"
extract_node.position = {"x": 300, "y": 250}
workflow.add_node(extract_node)

# 添加结束节点
end_node = WorkflowNodeModel(
    node_id="end",
    node_type=NodeType.END,
    name="结束",
    position={"x": 500, "y": 200}
)
workflow.add_node(end_node)

# 连接节点
from core.workflow import NodeConnection

workflow.add_connection(NodeConnection(
    connection_id="conn1",
    source_node_id="start",
    source_port="output",
    target_node_id="navigate",
    target_port="input"
))

workflow.add_connection(NodeConnection(
    connection_id="conn2",
    source_node_id="navigate",
    source_port="output",
    target_node_id="extract",
    target_port="input"
))

workflow.add_connection(NodeConnection(
    connection_id="conn3",
    source_node_id="extract",
    source_port="output",
    target_node_id="end",
    target_port="input"
))

print("工作流创建成功！")
print(f"节点数量: {len(workflow.nodes)}")
print(f"连接数量: {len(workflow.connections)}")
```

## 9. 总结

browser-use 集成为 LivingTreeAlAgent 提供了强大的浏览器自动化能力，通过以下特点提升用户体验：

- **性能优化**：浏览器会话池减少启动开销
- **安全增强**：域名白名单和内置安全保护
- **易用性**：直观的工作流节点配置界面
- **灵活性**：支持多种浏览器自动化任务
- **可扩展性**：易于集成到现有工作流中

通过本文档的指导，您可以快速上手 browser-use 集成功能，实现各种浏览器自动化任务，为 AI 代理提供更强大的网页交互能力。