# LivingTree AI Agent

> *「根系装配园开放，每一位开发者都是嫁接者，将创新的枝条接入生命之树。」*

一个基于 PyQt6 的智能代理开发平台，集成本次会话实现的所有高级功能，包括企业级 P2P 存储、数字分身、积分经济系统和智能浏览器。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green.svg)](https://pypi.org/project/PyQt6/)

---

## 核心功能

### 🤖 智能代理架构

| 模块 | 说明 |
|------|------|
| **分层代理架构** | LLM Agent、SequentialAgent、ParallelAgent、LoopAgent 分层设计 |
| **角色管理系统** | agency-agents 风格，支持角色能力矩阵和协作工作流 |
| **共享工作空间** | OpenSpace 风格，多 Agent 共享上下文和消息总线 |
| **技能进化系统** | 技能固化、合并、分裂、遗忘完整生命周期管理 |

### 🎭 虚拟会议系统

| 模块 | 说明 |
|------|------|
| **虚拟会议** | 支持评审会、法庭、课堂等多种场景 |
| **数字分身** | 语音克隆、数字分身参加会议 |
| **实时字幕** | 流式 Whisper 实时语音识别 |
| **同声传译** | 多语言实时翻译 |
| **会议纪要** | LLM 自动生成会议纪要 |
| **虚拟形象** | Avatar 可视化会议 |

### 🔧 语音与音频

| 模块 | 说明 |
|------|------|
| **语音合成** | edge-tts、MOSS-TTS 声音克隆 |
| **噪声抑制** | WebRTC 风格噪声抑制 |
| **实时对话** | WebSocket 流式语音对话 |
| **会议录音** | 会议内容录音转录 |

### 🧬 AmphiLoop 引擎

| 模块 | 说明 |
|------|------|
| **双向调度** | 感知→推理→执行→反馈→调整完整闭环 |
| **检查点系统** | 执行状态快照与回滚 |
| **容错回滚** | 失败时自动回退到稳定状态 |
| **增量学习** | 从经验中持续优化 |

### ⚡ Entraly 优化

| 模块 | 说明 |
|------|------|
| **PRISM 优化器** | 4维评估体系（更新频率、使用频率、语义相似度、香农熵） |
| **0/1 背包选择** | 动态规划算法压缩上下文到最小 token 容量 |
| **实时仪表盘** | 本地监控 token 消耗和成本节省 |

### 🎯 Hermes Agent 技能系统

| 模块 | 说明 |
|------|------|
| **技能商店** | 技能浏览、下载、管理 |
| **技能制作** | 自定义技能创建向导 |
| **技能上传** | 上传到 Hermes Agent 或 agent-skills.io |
| **会议集成** | 在会议中使用技能 |

### 📝 提示词管理

| 模块 | 说明 |
|------|------|
| **版本管理** | 提示词版本控制与回滚 |
| **审计日志** | 完整的变更追踪 |
| **GEP 进化** | 基因表达式编程优化提示词 |

### 🏢 企业级 P2P 存储系统

| 模块 | 说明 |
|------|------|
| **企业节点管理** | 管理企业内的 P2P 节点，负责节点发现、资源分配和负载均衡 |
| **本地文件管理** | 记录本地文件路径，监控状态，删除只删路径 |
| **版本控制** | 支持文件版本管理，可回滚到历史版本 |
| **权限管理** | 完善的权限管理系统，支持细粒度权限控制 |
| **文件预览** | 支持常见文件格式的在线预览 |
| **同步功能** | 支持企业网盘与虚拟（聚合）云盘的同步 |

### 🚀 企业任务调度系统

| 模块 | 说明 |
|------|------|
| **智能任务调度** | 基于节点资源状态自动分配任务，支持任务优先级和依赖关系 |
| **任务分组管理** | 支持创建任务组，组内任务有序执行，实时跟踪组进度和状态 |
| **多任务类型** | 支持存储任务、计算任务、网络任务、维护任务和自定义任务 |
| **智能任务路由** | 基于 RouteLLM 算法的智能任务路由和成本优化 |
| **资源管理** | 任务资源需求定义，节点资源利用率监控，智能负载均衡 |

### 🌟 数字分身系统

| 模块 | 说明 |
|------|------|
| **数字分身管理** | 创建、管理和升级数字分身 |
| **数字分身出租** | 允许用户出租数字分身参与其他用户的活动 |
| **活动参与** | 数字分身可以参与各种活动，如会议、游戏等 |
| **积分交易** | 出租数字分身可以获得积分，积分可以用于其他服务 |

### 💰 积分经济系统

| 模块 | 说明 |
|------|------|
| **积分管理** | 管理用户积分，包括赚取、花费、转移和交易 |
| **成就系统** | 完成任务获得成就，提升用户等级 |
| **徽章系统** | 获得特殊徽章，展示用户成就 |
| **游戏系统** | 集成积分奖励和活动参与，如森林探险、数字猜谜等 |

### 🛒 电商系统

| 模块 | 说明 |
|------|------|
| **多种服务类型** | 实物商品、远程实景直播、AI 计算服务、远程代操作、知识咨询、数字商品 |
| **积分支付** | 支持使用积分购买商品和服务 |
| **支付流程** | 买家付款→资金冻结→服务开始→服务完成→打款卖家 |
| **佣金系统** | 自动计算和扣除佣金 |

### 🌐 AI 增强浏览器

| 模块 | 说明 |
|------|------|
| **浏览器自动化** | 支持导航、提取内容、填写表单、搜索、截图等操作 |
| **扩展系统** | 借鉴 qutebrowser 的插件系统，支持扩展的加载和管理 |
| **插件系统** | 支持插件的注册、钩子和命令 |
| **用户脚本系统** | 支持用户脚本的加载和执行 |
| **配置管理** | 完善的配置管理系统，支持配置的加载、保存和验证 |

### 🎨 A2UI 范式

| 模块 | 说明 |
|------|------|
| **自适应 UI** | 根据系统状态和用户需求自动调整 UI |
| **智能降级** | 当核心服务不可用时提供优雅的降级方案 |
| **按需加载** | 仅加载当前需要的 UI 组件 |
| **实时反馈** | 所有操作都有进度提示和状态反馈 |
| **快捷配置** | 所有配置调用都有快捷修改功能 |

---

## 技术架构

```
LivingTreeAlAgent/
├── core/                          # 核心业务模块
│   ├── living_tree_ai/            # 主体架构
│   │   ├── agency_integration/     # Agency 集成
│   │   │   ├── role_manager.py          # 角色管理
│   │   │   ├── shared_workspace.py      # 共享工作空间
│   │   │   └── a2ui_components.py       # A2UI 组件
│   │   ├── voice/                 # 语音系统
│   │   │   ├── virtual_conference.py    # 虚拟会议
│   │   │   ├── digital_twin.py          # 数字分身
│   │   │   ├── voice_clone_transcribe.py
│   │   │   ├── streaming_whisper.py      # 流式识别
│   │   │   ├── conference_translation.py # 同声传译
│   │   │   └── meeting_summary.py        # 会议纪要
│   │   ├── skills/                # 技能系统
│   │   │   ├── skill_manager.py           # 技能管理
│   │   │   └── skill_conference_integration.py
│   │   └── browser_gateway/       # AI 增强浏览器
│   │       ├── extensions/               # 扩展系统
│   │       │   ├── extension_manager.py    # 扩展管理器
│   │       │   ├── plugin_system.py       # 插件系统
│   │       │   ├── user_scripts.py        # 用户脚本系统
│   │       │   └── api.py                 # 扩展 API
│   │       ├── config/                   # 配置管理
│   │       │   ├── config_manager.py      # 配置管理器
│   │       │   ├── config_types.py        # 配置类型
│   │       │   └── config_validator.py    # 配置验证器
│   │       ├── browser_use_adapter.py     # 浏览器适配器
│   │       └── browser_pool.py            # 浏览器池
│   ├── amphiloop/                 # AmphiLoop 引擎
│   │   └── amphiloop_engine.py          # 双向循环调度
│   ├── skill_evolution/            # 技能进化
│   │   ├── agent_loop.py                # Agent 循环
│   │   └── models.py                    # 进化模型
│   ├── optimization/               # Entraly 优化
│   │   ├── prism_optimizer.py            # PRISM 优化器
│   │   ├── knapsack_selector.py          # 0/1 背包选择
│   │   └── realtime_dashboard.py          # 实时仪表盘
│   ├── evolution/                  # 进化系统
│   │   ├── gep_integration.py            # GEP 集成
│   │   └── prompt_versioning.py         # 提示词版本
│   ├── enterprise/                 # 企业级功能
│   │   ├── node_manager.py              # 企业节点管理
│   │   ├── storage.py                   # 企业存储系统
│   │   ├── file_preview.py              # 文件预览
│   │   ├── permission.py                # 权限管理
│   │   ├── sync.py                      # 同步功能
│   │   ├── version_control.py           # 版本控制
│   │   ├── local_file_manager.py        # 本地文件管理
│   │   └── task_scheduler.py            # 任务调度系统
│   ├── digital_twin/               # 数字分身系统
│   │   └── user_twin.py                 # 用户数字分身
│   ├── credit_economy/             # 积分经济系统
│   │   └── system.py                    # 积分经济系统
│   ├── decommerce/                 # 电商系统
│   │   ├── models.py                    # 电商模型
│   │   ├── buyer_client.py             # 买家客户端
│   │   ├── seller_node.py              # 卖家节点
│   │   └── crdt_order.py               # 订单管理
│   └── p2p_cdn/                    # P2P CDN 系统
│       ├── storage.py                   # 存储管理
│       ├── cache_manager.py             # 缓存管理
│       └── router.py                    # 路由管理
├── ui/                            # PyQt6 UI
│   ├── workflow_panel/             # 工作流面板
│   ├── enterprise_panel/           # 企业功能面板
│   ├── digital_twin_panel/         # 数字分身面板
│   └── browser_panel/              # 浏览器面板
└── server/                        # 服务端
    ├── relay_server/               # 中继服务器
    └── shared/                     # 共享组件
```

---

## 快速开始

### 环境要求

- Python 3.11+
- PyQt6
- Windows 10+ / macOS / Ubuntu

### 安装依赖

```bash
pip install PyQt6 numpy websockets

# 可选依赖
pip install openai-whisper edge-tts browser-use
```

### 启动虚拟会议

```python
from core.living_tree_ai.voice.virtual_conference import VirtualConferenceSystem, ReviewMeetingScenario

# 创建评审会
conference = ReviewMeetingScenario.create_review_meeting(llm_handler=your_llm)
conference.start()

# 添加参与者
conference.add_participant(
    name="张专家",
    role=conference.roles["expert"],
    is_ai_controlled=True,
    llm_handler=your_llm
)
```

### 使用 AmphiLoop

```python
from core.amphiloop import get_amphiloop_engine

engine = get_amphiloop_engine()
engine.current_task_id = "task_001"

# 创建检查点
checkpoint = engine.checkpoint_manager.create_checkpoint(
    task_id="task_001",
    turn=5,
    phase="execute",
    state={"data": "..."},
    messages=[],
    execution_records=[]
)

# 处理失败
rollback_checkpoint = engine.handle_failure("Tool execution failed")
```

### 使用 Entraly 优化

```python
from core.optimization import get_entroly_optimizer

optimizer = get_entroly_optimizer()
optimizer.start_session()

# 优化上下文
fragments = [
    ("def foo(): pass", "test.py", 10),
    ("class Bar: pass", "test.py", 20),
]
result = optimizer.optimize_context("函数用法", fragments)
print(f"Token 减少: {result.token_reduction_percent:.1f}%")

# 获取仪表盘
dashboard_data = optimizer.get_dashboard_data()
```

### 使用企业存储系统

```python
from core.enterprise import get_enterprise_storage

# 获取企业存储实例
storage = get_enterprise_storage("enterprise_1")

# 上传本地文件（只记录路径）
file_id = await storage.upload_local_file(
    name="report.pdf",
    parent_id="root",
    local_path="C:\\reports\\2024-Q1.pdf",
    owner="user1"
)

# 获取文件信息
file = storage.get_file(file_id)
print(f"File: {file.name}, Path: {file.metadata.get('local_path')}")

# 版本控制
versions = storage.version_control.get_versions(file_id)
print(f"Versions: {len(versions)}")
```

### 使用任务调度系统

```python
from core.enterprise import get_enterprise_task_scheduler, EnterpriseTask, TaskGroup, TaskType

# 获取调度器
scheduler = get_enterprise_task_scheduler("enterprise_1")

# 创建任务组
group = TaskGroup(
    group_id="group_1",
    enterprise_id="enterprise_1",
    name="数据处理任务组",
    description="处理企业数据的任务组"
)
group_id = scheduler.create_task_group(group)

# 创建任务
task = EnterpriseTask(
    task_id="task_1",
    enterprise_id="enterprise_1",
    title="数据备份",
    task_type=TaskType.STORAGE,
    priority=3,
    required_storage=1024,  # 1GB
    group_id=group_id
)
scheduler.create_task(task)
```

### 使用数字分身系统

```python
from core.digital_twin import get_user_twin_manager

# 获取数字分身管理器
twin_manager = get_user_twin_manager()

# 创建数字分身
twin_id = twin_manager.create_twin(
    user_id="user1",
    name="我的数字分身",
    description="我的第一个数字分身"
)

# 出租数字分身
rental_id = twin_manager.rent_twin(
    twin_id=twin_id,
    renter_id="user2",
    activity_id="activity_1",
    duration_hours=2,
    price=100
)

# 接受出租请求
twin_manager.accept_rental(rental_id)

# 完成出租
twin_manager.complete_rental(rental_id)
```

### 使用积分经济系统

```python
from core.credit_economy import get_credit_economy_system

# 获取积分经济系统
economy = get_credit_economy_system()

# 增加积分
economy.add_credits("user1", 100, "完成任务奖励")

# 转移积分
economy.transfer_credits("user1", "user2", 50, "租金支付")

# 获取用户积分
credits = economy.get_user_credits("user1")
print(f"User1 credits: {credits}")

# 获得成就
economy.award_achievement("user1", "first_rental", "完成第一次出租")
```

### 使用 AI 增强浏览器

```python
from core.living_tree_ai.browser_gateway import create_browser_use_adapter

# 创建浏览器适配器
adapter = create_browser_use_adapter()

# 初始化
await adapter.initialize()

# 执行任务
result = await adapter.execute_task("打开百度并搜索 'AI 浏览器'")
print(f"Task result: {result['final_result']}")

# 导航到网页
await adapter.navigate("https://www.github.com")

# 提取页面内容
content = await adapter.extract_content("https://www.github.com")
print(f"Page content: {content['final_result'][:100]}...")

# 关闭浏览器
await adapter.close()
```

---

## 核心模块详解

### 共享工作空间 (OpenSpace)

```python
from core.living_tree_ai.agency_integration.shared_workspace import SharedWorkspace

workspace = SharedWorkspace()
workspace.register_agent("agent_1", "Agent One", role="developer")

# 设置共享上下文
workspace.set_context("project_status", "in_progress", owner_id="agent_1")

# 发送消息
await workspace.send_message(
    sender_id="agent_1",
    sender_name="Agent One",
    msg_type="update",
    content="任务完成"
)
```

### 角色能力矩阵

```python
from core.living_tree_ai.agency_integration.role_manager import get_role_manager

manager = get_role_manager()

# 获取技能雷达图
radar = manager.get_skill_radar_data("Full Stack Engineer")
# {'labels': ['Python', 'JavaScript'], 'values': [3, 3], 'overall_score': 3.0}

# 自动分配角色
assignments = manager.auto_assign_roles(
    task_description="开发一个 Web 应用",
    available_agents=[("agent_1", "张三"), ("agent_2", "李四")]
)
```

### 数字分身

```python
from core.living_tree_ai.voice.digital_twin import get_twin_manager

twin_manager = get_twin_manager()

# 录音克隆
twin_manager.clone_from_recording(
    reference_audio_path="my_voice.wav",
    twin_name="我的分身"
)

# 使用分身
twin = twin_manager.create_twin_session("my_twin")
response = await twin_manager.twin_speak(twin.twin_id, "你好，我是数字分身")
```

### PRISM 优化器

```python
from core.optimization.prism_optimizer import PRISMOptimizer, ShannonEntropyCalculator

# 计算香农熵
entropy = ShannonEntropyCalculator.calculate_entropy("def foo(): pass")
print(f"香农熵: {entropy:.4f}")

# 过滤噪音
optimizer = PRISMOptimizer()
filtered = optimizer.filter_noise(query="函数用法", top_k=5)
```

### 企业存储系统

```python
from core.enterprise import get_enterprise_storage

# 获取企业存储实例
storage = get_enterprise_storage("enterprise_1")

# 上传本地文件（只记录路径）
file_id = await storage.upload_local_file(
    name="report.pdf",
    parent_id="root",
    local_path="C:\\reports\\2024-Q1.pdf",
    owner="user1"
)

# 下载文件（对于本地文件，会返回本地路径）
file_path = await storage.download_file(file_id, "downloads")
print(f"Downloaded to: {file_path}")

# 删除文件（只删除路径记录）
await storage.delete_file(file_id)
```

### 任务调度系统

```python
from core.enterprise import get_enterprise_task_scheduler, EnterpriseTask, TaskType

# 获取调度器
scheduler = get_enterprise_task_scheduler("enterprise_1")

# 创建任务
task = EnterpriseTask(
    task_id="task_1",
    enterprise_id="enterprise_1",
    title="数据处理",
    task_type=TaskType.COMPUTING,
    priority=4,
    required_cpu=2.0,
    required_memory=4096
)

# 添加任务
task_id = scheduler.create_task(task)

# 获取任务状态
task_status = scheduler.get_task(task_id)
print(f"Task status: {task_status.status}")

# 取消任务
scheduler.cancel_task(task_id)
```

### 数字分身出租

```python
from core.digital_twin import get_user_twin_manager

# 获取数字分身管理器
twin_manager = get_user_twin_manager()

# 创建活动
activity_id = twin_manager.create_activity(
    name="技术分享会",
    description="分享 AI 技术最新进展",
    organizer_id="user1",
    duration_hours=2
)

# 出租数字分身
rental_id = twin_manager.rent_twin(
    twin_id="twin_1",
    renter_id="user2",
    activity_id=activity_id,
    duration_hours=2,
    price=100
)

# 接受出租请求
twin_manager.accept_rental(rental_id)

# 完成出租
twin_manager.complete_rental(rental_id)

# 获取出租历史
rentals = twin_manager.get_user_rentals("user1")
print(f"Total rentals: {len(rentals)}")
```

### 积分经济系统

```python
from core.credit_economy import get_credit_economy_system

# 获取积分经济系统
economy = get_credit_economy_system()

# 增加积分
economy.add_credits("user1", 100, "完成任务奖励")

# 转移积分
economy.transfer_credits("user1", "user2", 50, "租金支付")

# 获取用户积分
credits = economy.get_user_credits("user1")
print(f"User1 credits: {credits}")

# 获取用户成就
achievements = economy.get_user_achievements("user1")
print(f"User1 achievements: {len(achievements)}")

# 获取用户徽章
badges = economy.get_user_badges("user1")
print(f"User1 badges: {len(badges)}")
```

### AI 增强浏览器

```python
from core.living_tree_ai.browser_gateway import create_browser_use_adapter
from core.living_tree_ai.browser_gateway.extensions import get_extension_manager

# 创建浏览器适配器
adapter = create_browser_use_adapter()

# 初始化
await adapter.initialize()

# 执行任务
result = await adapter.execute_task("打开百度并搜索 'AI 浏览器'")
print(f"Task result: {result['final_result']}")

# 填写表单
form_data = {
    "username": "test",
    "password": "password"
}
result = await adapter.fill_form("https://example.com/login", form_data)
print(f"Form fill result: {result['final_result']}")

# 搜索内容
result = await adapter.search("Python programming")
print(f"Search result: {result['final_result'][:100]}...")

# 截图
result = await adapter.screenshot("https://www.github.com", "github.png")
print(f"Screenshot saved to: {result['final_result']}")

# 关闭浏览器
await adapter.close()
```

---

## 贡献指南

### 提交规范

```
feat(core): 添加新功能
fix(ui): 修复界面bug
docs: 更新文档
refactor: 重构代码
perf(optimization): 性能优化
feat(enterprise): 企业功能相关
feat(digital_twin): 数字分身相关
feat(credit_economy): 积分经济相关
feat(browser): 浏览器功能相关
```

---

## 更新日志

### 2026-04-20

- 新增 AmphiLoop 引擎（双向循环调度、容错回滚、增量学习）
- 新增 Entraly 优化（PRISM 优化器、0/1 背包、实时仪表盘）
- 新增 Hermes Agent 技能系统
- 新增数字分身功能
- 新增共享工作空间
- 新增角色能力矩阵
- 新增企业级 P2P 存储系统（本地文件管理、版本控制、权限管理、文件预览、同步功能）
- 新增企业任务调度系统（智能任务调度、任务分组管理、多任务类型、智能任务路由、资源管理）
- 新增数字分身出租功能（数字分身管理、出租、活动参与、积分交易）
- 新增积分经济系统（积分管理、成就系统、徽章系统、游戏系统）
- 新增电商系统（多种服务类型、积分支付、支付流程、佣金系统）
- 新增 AI 增强浏览器（浏览器自动化、扩展系统、插件系统、用户脚本系统、配置管理）

---

## 致谢

- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) - Hermes Agent 架构参考
- [OpenSpace HKUDS](https://github.com/) - 多 Agent 协作空间理念
- [Entroly](https:///) - PRISM 优化算法灵感
- [AmphiLoop](https:///) - 双向循环调度理念

---

*LivingTree AI Agent - 让智能体自我进化* 🌟
