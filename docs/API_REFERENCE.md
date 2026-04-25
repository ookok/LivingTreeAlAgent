# LivingTreeAI API Reference

**版本**: 1.0.0
**日期**: 2026-04-26

---

## 目录

1. [Intent Engine](#1-intent-engine)
2. [Evolution Engine](#2-evolution-engine)
3. [Multi-Agent](#3-multi-agent)
4. [Proxy Gateway](#4-proxy-gateway)
5. [Plugin Manager](#5-plugin-manager)
6. [Marketplace](#6-marketplace)
7. [Finance Panel](#7-finance-panel)
8. [Game Panel](#8-game-panel)
9. [i18n](#9-i18n)

---

## 1. Intent Engine

### IntentEngine

意图驱动引擎核心类。

```python
from core.intent_engine.intent_engine import IntentEngine

engine = IntentEngine()

# 解析意图
result = engine.parse("帮我写一个Python函数")
```

#### 方法

| 方法 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| `parse(intent_text)` | 解析意图文本 | `intent_text: str` | `IntentResult` |
| `classify(intent_text)` | 分类意图 | `intent_text: str` | `IntentCategory` |
| `extract_entities(intent_text)` | 提取实体 | `intent_text: str` | `List[Entity]` |

### IntentCache

意图缓存系统。

```python
from core.intent_engine.intent_cache import IntentCache, get_intent_cache

cache = get_intent_cache()
cache.set("key", "value")
value = cache.get("key")
```

---

## 2. Evolution Engine

### EvolutionEngine

进化引擎核心类。

```python
from core.evolution.evolution_engine import EvolutionEngine, get_evolution_engine

engine = get_evolution_engine()
engine.evolve()
```

#### 方法

| 方法 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| `evolve()` | 执行进化 | - | `EvolutionResult` |
| `diagnose()` | 诊断问题 | - | `List[Issue>` |
| `repair()` | 修复问题 | - | `RepairResult` |
| `get_status()` | 获取状态 | - | `SystemStatus` |

---

## 3. Multi-Agent

### MultiAgentWorkflow

多代理协作工作流。

```python
from core.multi_agent.workflow_engine import MultiAgentWorkflow, get_multi_agent_workflow

workflow = get_multi_agent_workflow()
workflow.register_agent(agent)
workflow.create_task("task1", requirements)
```

### AgentOrchestrationViewer

编排可视化。

```python
from core.agent.orchestration_viewer import AgentOrchestrationViewer, get_orchestration_viewer

viewer = get_orchestration_viewer()
viewer.initialize_workflow("workflow1")
viewer.add_node("node1", "Agent 1", "planner")
```

---

## 4. Proxy Gateway

### SmartProxyGateway

智能代理网关。

```python
from core.smart_proxy_gateway import SmartProxyGateway, get_proxy_gateway, ProxyEndpoint

gateway = get_proxy_gateway()

# 注册端点
endpoint = ProxyEndpoint(
    id="proxy1",
    name="Proxy 1",
    url="http://proxy1.example.com"
)
gateway.register_endpoint(endpoint)

# 选择端点
selected = gateway.select_endpoint("/api/users")
```

---

## 5. Plugin Manager

### PluginManager

插件管理系统。

```python
from core.plugin_manager import PluginManager, get_plugin_manager, PluginInfo

manager = get_plugin_manager()

# 注册插件
info = PluginInfo(
    id="my-plugin",
    name="My Plugin",
    version="1.0.0",
    author="Author",
    description="Description"
)
manager.register_plugin(info)

# 加载插件
manager.load_plugin("my-plugin")
manager.activate_plugin("my-plugin")
```

---

## 6. Marketplace

### Marketplace

生态市场。

```python
from core.marketplace import Marketplace, get_marketplace, ListingType, PriceModel

marketplace = get_marketplace()

# 创建商品
listing = marketplace.create_listing(
    listing_type=ListingType.SKILL,
    name="Advanced Python Skill",
    description="Learn advanced Python",
    seller_id="seller1",
    price=99.0,
)

# 发布商品
marketplace.publish_listing(listing.id)

# 搜索
results = marketplace.search("Python")
```

---

## 7. Finance Panel

### FinanceHubPanel

金融面板。

```python
from client.src.presentation.panels.finance_hub_panel import FinanceHubPanel, get_finance_hub_panel, PanelTab

panel = get_finance_hub_panel()

# 切换选项卡
panel.switch_tab(PanelTab.INVESTMENT)

# 获取投资组件
investment = panel.get_widget(PanelTab.INVESTMENT)

# 获取整体摘要
summary = panel.get_overall_summary()
```

---

## 8. Game Panel

### GameHubPanel

游戏面板。

```python
from client.src.presentation.panels.game_hub_panel import GameHubPanel, get_game_hub_panel, Game, GameStatus

panel = get_game_hub_panel()

# 添加游戏
game = Game(
    id="game1",
    name="My Game",
    genre="RPG",
    platform="PC"
)
panel.add_game(game)

# 开始游戏
panel.start_playing("game1")

# 停止游戏
panel.stop_playing()
```

---

## 9. i18n

### LanguageManager

多语言管理器。

```python
from core.i18n.language_manager import LanguageManager, get_language_manager, Language, t

manager = get_language_manager()

# 设置语言
manager.set_language(Language.EN)

# 翻译
text = manager.t("app.name")
text = t("button.save")  # 便捷函数

# 复数形式
text = manager.tn("item", "items", count)
```

---

## 错误码

| 错误码 | 说明 |
|--------|------|
| `LT001` | 意图解析失败 |
| `LT002` | 进化引擎错误 |
| `LT003` | 代理通信失败 |
| `LT004` | 网关选择失败 |
| `LT005` | 插件加载失败 |
| `LT006` | 市场交易失败 |

---

## 事件

### IntentEngine 事件

| 事件 | 说明 |
|------|------|
| `intent_parsed` | 意图解析完成 |
| `intent_classified` | 意图分类完成 |
| `entity_extracted` | 实体提取完成 |

### EvolutionEngine 事件

| 事件 | 说明 |
|------|------|
| `evolution_started` | 进化开始 |
| `evolution_completed` | 进化完成 |
| `issue_detected` | 问题检测 |
| `repair_completed` | 修复完成 |

---

## 类型定义

### IntentResult

```python
@dataclass
class IntentResult:
    intent: str
    category: IntentCategory
    entities: List[Entity]
    confidence: float
    metadata: Dict[str, Any]
```

### EvolutionResult

```python
@dataclass
class EvolutionResult:
    generation: int
    fitness: float
    improvements: List[str]
    issues_fixed: int
    duration: float
```

---

**LivingTreeAI - Build the Future of AI Coding! 🚀**
