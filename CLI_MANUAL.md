# LivingTree CLI 命令手册

> v2.4 | 2026-05-15 | 18 LLM providers | 43 MCP tools | 32 LocalToolBus tools

---

## 快速开始

```bash
# 安装
pip install -e .

# 查看所有命令
python -m livingtree --help
```

---

## 命令索引

| 命令 | 用途 | 依赖 |
|------|------|------|
| `livingtree web` | 启动 Web 服务 | 无 |
| `livingtree debug chat` | **调试管线 (6阶段)** | API keys |
| `livingtree quick` | 快速单次对话 | API keys |
| `livingtree client` | 交互式 REPL | API keys |
| `livingtree secrets` | 密钥管理 | 无 |
| `livingtree vitals` | 7器官健康检查 | 无 |
| `livingtree test` | 集成测试 | API keys |
| `livingtree cli` | CLI工具发现/注册 | 无 |

---

## 1. `livingtree web` — Web 服务

```bash
python -m livingtree web
# 启动于 http://localhost:8100
# 路由: /tree/living (画布), /tree/admin (控制台)
```

---

## 2. `livingtree debug chat` — 调试管线 (核心)

**用途**: 端到端调试，展示全部6个阶段，含逐行追踪和工具执行。

### 语法

```bash
python -m livingtree debug chat "<消息>" [选项]
```

### 选项

| 选项 | 说明 |
|------|------|
| `--trace` | 启用 DebugPro LineTracer 逐行追踪 |
| `--verbose` / `-v` | 显示完整响应和详细耗时 |

### 范例

```bash
# 基本用法 — 6阶段管线调试
python -m livingtree debug chat "杭州有哪些好玩的，2天2000元够不够"

# 输出:
# [1/6] Input Normalization     → kind=static_text
# [2/6] ContextMoE Memory       → 5ms
# [3/6] Provider Election       → elected=stepfun (from 18 alive)
# [4/6] LLM Chat                → deepseek: 1026 chars
# [5/6] Tool Call Detection     → tools executed via LocalToolBus
# [6/6] Error Summary           → No errors intercepted
```

```bash
# 详细模式 — 显示完整回复和所有耗时
python -m livingtree debug chat "什么是EIA环评" -v
```

```bash
# 逐行追踪 — 启用 LineTracer 记录每行执行
python -m livingtree debug chat "帮我搜索最新的AI论文" --trace
```

### 管线6阶段详解

```
用户输入
  │
  ▼
[1/6] living_input_bus     # 输入标准化 (CLI/Web/API → 统一格式)
  │
  ▼
[2/6] context_moe          # 情境记忆检索 (热/温/冷 三通道)
  │
  ▼
[3/6] smart_route          # 提供商选举 (18个并行ping → 最优选择)
  │
  ▼
[4/6] llm.chat()           # LLM对话 (包含prompt注入 + 工具声明 + 会话压缩)
  │     ├─ 失败 → 自动回退到下一个provider (最多5个)
  │     └─ 成功 → 返回response
  │
  ▼
[5/6] Tool Call Detection  # 工具调用检测
  │     ├─ 检测 <tool_call name="xxx">...</tool_call>
  │     ├─ 解析参数 (XML/JSON/OpenAI三种格式)
  │     └─ 通过 LocalToolBus 直接执行 (<1ms, 无子进程)
  │
  ▼
[6/6] ErrorInterceptor     # 错误汇总 (全局异常捕获统计)
```

---

## 3. `livingtree quick` — 快速对话

```bash
python -m livingtree quick "今天是星期几"
# 单轮对话，无交互，输出即退出

python -m livingtree q "用Python写一个快速排序"
# 简写命令
```

---

## 4. `livingtree client` — 交互式 REPL

```bash
python -m livingtree client
# 进入交互模式:
#   > 杭州有哪些好玩的
#   > /stats     — 查看会话统计
#   > /exit      — 退出
```

---

## 5. `livingtree secrets` — 密钥管理

```bash
# 设置API密钥
livingtree secrets set deepseek_api_key sk-xxxxxxxx

# 列出所有已配置的密钥 (不显示值)
livingtree secrets list

# 例子: 配置多个提供商
livingtree secrets set deepseek_api_key sk-xxx
livingtree secrets set zhipu_api_key xxx.yyy.zzz
```

---

## 6. `livingtree vitals` — 健康检查

```bash
python -m livingtree vitals
# 检查7个器官: config, providers, memory, knowledge, execution, network, safety
```

---

## 7. `livingtree test` — 集成测试

```bash
python -m livingtree test
# 运行5个测试: 基础对话, 任务规划, 知识库, 细胞注册, 状态检查
```

---

## 8. `livingtree cli` — CLI工具管理

```bash
# 扫描系统中的CLI工具
python -m livingtree cli scan

# 搜索工具
python -m livingtree cli search git

# 注册工具到 CapabilityBus
python -m livingtree cli register mytool

# 执行已注册的工具
python -m livingtree cli exec mytool -- --help
```

---

## 端到端验证示例

以下命令已验证可以通过（2026-05-15）：

```bash
# 1. 简单问答
python -m livingtree debug chat "今天是星期几"
# → deepseek: "今天是2024年7月12日，星期五。" (18 chars, 358 tokens, 2311ms)

# 2. 复杂旅游规划
python -m livingtree debug chat "杭州有哪些好玩的，2天2000元够不够"
# → deepseek: 1026 chars 详细攻略 (1305 tokens, 12001ms)
#   包含 Day1/Day2行程 + 费用表格 + 省钱建议

# 3. 详细模式
python -m livingtree debug chat "什么是EIA环评" -v
# → 完整回复 + provider列表 + 每阶段耗时

# 4. 工具调用 (需要查询实时数据时LLM会自动使用)
python -m livingtree debug chat "帮我查询GB3095-2012中PM2.5的标准限值"
# → 可能触发 lookup_standard 工具调用
```

---

## 故障排除

| 症状 | 原因 | 解决 |
|------|------|------|
| `0 providers alive` | API密钥未配置 | `livingtree secrets set deepseek_api_key sk-xxx` |
| `All providers failed` | 密钥过期/网络问题 | 检查 `livingtree secrets list` |
| `ModuleNotFoundError` | 未安装依赖 | `pip install -e ".[all]"` |
| `ConnectionPool timeout` | 网络不通 | 检查防火墙/代理 |
| `MCPHostClient EOF` | npx未安装 | MCP外部工具需要 Node.js |

---

## 环境要求

- Python >= 3.13
- 至少1个有效的 LLM API Key (推荐 deepseek)
- 可选: Node.js (MCP 外部工具), Numba (JIT加速), CUDA (GPU推理)
