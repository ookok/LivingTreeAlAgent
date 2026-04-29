# 📊 Opik 集成使用指南

## ✅ 已完成的工作

### Phase 1: Python SDK 集成 ✅
1. **安装 Opik SDK** (版本: 2.0.17)
2. **创建追踪模块** (`client/src/business/opik_tracer.py`)
   - `OpikConfig`: 配置类
   - `configure_opik()`: 初始化 Opik
   - `trace_llm_call`, `trace_tool_call`, `trace_agent_call`: 装饰器
   - `start_trace()`, `log_trace()`: 手动追踪接口
3. **集成到 GlobalModelRouter** (`client/src/business/global_model_router.py`)
   - `call_model()` 方法添加追踪逻辑
   - `call_model_sync()` 函数添加追踪逻辑

### Phase 2: 生产监控 ✅
1. **创建监控器** (`client/src/business/opik_monitor.py`)
   - `OpikMonitor`: 监控器类
   - `MonitorConfig`: 配置类
   - `AlertRule`: 告警规则类
   - `@monitor_tool`: 装饰器
2. **集成到所有 Tool 执行** (`client/src/business/tools/base_tool.py`)
   - `agent_call()` 方法添加监控逻辑
3. **添加告警规则**
   - 支持多种告警条件（threshold_exceeded, anomaly_detected 等）
   - 支持多种动作（log, notify, fallback, disable_tool）

### Phase 3: Dashboard 集成 ✅
1. **创建 UI 面板** (`client/src/presentation/panels/opik_panel.py`)
   - `OpikDashboardPanel`: 主面板类
   - 5个标签页：Dashboard、Traces、Metrics、Alerts、配置
2. **嵌入 Opik Dashboard** (QWebEngineView)
   - 使用 QWebEngineView 嵌入 Opik Web UI
   - 支持刷新、外部打开
3. **显示实时统计**
   - Traces 查看器
   - Metrics 监控
   - Alerts 管理
4. **注册路由到导航栏** (`client/src/presentation/router/routes.py`)
   - 添加 Route("opik", "Opik 监控", "📊", _create_opik_panel, category="tool")

---

## 🚀 使用步骤

### 步骤1: 安装依赖

```bash
# 安装 Opik SDK
pip install opik

# 安装 PyQt6-WebEngine（用于 Dashboard 嵌入）
pip install PyQt6-WebEngine
```

### 步骤2: 启动 Opik 服务器

```bash
# 启动本地服务器
opik server start

# 看到类似输出：
# ✅ Opik server started successfully!
# 🌐 Dashboard: http://localhost:5173
# 📊 API endpoint: http://localhost:5173/api
```

### 步骤3: 访问 Dashboard

在浏览器打开: http://localhost:5173

首次访问会要求配置：
- 选择 "Use local instance"
- 一路 Next 即可

### 步骤4: 初始化 LivingTreeAI 的 Opik 集成

在 Python 代码中：

```python
from client.src.business.opik_tracer import init_opik_for_livingtree, OpikConfig

# 使用默认配置（本地模式）
success = init_opik_for_livingtree()
if success:
    print("✅ Opik 初始化成功")

# 或者自定义配置
config = OpikConfig(
    enabled=True,
    use_local=True,          # 使用本地部署
    project_name="livingtree-ai",
    trace_llm_calls=True,
    trace_tool_calls=True,
    trace_agent_calls=True,
    monitor_token_usage=True,
    monitor_cost=True,
    monitor_latency=True,
)
init_opik_for_livingtree(config)
```

### 步骤5: 在 LivingTreeAI 中使用

1. 启动 LivingTreeAI 客户端
2. 点击左侧导航栏的 **"📊 Opik 监控"**
3. 在配置标签页中应用配置
4. Dashboard 标签页会自动加载 Opik Web UI

现在，所有通过 `GlobalModelRouter` 的 LLM 调用都会自动被追踪。

---

## 📊 Phase 3: Dashboard 集成说明

### 功能特性

Opik Dashboard 面板提供以下标签页：

1. **📊 Dashboard**: 嵌入 Opik Web UI（需要安装 PyQt6-WebEngine）
2. **🔍 Traces**: 查看追踪记录
3. **📈 Metrics**: 监控 LLM 调用指标
4. **🚨 Alerts**: 管理告警规则
5. **⚙️ 配置**: 配置 Opik 连接和追踪选项

### 标签页详细说明

#### 📊 Dashboard 标签页
- 嵌入 Opik 官方 Web UI
- 可以直接在面板中查看所有追踪数据
- 支持刷新、外部打开

**注意**: 需要安装 `PyQt6-WebEngine`：
```bash
pip install PyQt6-WebEngine
```

如果未安装，会显示提示和手动打开链接的按钮。

#### 🔍 Traces 标签页
- 显示所有 LLM/Tool/Agent 调用的追踪记录
- 表格包含：ID、名称、类型、开始时间、延迟、状态
- 点击记录可以查看详细输入/输出

**提示**: 完整数据需要通过 Opik Python SDK 获取，或直接在 Dashboard 网页查看。

#### 📈 Metrics 标签页
- 显示 LLM 调用的关键指标
- 指标包括：调用次数、平均延迟、Token 使用量、错误率
- 如果安装了 `opik_monitor.py`，还会显示监控器统计

