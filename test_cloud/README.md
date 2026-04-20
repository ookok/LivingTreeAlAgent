# LivingTree AI Agent

> *「根系装配园开放，每一位开发者都是嫁接者，将创新的枝条接入生命之树。」*

一个基于 PyQt6 的智能代理开发平台，集成本次会话实现的所有高级功能。

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
│   │   └── skills/                # 技能系统
│   │       ├── skill_manager.py           # 技能管理
│   │       └── skill_conference_integration.py
│   ├── amphiloop/                 # AmphiLoop 引擎
│   │   └── amphiloop_engine.py          # 双向循环调度
│   ├── skill_evolution/            # 技能进化
│   │   ├── agent_loop.py                # Agent 循环
│   │   └── models.py                    # 进化模型
│   ├── optimization/               # Entraly 优化
│   │   ├── prism_optimizer.py            # PRISM 优化器
│   │   ├── knapsack_selector.py          # 0/1 背包选择
│   │   └── realtime_dashboard.py          # 实时仪表盘
│   └── evolution/                  # 进化系统
│       ├── gep_integration.py            # GEP 集成
│       └── prompt_versioning.py         # 提示词版本
├── ui/                            # PyQt6 UI
│   └── workflow_panel/             # 工作流面板
└── server/                        # 服务端
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
pip install openai-whisper edge-tts
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

---

## 贡献指南

### 提交规范

```
feat(core): 添加新功能
fix(ui): 修复界面bug
docs: 更新文档
refactor: 重构代码
perf(optimization): 性能优化
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

---

## 致谢

- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) - Hermes Agent 架构参考
- [OpenSpace HKUDS](https://github.com/) - 多 Agent 协作空间理念
- [Entroly](https:///) - PRISM 优化算法灵感
- [AmphiLoop](https:///) - 双向循环调度理念

---

*LivingTree AI Agent - 让智能体自我进化* 🌟
