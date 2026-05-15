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
| `livingtree start / stop / restart / status / logs / update` | 服务管理 (CowAgent 风格) | 无 |
| `livingtree secrets` | 密钥管理 | 无 |
| `livingtree debug` | **调试循环** (文件修复 / 管线对话) | 部分需 API keys |
| `livingtree quick` | 快速单次对话 | API keys |
| `livingtree client` | 交互式 REPL | API keys |
| `livingtree test` | 集成测试 | API keys |
| `livingtree check` | 环境检查 | 无 |
| `livingtree improve` | **自主改进** (缺陷扫描 / 创新提议 / 自动修复) | API keys (LLM 模式) |
| `livingtree models` | 模型仓库管理 (同步 / 列表 / 自动检测) | API keys |
| `livingtree cli` | CLI 反省工具 (发现 / 注册 / 执行系统 CLI) | 无 |
| `livingtree cli-anything` | 任意代码转 CLI 工具 | 无 |
| `livingtree recording` | 任务录制与回放 | 无 |
| `livingtree canary` | 金丝雀回归测试 | API keys |
| `livingtree skill` | 技能市场管理 (安装 / 搜索 / 创建) | 无 |
| `livingtree channel` | 消息通道切换 (微信 / 飞书 / 钉钉) | 无 |
| `livingtree relay` | 启动 Relay 服务器 | 无 |
| `livingtree config` | 查看 / 设置配置 | 无 |
| `livingtree trace` | 触发链可视化 + 器官数据流 + 系统报告 | 无 |
| `livingtree deps` | 生成模块依赖拓扑图 (DEPENDENCIES.mmd) | 无 |

---

## 1. `livingtree web` — Web 服务

```bash
python -m livingtree web
# 启动于 http://localhost:8100
# 路由: /tree/living (画布), /tree/admin (控制台)
```

---

## 2. 服务管理 — start / stop / restart / status / logs / update

```bash
livingtree start              # 后台启动 (守护进程)
livingtree stop               # 停止后台服务
livingtree restart            # 重启服务
livingtree status             # 查看服务运行状态
livingtree logs               # 查看最后 20 行日志
livingtree logs 50            # 查看最后 50 行日志
livingtree update             # Git pull + 重启
```

---

## 3. `livingtree debug` — 调试循环

**两种模式**: 文件修复 + 管线对话。

### 3a. 文件调试模式

```bash
python -m livingtree debug <文件> [选项]
```

| 选项 | 说明 |
|------|------|
| `--level L1\|L2\|L3` | 调试级别 (L1=基础, L2=半自动, L3=全自动) |
| `--trace` | 启用 DebugPro LineTracer 逐行追踪 |
| `--max-attempts N` | 最大尝试次数 (默认 5) |
| `--args ...` | 传递给目标脚本的参数 |

```bash
# 示例: 半自动修复 main.py
python -m livingtree debug main.py --level L2

# 示例: 全自动修复 + 逐行追踪
python -m livingtree debug main.py --level L3 --trace --max-attempts 10
```

### 3b. 管线对话模式 (核心)

```bash
python -m livingtree debug chat "<消息>" [选项]
```

| 选项 | 说明 |
|------|------|
| `--trace` | 启用 DebugPro LineTracer 逐行追踪 |
| `--verbose` / `-v` | 显示完整响应和详细耗时 |

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

## 4. `livingtree quick` — 快速对话

```bash
python -m livingtree quick "今天是星期几"
# 单轮对话，无交互，输出即退出

python -m livingtree q "用Python写一个快速排序"
# 简写命令
```

---

## 5. `livingtree client` — 交互式 REPL

```bash
python -m livingtree client
# 进入交互模式:
#   > 杭州有哪些好玩的
#   > /stats     — 查看会话统计
#   > /exit      — 退出
```

---

## 6. `livingtree secrets` — 密钥管理

```bash
# 设置API密钥
livingtree secrets set deepseek_api_key sk-xxxxxxxx

# 列出所有已配置的密钥 (显示脱敏值)
livingtree secrets list

# 查看某个密钥的值
livingtree secrets get deepseek_api_key

# 删除某个密钥
livingtree secrets delete deepseek_api_key

# 配置多个提供商
livingtree secrets set deepseek_api_key sk-xxx
livingtree secrets set zhipu_api_key xxx.yyy.zzz
```

---

## 7. `livingtree test` — 集成测试

```bash
python -m livingtree test
# 运行集成测试
```

---

## 8. `livingtree check` — 环境检查

```bash
python -m livingtree check
# 别名: livingtree env
# 检查 Python 版本、依赖、网络等环境条件
```

---

## 9. `livingtree improve` — 自主改进

```bash
livingtree improve --scan          # 扫描代码库中的缺陷
livingtree improve --scan --llm    # 使用 LLM 辅助扫描缺陷
livingtree improve --propose       # 扫描缺陷 + LLM 提出改进方案
livingtree improve --propose --llm # 使用 LLM 增强方案提议
livingtree improve --auto          # 全自动循环: 扫描→提议→实施→验证
livingtree improve --auto --apply  # 自动实施改进 (直接修改代码)
livingtree improve --report        # 查看改进统计 (周期/创新/缺陷数)
```

### 工作流

```
--scan  ──→  发现缺陷 (按类别/严重程度分类)
   │
   ▼
--propose ──→  基于缺陷向 LLM 提出创新方案
   │
   ▼
--auto ──→  全自动: 扫描 → 提议 → 实施方案 → 验证结果
   │
   ▼
--report ──→  改进周期统计、创新数量、缺陷总数
```

