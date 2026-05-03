# 用户手册

## 启动

### 桌面快捷方式 (推荐)
双击桌面 **LivingTree AI Agent** 图标，自动在 Windows Terminal 中启动。

### 命令行

```powershell
cd LivingTreeAlAgent
python -m livingtree tui
```

首次启动自动检查 Windows Terminal，如未安装自动下载到 `.wt/` 目录。

---

## 界面说明

### 标签页

| 标签 | 快捷键 | 功能 |
|------|--------|------|
| **Chat** | `Ctrl+1` | AI对话、文件上传、Markdown渲染、任务树 |
| **Code** | `Ctrl+2` | 代码编辑、AI生成、AST解析、调用链分析 |
| **Docs** | `Ctrl+3` | 文件浏览器、知识库搜索、格式发现 |
| **Settings** | `Ctrl+4` | API配置、基因组开关、细胞训练 |

### 全局快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Q` | 退出 |
| `Ctrl+P` | 命令面板 (30个工具) |
| `Ctrl+D` | 暗/亮主题 |
| `F5` | 刷新 |

---

## Chat 聊天

### 基本对话
在底部输入框输入内容，`Enter` 发送。系统自动判断复杂度，简单问题用 flash 模型，复杂问题(>200字或含分析/推理关键词)用 pro 模型深度推理。

### 斜杠命令

| 命令 | 功能 | 示例 |
|------|------|------|
| `/code 描述` | AI生成代码 | `/code 写一个高斯扩散计算函数` |
| `/report 类型` | 生成报告 | `/report 环评报告` |
| `/analyze 主题` | 深度分析 | `/analyze 这个项目的环境风险` |
| `/search 关键词` | 知识搜索 | `/search GB3095` |
| `/search 2023 关键词` | 时间回溯 | `/search 2023-06 环评标准` |
| `/file 路径` | 预览文件 | `/file ./data/report.md` |

### 文件上传
点击 **File** 按钮，选择文件。图片文件自动标注尺寸，源码文件自动语法高亮预览。

### 任务树
左侧面板实时显示 AI 处理管线: `○ 感知 → ● 认知 → ● 规划 → ◐ 执行 → ○ 反思 → ○ 进化`。底部显示 Token 消耗和费用。

---

## Code 代码编辑

### 基本操作
- 工具栏选择语言 → 输入文件路径 → **Open** 打开 / **Save** 保存
- **AI Gen** 自动生成代码
- **Run** 运行 Python 代码

### 代码图工具
使用前点击 **Index** 索引代码库，然后：

| 工具 | 功能 |
|------|------|
| **Callers** | 查找谁调用了当前函数 |
| **Callees** | 查找当前函数调用了谁 |
| **Blast** | 分析文件变更影响范围 |
| **Hubs** | 找出架构热点 |
| **AST** | 显示语法树结构 |

---

## Docs 文档管理

- 左侧文件树浏览工作区
- 点击文件预览内容（代码语法高亮、Markdown渲染）
- **Search KB**: 搜索知识库
- **Formats**: 分析文档格式
- **Gaps**: 检测知识空白
- **Index**: 索引代码库到代码知识图
- **Save As**: 另存当前文件
- **Analyze**: AI分析当前文档

---

## Settings 设置

### 配置
- API Key（保存后自动加密存储）
- 模型选择
- 思考模式开关

### 基因组开关
控制数字生命体的基因表达：

| 基因 | 控制 |
|------|------|
| DNA Engine | 环境/安全领域知识可见性 |
| Knowledge Layer | 知识库访问 |
| Capability Layer | 技能/工具可用性 |
| Network Layer | P2P网络 |
| Cell Layer | 细胞训练 |
| Self Evolution | 自主进化 |
| Code Absorption | 代码吞噬 |

修改后点击 **Apply Genes** 生效。

### 细胞训练
- 输入 Cell Name + Model ID
- 选择训练类型: LoRA / Full / Distill / GRPO
- **Drill Train** 启动 MS-SWIFT 训练
- **Absorb Code** 吞噬代码库为细胞能力

---

## 命令面板 (Ctrl+P)

统一搜索入口，30个工具分类:

| 类别 | 工具 |
|------|------|
| 代码 | Generate Code, Blast Radius, Find Callers, Parse AST... |
| 聊天 | Deep Analyze, Generate Report |
| 文档 | Index Codebase, Search Knowledge, Detect Gaps... |
| 系统 | Status, Metrics, Health Check, Peers |
| 训练 | Train Cell, Drill Train, Absorb Codebase |

---

## API 服务

```powershell
python -m livingtree server
```

启动后访问 `http://localhost:8100/docs` 查看 Swagger 文档。

主要端点：
- `POST /api/chat` — 发送消息
- `POST /api/report/generate` — 生成工业报告
- `POST /api/cell/train` — 训练细胞
- `GET /api/hitl/pending` — 查看待审批任务
- `POST /api/hitl/approve` — 批准任务
- `GET /api/cost/status` — 预算状态

---

## 知识库

### 添加知识

```python
from livingtree.knowledge.knowledge_base import KnowledgeBase, Document
from datetime import datetime

kb = KnowledgeBase()
doc = Document(
    title="GB3095-2012 环境空气质量标准",
    content="...",
    domain="eia",
    valid_from=datetime(2016, 1, 1),
    source="manual",
)
kb.add_knowledge(doc)
```

### 时间点查询

```python
# 当前有效
results = kb.search_current("空气质量")

# 2023年的标准
results = kb.search_as_of("空气质量", as_of=datetime(2023, 6, 15))

# 全量历史
results = kb.history()
```

---

## 桌面快捷方式

双击桌面图标或运行：

```powershell
python scripts/install_shortcut.py
```

生成 `LivingTree AI Agent.lnk` 到桌面，带绿树图标。

---

## 联系方式

- 🌐 官网: [www.livingtree-ai.com](https://www.livingtree-ai.com)
- 📧 邮箱: livingtreeai@163.com
- 🐙 GitHub: [ookok/LivingTreeAlAgent](https://github.com/ookok/LivingTreeAlAgent)
