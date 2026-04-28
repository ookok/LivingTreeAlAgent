# mattpocock/skills 集成说明

> **集成日期**: 2026-04-27
> **源仓库**: https://github.com/mattpocock/skills (24.9k stars, MIT License)
> **适配工具**: `client/src/business/skills_adapter.py`

## 集成概述

已将 `mattpocock/skills` 的 21 个专业工程师技能集成到 LivingTreeAlAgent，
所有技能已转换为 WorkBuddy 兼容格式，可直接使用。

## 已集成技能列表

| 技能名 | 功能 | 优先级 | 状态 |
|--------|------|--------|------|
| **tdd** | 测试驱动开发（红绿重构循环） | P0 | ✅ 已优化 |
| **write-a-skill** | 创建新技能的指南 | P0 | ✅ 已优化 |
| to-prd | 生成产品需求文档（PRD） | P1 | ✅ 已适配 |
| to-issues | 将需求拆解为 GitHub Issues | P1 | ✅ 已适配 |
| grill-me | 方案深度质询 | P1 | ✅ 已适配 |
| design-an-interface | 并行生成接口设计方案 | P1 | ✅ 已适配 |
| improve-codebase-architecture | 架构优化建议 | P1 | ✅ 已适配 |
| request-refactor-plan | 生成重构计划 | P1 | ✅ 已适配 |
| triage-issue | Bug 根因分析 | P2 | ✅ 已适配 |
| setup-pre-commit | 配置预提交钩子 | P2 | ✅ 已适配 |
| git-guardrails-claude-code | 拦截危险 Git 命令 | P2 | ⚠️ 需额外适配 |
| obsidian-vault | Obsidian 笔记管理 | P2 | ✅ 已适配 |
| edit-article | 文章改写 | P3 | ✅ 已适配 |
| ubiquitous-language | DDD 通用语言提取 | P3 | ✅ 已适配 |
| migrate-to-shoehorn | TypeScript 类型断言迁移 | P3 | ✅ 已适配 |
| scaffold-exercises | 生成习题结构 | P3 | ✅ 已适配 |
| caveman | (用途未公开) | P3 | ✅ 已适配 |
| domain-model | (用途未公开) | P3 | ✅ 已适配 |
| github-triage | (用途未公开) | P3 | ✅ 已适配 |
| qa | (用途未公开) | P3 | ✅ 已适配 |
| zoom-out | (用途未公开) | P3 | ✅ 已适配 |

## 使用方式

### 1. 加载技能

WorkBuddy 会自动加载 `.workbuddy/skills/` 下的所有技能。

**验证技能已加载**：
```powershell
python -c "import os; skills = os.listdir('.workbuddy/skills/mattpocock'); print('\n'.join(skills))"
```

### 2. 触发技能

**方式 A：直接提及触发词**
```
用户: 用 TDD 方式实现这个功能
用户: 帮我创建一个新技能
用户: 生成 PRD
```

**方式 B：通过 `use_skill` 工具**
```
use_skill(command="tdd")
use_skill(command="write-a-skill")
```

### 3. 示例：使用 tdd 技能

```
用户: 用 TDD 方式实现 ModelRouter 的 fallback 机制

Agent 操作流程:
1. [规划] 与用户确认接口设计、测试重点
2. [红] 写测试: test_fallback_when_primary_fails()
3. [绿] 最小实现: 添加 fallback 逻辑
4. [重构] 优化 fallback 选择策略
5. [重复] 为其他场景写测试
```

### 4. 示例：使用 write-a-skill 技能

```
用户: 帮我创建一个 EIAgent 专用的技能

Agent 操作流程:
1. [需求收集] 询问技能覆盖的任务/领域、使用场景、是否需要脚本
2. [起草技能] 创建 SKILL.md（带 YAML frontmatter）
3. [审查] 与用户确认覆盖范围、缺失内容
4. [安装] 放入 ~/.workbuddy/skills/ 或项目 .workbuddy/skills/
```

## 格式差异与适配说明

| 维度 | mattpocock/skills | WorkBuddy |
|------|-------------------|-----------|
| **SKILL.md 格式** | YAML frontmatter + Markdown | YAML frontmatter + Markdown（相同） |
| **frontmatter 字段** | name, description | name, description, location（额外字段） |
| **脚本语言** | Shell (.sh) | Python (.py) 推荐 |
| **安装方式** | `npx skills@latest add` | 放入 `.workbuddy/skills/` |
| **触发词** | description 字段 | description 字段（相同） |

**主要适配工作**：
1. 添加 `location: user` 到 YAML frontmatter
2. 保留原 Markdown 内容
3. 添加 LivingTreeAlAgent 适配说明
4. 为 Shell 脚本添加 Windows 兼容说明

## 待完成工作

- [ ] 为所有技能添加正确的 YAML frontmatter（当前只有 tdd 和 write-a-skill 有）
- [ ] 将 Shell 脚本转换为 Python 版本（提高 Windows 兼容性）
- [ ] 测试所有技能的实际触发效果
- [ ] 为 EIAgent 项目定制专用技能（基于这些通用技能）

## 更新与同步

当 mattpocock/skills 仓库更新时，重新运行适配工具：

```powershell
# 更新源仓库
cd .workbuddy/references/mattpocock-skills
git pull

# 重新运行适配工具
cd ../..
python client/src/business/skills_adapter.py --source ".workbuddy/references/mattpocock-skills" --target ".workbuddy/skills/mattpocock"
```

## 相关文件

- 适配工具: `client/src/business/skills_adapter.py`
- 源仓库: `.workbuddy/references/mattpocock-skills/`
- 输出目录: `.workbuddy/skills/mattpocock/`
- 索引文件: `.workbuddy/skills/mattpocock/INDEX.md`
