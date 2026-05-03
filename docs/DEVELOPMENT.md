# 开发手册

## 环境要求

- Python 3.11+
- Windows 10/11 (x64)
- Windows Terminal (自动下载)
- DeepSeek API Key

## 依赖安装

```powershell
pip install -r requirements.txt
```

核心依赖：
- `textual>=8.2` — TUI 框架
- `litellm>=1.80` — LLM 统一路由
- `pydantic>=2.0` — 数据模型
- `loguru` — 结构化日志
- `aiohttp` — 异步HTTP
- `tree-sitter` + 语言包 — AST解析

## 项目结构

```
LivingTreeAlAgent/
├── livingtree/              # 核心包
│   ├── __init__.py          # 导出 LivingWorld, LifeEngine 等
│   ├── main.py              # CLI 入口
│   ├── dna/                 # 生命蓝图层
│   │   ├── life_engine.py   #   中央管线
│   │   ├── living_world.py  #   统一上下文
│   │   ├── dual_consciousness.py # LiteLLM路由
│   │   ├── genome.py        #   数字基因组
│   │   ├── safety.py        #   16层安全
│   │   ├── litellm_config.py #  本地定价
│   │   └── zeroize.py       #   密钥零化
│   ├── cell/                # 细胞AI层
│   │   ├── cell_ai.py       #   可训练AI细胞
│   │   ├── trainer.py       #   LoRA训练器
│   │   ├── distillation.py  #   知识蒸馏
│   │   ├── mitosis.py       #   细胞分裂
│   │   ├── phage.py         #   AST代码吞噬
│   │   ├── regen.py         #   细胞再生
│   │   ├── registry.py      #   细胞注册中心
│   │   └── swift_trainer.py #   MS-SWIFT集成
│   ├── knowledge/           # 知识管理层
│   │   ├── knowledge_base.py #  Bi-temporal知识库
│   │   ├── vector_store.py   #  向量存储
│   │   ├── knowledge_graph.py # 知识图谱
│   │   ├── format_discovery.py # 文档格式发现
│   │   └── gap_detector.py    #  知识空白检测
│   ├── capability/          # 能力工厂层
│   │   ├── tool_market.py   #   30个工具注册
│   │   ├── doc_engine.py    #   报告生成引擎
│   │   ├── code_engine.py   #   自注释代码引擎
│   │   ├── ast_parser.py    #   Tree-sitter解析器
│   │   ├── code_graph.py    #   代码知识图
│   │   ├── skill_factory.py #   技能工厂
│   │   ├── material_collector.py # 资料收集
│   │   └── tianditu.py      #   天地图集成
│   ├── execution/           # 任务编排层
│   │   ├── task_planner.py  #   5领域模板
│   │   ├── orchestrator.py  #   多Agent调度
│   │   ├── thinking_evolution.py # 认知进化引擎
│   │   ├── quality_checker.py    # 7阶段质量检查
│   │   ├── hitl.py          #   人机协同
│   │   ├── checkpoint.py    #   断点续传
│   │   ├── cost_aware.py    #   预算管控
│   │   └── self_healer.py   #   自我修复
│   ├── network/             # P2P网络层
│   ├── api/                 # FastAPI服务
│   ├── config/              # 配置+加密
│   ├── observability/       # 可观测性
│   ├── tui/                 # Textual终端界面
│   │   ├── app.py           #   主应用
│   │   ├── screens/         #   4个标签页
│   │   ├── widgets/         #   7个自定义组件
│   │   ├── wt_bootstrap.py  #   WT引导器
│   │   └── styles/          #   CSS主题
│   └── mcp/                 # MCP协议
├── client/src/business/     # 遗留业务逻辑
├── config/                  # 配置文件
│   ├── config.yaml          #   默认配置
│   └── secrets.enc          #   加密密钥库
├── scripts/                 # 工具脚本
├── docs/                    # 文档
└── run_tui.bat              # 一键启动
```

## 开发约定

### 导入规范

```python
# 新代码使用 livingtree 包
from livingtree.dna import LifeEngine, LivingWorld
from livingtree.cell import CellAI, Distillation
from livingtree.execution import TaskPlanner

# 通过 LivingWorld 访问子系统
engine = LifeEngine(world)
kb = world.knowledge_base
cg = world.code_graph
```

### 添加新工具

1. 在 `capability/tool_market.py` 中定义 handler 函数
2. 添加到 `ALL_TOOLS` 列表
3. 工具自动注册到 `ToolMarket`，可通过 `Ctrl+P` 命令面板调用

```python
def _my_tool(params: dict, world: Any = None) -> dict:
    # 实现逻辑
    return {"result": "ok"}

# 添加到 ALL_TOOLS
("my_tool", "Description", "category", {"properties": {...}}, _my_tool),
```

### 添加新报告模板

在 `capability/doc_engine.py` 的 `INDUSTRIAL_TEMPLATES` 字典中添加：

```python
INDUSTRIAL_TEMPLATES = {
    "我的报告": ["1 章节A", "1.1 小节", "2 章节B", ...],
    ...
}
```

### 添加新LLM提供商

修改 `config/config.yaml`：

```yaml
model:
  flash_model: "deepseek/deepseek-v4-flash"    # provider/model
  pro_model: "openai/gpt-4o"                   # 可切换到任意LiteLLM支持的提供商
  deepseek_api_key: ""                         # 存储在 secrets.enc
```

支持的提供商格式（通过LiteLLM）：`deepseek/`, `openai/`, `anthropic/`, `ollama/`, `groq/` 等 100+。

## 运行测试

```powershell
# 集成测试 (5项)
python -m livingtree test

# 工具市场测试
python -c "from livingtree.capability.tool_market import register_all_tools; print('OK')"

# 天地图瓦片测试
python -c "from livingtree.capability.tianditu import fetch_tile; data=fetch_tile('vec',6,3,12); print(len(data),'bytes')"
```

## 配置管理

### 配置文件优先级
1. `config/config.yaml` — 默认值
2. `config/secrets.enc` — 加密密钥
3. 环境变量 `LT_*` — 运行时覆盖

### 常用环境变量

| 变量 | 说明 |
|------|------|
| `LT_DEEPSEEK_API_KEY` | DeepSeek API密钥 |
| `LT_FLASH_MODEL` | 快速模型 |
| `LT_PRO_MODEL` | 深度模型 |
| `LT_NODE_NAME` | 节点名称 |
| `LT_LAN_PORT` | P2P端口 |
| `LT_LOG_LEVEL` | 日志级别 |

### 加密密钥库

```python
from livingtree.config.secrets import get_secret_vault
vault = get_secret_vault()
vault.set("deepseek_api_key", "sk-xxx")
key = vault.get("deepseek_api_key")
```

密钥存储在 `config/secrets.enc`（已加入 `.gitignore`），使用机器绑定的 XOR 加密。

## 定价参考

DeepSeek 官方定价（元/百万tokens）：

| 模型 | 输入 | 输出 | 有效期 |
|------|------|------|--------|
| deepseek-v4-flash | ¥1 | ¥2 | — |
| deepseek-v4-pro | ¥3 | ¥6 | 2.5折至2026-05-31 |

详见 `livingtree/dna/litellm_config.py` 和 `livingtree/execution/cost_aware.py`。