---

## 10. `livingtree models` — 模型仓库管理

```bash
livingtree models sync              # 从所有18个提供商同步模型列表
livingtree models sync deepseek     # 仅同步指定提供商
livingtree models list              # 列出所有已缓存的模型
livingtree models list deepseek     # 列出某个提供商的模型
livingtree models show deepseek     # 显示提供商详细模型信息 + 定价
livingtree models auto              # 自动检测每个提供商的最佳模型 (用于 CI)
```

---

## 11. `livingtree cli` — CLI 反省工具

发现并注册系统中的 CLI 工具到 CapabilityBus。

```bash
livingtree cli scan                # 扫描 PATH 中的 CLI 工具
livingtree cli search git          # 搜索工具
livingtree cli register mytool     # 注册工具到 CapabilityBus
livingtree cli register-all        # 批量注册所有发现工具
livingtree cli list                # 列出可用/已注册工具
livingtree cli list dev            # 按类别筛选
livingtree cli exec mytool -- --help  # 执行已注册的工具
```

---

## 12. `livingtree cli-anything` — 任意代码转 CLI

将 Python 函数或仓库包装为 CLI 工具。

```bash
livingtree cli-anything wrap <file> [func_name] [--install]
# 从 Python 文件包装函数为 CLI 脚本

livingtree cli-anything repo <url> [--install]
# 从 Git 仓库自动发现入口点并生成命令

livingtree cli-anything new <name>
# 创建新的 CLI Manifest 模板

livingtree cli-anything manifest <path>
# 解析并显示 CLI Manifest 定义

livingtree cli-anything publish <manifest> [target]
# 发布 CLI 到指定目标 (pip 等)

livingtree cli-anything stats
# 查看已生成工具和 Manifest 统计
```

---

## 13. `livingtree recording` — 任务录制与回放

```bash
livingtree record start "我的任务"    # 开始录制
livingtree record stop                # 停止录制并保存
livingtree record list                # 列出所有录制
livingtree record replay <id>         # 回放录制 (流式模式)
livingtree record replay <id> 2.0     # 2倍速回放
livingtree record export <id>         # 导出为 JSON
livingtree record export <id> html    # 导出为 HTML
livingtree record render <id>         # 渲染为时间线 (JSON)
livingtree record render <id> graph   # 渲染为关系图
livingtree record delete <id>         # 删除录制
```

---

## 14. `livingtree canary` — 金丝雀回归测试

```bash
livingtree canary              # 运行金丝雀测试并对比基线
livingtree canary baseline     # 保存当前路由决策为基线
```

---

## 15. `livingtree skill` — 技能市场管理

```bash
livingtree skill hub                # 浏览远程技能市场
livingtree skill list               # 列出已安装的技能
livingtree skill install <name>     # 从 Hub/GitHub 安装技能
livingtree skill search <kw>        # 搜索技能
livingtree skill uninstall <name>   # 卸载技能
livingtree skill enable <name>      # 启用技能
livingtree skill disable <name>     # 禁用技能
livingtree skill create <name> [code] [category]  # 创建新技能
livingtree skill discover           # 扫描 SKILL.md 文件
livingtree skill propose <描述>     # 从任务描述提议技能
livingtree skill graph              # 显示技能依赖关系图
livingtree skill report             # 显示技能进度报告
```

---

## 16. `livingtree channel` — 消息通道

```bash
livingtree channel weixin       # 启用微信通道
livingtree channel feishu       # 启用飞书通道
livingtree channel dingtalk     # 启用钉钉通道

# 不带参数查看所有可用通道
livingtree channel
```

---

## 17. `livingtree relay` — Relay 服务器

```bash
python -m livingtree relay
# 启动 Relay 服务器，用于多实例间通信
```

---

## 18. `livingtree config` — 配置管理

```bash
livingtree config                # 显示全部配置 (JSON)
livingtree config <key>          # 查看某个配置项
livingtree config <key> <value>  # 设置配置项
```

---

## 19. `livingtree trace` — 系统诊断

可视化触发链、器官数据流、知识谱系、意识评估和系统生命体征。

```bash
python -m livingtree trace
# 输出包含:
#   - 4-Layer Model Routing 路由策略
#   - 12-Organ Data Flow 器官数据流
#   - Knowledge Lineage 知识谱系统计
#   - Awareness 意识评估 (元认知/自我/社交/情境)
#   - Vitals 生命体征 (CPU/RAM/LED/Leaf)
#   - Adaptive Trigger Flow 自适应触发流
```

---

## 20. `livingtree deps` — 模块依赖拓扑

```bash
python -m livingtree deps
# 生成 DEPENDENCIES.mmd (Mermaid 格式)
# 可用 https://mermaid.live 或 VS Code Mermaid Preview 查看
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

# 4. 标准查询
python -m livingtree debug chat "帮我查询GB3095-2012中PM2.5的标准限值"
# → deepseek: 373 chars, PM2.5限值表格 (一级/二级, 年均/日均)

# 5. 自主改进扫描
python -m livingtree improve --scan
# → 扫描代码缺陷 (按类别/严重程度)

# 6. 模型同步
python -m livingtree models sync
# → 从所有配置提供商拉取模型列表
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
| 某 provider 404 | 模型 ID 不正确 | 运行 `livingtree models auto` 自动检测 |

---

## 环境要求

- Python >= 3.13
- 至少1个有效的 LLM API Key (推荐 deepseek)
- 可选: Node.js (MCP 外部工具), Numba (JIT加速), CUDA (GPU推理)
