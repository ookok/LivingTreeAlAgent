# LivingTreeAI 内置技能目录

本目录包含 LivingTreeAI 项目**内置集成**的技能与专家角色库。

## 📁 目录结构

```
.livingtree/skills/
├── mattpocock/              # mattpocock/skills (21个工程技能)
│   ├── tdd/
│   │   └── SKILL.md
│   ├── write-a-skill/
│   │   └── SKILL.md
│   └── ... (共21个技能目录)
│
└── agency-agents-zh/        # agency-agents-zh (199个专家角色)
    ├── academic-anthropologist/
    │   └── SKILL.md
    ├── engineering-ai-engineer/
    │   └── SKILL.md
    └── ... (共199个角色目录)
```

## 🎯 设计理念

### 为什么放在 `.livingtree/` 目录？

| 目录 | 用途 | 说明 |
|------|------|------|
| `.livingtree/` | **项目内置** | 随项目版本控制，所有用户共享 |
| `.workbuddy/` | **用户级** | 用户个人配置，不纳入版本控制 |

**优势**：
- ✅ 技能作为项目一部分，统一版本管理
- ✅ 新用户克隆项目后，立即可用所有内置技能
- ✅ 用户可自定义添加技能到 `.workbuddy/skills/`，不影响项目内置技能

## 📚 已集成的技能库

### 1. mattpocock/skills (21个)

**来源**: https://github.com/mattpocock/skills (24.9k stars)

**包含的技能**：
- `tdd` - 测试驱动开发（TDD）流程引导
- `write-a-skill` - 创建新技能指南
- `to-prd` - 生成产品需求文档
- `improve-codebase-architecture` - 架构优化建议
- `design-an-interface` - 并行生成接口设计方案
- ... (共21个工程技能)

### 2. agency-agents-zh (199个)

**来源**: https://github.com/agency-agents-zh/agency-agents-zh

**包含的专家角色**（按部门分类）：
- `academic/` - 学术专家（人类学家、地理学家、历史学家等）
- `design/` - 设计专家（UI设计师、UX架构师、品牌守护者等）
- `engineering/` - 工程专家（AI工程师、后端架构师、前端开发等）
- `finance/` - 财务专家（财务分析师、风险管理师、投资顾问等）
- `marketing/` - 市场专家（增长经理、内容策略师、SEO专家等）
- `product/` - 产品专家（产品经理、数据分析师、UX研究员等）
- `sales/` - 销售专家（销售教练、售前工程师、投标策略师等）
- `specialized/` - 专业领域（MCP构建者、会议助手、文档生成器等）
- ... (共18个部门，199个专家角色)

## 🔧 技能格式

每个技能一个子目录，包含 `SKILL.md` 文件（WorkBuddy 格式）：

```yaml
---
name: 技能名称
description: 技能描述（包含触发词）
location: user
color: 颜色（可选，agency-agents-zh特有）
---

# 技能标题

技能详细内容...
```

**与 mattpocock 原始格式的差异**：
| 字段 | mattpocock/skills | WorkBuddy |
|------|-------------------|-------------|
| `name` | ✅ | ✅ |
| `description` | ✅ | ✅ |
| `location` | ❌ | ✅ 必需 |
| `color` | ❌ | ✅ 可选（agency-agents-zh） |

## 🚀 使用方式

### 1. 通过技能中心面板（推荐）

1. 启动 LivingTreeAI 客户端
2. 点击左侧工具菜单 → **「🧠 技能中心」**
3. 浏览三个标签页：
   - **⚡ 技能库** - 查看所有 220 个技能
   - **👤 专家角色** - 按部门浏览 199 个专家角色
   - **✅ 已启用** - 管理已启用的技能
4. 选中技能 → 点击 **「✅ 启用技能」**
5. 在对话中，触发词会自动加载对应技能

### 2. 对话中直接触发

启用技能后，对话中提及触发词会自动加载：

```
用户: 用 TDD 方式实现这个功能
→ 自动触发 tdd 技能（测试驱动开发）

用户: 帮我用产品经理视角分析这个需求
→ 自动触发 产品经理 角色（agency-agents-zh）
```

## 🔄 更新技能库

### 更新 mattpocock/skills

```powershell
# 1. 更新源仓库
cd d:\mhzyapp\LivingTreeAlAgent
git -C .workbuddy\references\mattpocock-skills pull

# 2. 重新运行适配工具
python client\src\business\skills_adapter.py
```

### 更新 agency-agents-zh

```powershell
# 1. 更新源仓库
cd d:\mhzyapp\LivingTreeAlAgent
git -C .workbuddy\references\agency-agents-zh pull

# 2. 重新运行适配工具
python client\src\business\agents_adapter.py
```

## 📝 添加自定义技能

### 方式1：添加到项目内置目录（所有用户共享）

1. 在 `.livingtree/skills/` 下创建子目录
2. 创建 `SKILL.md` 文件（参考现有技能格式）
3. 提交到 Git 版本控制

### 方式2：添加到用户级目录（仅当前用户）

1. 在 `~/.workbuddy/skills/` 下创建子目录
2. 创建 `SKILL.md` 文件
3. 不需要提交到 Git

**优先级**：用户级目录 > 项目内置目录（同名技能，用户级覆盖项目级）

## 🗂️ 相关目录

| 目录 | 说明 |
|------|------|
| `.livingtree/skills/` | 项目内置技能（本文档所在目录） |
| `.livingtree/references/` | 技能库源仓库（可选，用于重新适配） |
| `.workbuddy/skills/` | 用户级技能目录（可选） |
| `.workbuddy/active_skills.json` | 已启用技能列表（持久化） |

## 📖 适配工具说明

### skills_adapter.py

**路径**: `client/src/business/skills_adapter.py`

**功能**: 将 mattpocock/skills 适配为 WorkBuddy 格式

**使用**:
```powershell
python client\src\business\skills_adapter.py `
  --source ".workbuddy/references/mattpocock-skills" `
  --target ".livingtree/skills/mattpocock"
```

### agents_adapter.py

**路径**: `client/src/business/agents_adapter.py`

**功能**: 将 agency-agents-zh 专家角色适配为 WorkBuddy 格式

**使用**:
```powershell
python client\src\business\agents_adapter.py
```

（自动扫描 `.livingtree/references/agency-agents-zh/` 并适配到 `.livingtree/skills/agency-agents-zh/`）

## 📊 统计信息

| 项目 | 数量 |
|------|------|
| mattpocock/skills | 21 个工程技能 |
| agency-agents-zh | 199 个专家角色 |
| **总计** | **220 个** 内置技能 |
| 覆盖领域 | 工程、设计、产品、市场、财务、销售等 |
| 部门分类 | 18 个部门（agency-agents-zh） |

## 🛠️ SkillsPanel 面板

**路径**: `client/src/presentation/panels/skills_panel.py`

**功能**:
- 浏览所有内置技能（项目级 + 用户级）
- 按来源过滤（mattpocock / agency / 自定义）
- 按部门过滤（agency-agents-zh）
- 搜索技能名称、描述
- 启用/禁用技能
- 查看技能详情

**注册路由**: `client/src/presentation/router/routes.py`

## 📜 版本历史

- **2026-04-27**: 初始版本，集成 mattpocock/skills (21) + agency-agents-zh (199)
- **2026-04-27**: 从 `.workbuddy/skills/` 迁移到 `.livingtree/skills/`（项目内置目录）

---

**维护者**: LivingTreeAI 开发团队  
**最后更新**: 2026-04-27