#### 🚨 Alerts 标签页
- 管理告警规则
- 表格显示：规则名称、指标、条件、阈值、状态
- 可以添加/编辑/删除告警规则
- 告警日志显示触发的告警历史

#### ⚙️ 配置标签页
- **连接配置**:
  - Dashboard URL: Opik Dashboard 地址
  - 使用本地部署: 勾选以连接本地 Opik 服务器
  - API Key: 云端模式需要
  - Workspace: 云端模式需要
  - 项目名: Opik 项目名称

- **追踪选项**:
  - 追踪 LLM 调用: 记录所有 LLM 调用
  - 追踪 Tool 调用: 记录所有 Tool 执行
  - 追踪 Agent 调用: 记录所有 Agent 运行

- **监控选项**:
  - 监控 Token 使用: 统计 Token 消耗
  - 监控成本: 计算 API 成本
  - 监控延迟: 记录响应时间

---

## 🔧 高级用法

### 1. 手动追踪

如果需要在特定位置添加追踪：

```python
from client.src.business.opik_tracer import start_trace, log_trace

# 开始追踪
trace = start_trace(
    name="my_custom_trace",
    trace_type="tool",
    metadata={"user": "admin"}
)

# 执行一些操作
result = do_something()

# 记录结果
log_trace(
    trace,
    input_data={"input": "some input"},
    output_data={"result": result},
    metadata={"success": True}
)
```

### 2. 使用装饰器

```python
from client.src.business.opik_tracer import trace_llm_call, trace_tool_call

@trace_llm_call(name="my_llm_call")
def my_llm_function(prompt: str) -> str:
    # 这个函数会自动被追踪
    return call_model_sync(ModelCapability.CHAT, prompt)

@trace_tool_call(name="my_tool")
def my_tool_function(arg: str) -> str:
    # 这个工具调用会自动被追踪
    return f"Tool result: {arg}"
```

### 3. 追踪 Agent 调用

```python
from client.src.business.opik_tracer import trace_agent_call

@trace_agent_call(name="my_agent")
def run_my_agent(query: str) -> str:
    # 这个 Agent 调用会自动被追踪
    # ...
    return result
```

### 4. 使用监控装饰器

```python
from client.src.business.opik_monitor import monitor_tool

@monitor_tool(name="my_tool")
def my_tool_function(arg: str) -> str:
    # 这个工具调用会被监控
    return f"Tool result: {arg}"
```

---

## 📊 Dashboard 功能

访问 http://localhost:5173 后，你可以：

### 1. Traces 页面
- 查看所有追踪记录
- 筛选 by 类型 (LLM/Tool/Agent)
- 查看每个调用的详细信息（输入、输出、延迟、Token 使用）

### 2. Analytics 页面
- Token 使用统计
- 成本分析
- 延迟分析
- 成功率统计

### 3. Projects 页面
- 管理多个项目
- 每个项目有独立的追踪数据

### 4. Datasets 页面
- 创建测试数据集
- 运行批量评估

---

## 🚨 常见问题

### Q1: Opik 服务器启动失败

**解决方案**:
```bash
# 检查端口是否被占用
netstat -ano | findstr :5173

# 如果端口被占用，杀掉进程
taskkill /PID <PID> /F

# 重新启动
opik server start
```

### Q2: 追踪数据没有出现在 Dashboard

**可能原因**:
1. Opik 未正确初始化
2. LLM 调用失败
3. 网络问题

**解决方案**:
```python
# 检查 Opik 是否启用
from client.src.business.opik_tracer import is_opik_enabled
print(is_opik_enabled())  # 应该返回 True

# 检查日志
# 在日志中搜索 "Opik"，看是否有错误信息
```

### Q3: 我想使用云端 Opik

**解决方案**:
```python
from client.src.business.opik_tracer import OpikConfig, init_opik_for_livingtree

config = OpikConfig(
    enabled=True,
    use_local=False,         # 使用云端
    api_key="your-api-key",  # 从 opik.com 获取
    workspace="your-workspace",
)
init_opik_for_livingtree(config)
```

### Q4: QWebEngineView 不可用

**解决方案**:
```bash
# 安装 PyQt6-WebEngine
pip install PyQt6-WebEngine
```

如果无法安装，面板会显示提示和手动打开链接的按钮。

---

## 📚 参考资源

- **Opik 官方文档**: https://www.comet.com/docs/opik/
- **Opik GitHub**: https://github.com/comet-ml/opik
- **LivingTreeAI 文档**:
  - `client/src/business/opik_tracer.py`
  - `client/src/business/opik_monitor.py`
  - `client/src/presentation/panels/opik_panel.py`

---

## 🧪 测试

### 测试 Phase 1

```bash
cd d:/mhzyapp/LivingTreeAlAgent
python test_opik_integration.py
```

### 测试 Phase 2

```bash
cd d:/mhzyapp/LivingTreeAlAgent
python test_opik_monitor.py
```

### 测试 Phase 3

```bash
cd d:/mhzyapp/LivingTreeAlAgent
python test_opik_dashboard.py
```

---

**最后更新**: 2026-04-29
**作者**: LivingTreeAI Development Team
