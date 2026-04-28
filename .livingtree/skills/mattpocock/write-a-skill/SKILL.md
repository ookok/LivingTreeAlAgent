---
name: write-a-skill
description: 创建新的 Agent 技能（SKILL.md）。当用户要求"创建技能"、"新建skill"、"write a skill"、"帮我写一个技能"时触发。支持生成符合WorkBuddy格式的完整技能包。
location: user
---

# Writing Skills

> **来源**: mattpocock/skills (`write-a-skill`)
> **适配**: 已转换为 WorkBuddy 格式

## Process

1. **Gather requirements** - ask user about:
   - What task/domain does the skill cover?
   - What specific use cases should it handle?
   - Does it need executable scripts or just instructions?
   - Any reference materials to include?

2. **Draft the skill** - create:
   - SKILL.md with concise instructions (including YAML frontmatter)
   - Additional reference files if content exceeds 500 lines
   - Utility scripts if deterministic operations needed

3. **Review with user** - present draft and ask:
   - Does this cover your use cases?
   - Anything missing or unclear?
   - Should any section be more/less detailed?

## Skill Structure (WorkBuddy Format)

```
skill-name/
├── SKILL.md           # Main instructions (required, with YAML frontmatter)
├── REFERENCE.md       # Detailed docs (if needed)
├── EXAMPLES.md        # Usage examples (if needed)
└── scripts/           # Utility scripts (if needed)
    └── helper.py      # Note: WorkBuddy uses Python, not JS
```

## SKILL.md Template (WorkBuddy Format)

```md
---
name: skill-name
description: Brief description of capability. Use when [specific triggers]. (Must be in third person, max 1024 chars)
location: user  # or manager, plugin
---

# Skill Name

## Quick start

[Minimal working example - help the agent use this skill effectively]

## Workflows

[Step-by-step processes with checklists for complex tasks]

## Advanced features

[Link to separate files: See [REFERENCE.md](REFERENCE.md)]
```

## Description Requirements

The description is **the only thing your agent sees** when deciding which skill to load. It's surfaced in the system prompt alongside all other installed skills. Your agent reads these descriptions and picks the relevant skill based on the user's request.

**Goal**: Give your agent just enough info to know:

1. What capability this skill provides
2. When/why to trigger it (specific keywords, contexts)

**Format**:

- Max 1024 chars
- Write in third person
- First sentence: what it does
- Second sentence: "Use when [specific triggers]"

**Good example**:

```
Extract text and tables from PDF files, fill forms, merge documents. Use when working with PDF files or when user mentions PDFs, forms, or document extraction.
```

**Bad example**:

```
Helps with documents.
```

The bad example gives your agent no way to distinguish this from other document skills.

## When to Add Scripts

Add utility scripts when:

- Operation is deterministic (validation, formatting)
- Same code would be generated repeatedly
- Errors need explicit handling

**WorkBuddy Note**: Use Python scripts (not JS/Shell) for maximum compatibility.

Scripts save tokens and improve reliability vs generated code.

## When to Split Files

Split into separate files when:

- SKILL.md exceeds 100 lines
- Content has distinct domains (finance vs sales schemas)
- Advanced features are rarely needed

## Review Checklist

After drafting, verify:

- [ ] Description includes triggers ("Use when...")
- [ ] SKILL.md under 100 lines (excluding frontmatter)
- [ ] No time-sensitive info
- [ ] Consistent terminology
- [ ] Concrete examples included
- [ ] References one level deep
- [ ] YAML frontmatter is valid

## LivingTreeAlAgent 适配说明

本技能已适配 LivingTreeAlAgent，使用时：

1. **创建技能**：`write-a-skill` 会生成符合 WorkBuddy 格式的 SKILL.md
2. **安装位置**：
   - 用户级：`~/.workbuddy/skills/<skill-name>/`
   - 项目级：`<workspace>/.workbuddy/skills/<skill-name>/`
3. **脚本语言**：推荐使用 Python（而非 Shell/JS），确保跨平台兼容
4. **触发词**：在 `description` 字段中明确指定触发条件

### 示例：创建一个 EIAgent 专用技能

```
用户: 帮我创建一个技能，用于自动生成环评报告章节

技能结构:
eia-report-generator/
├── SKILL.md           # 主提示词
├── templates/         # 报告模板
│   ├── air-quality.md
│   ├── noise.md
│   └── ecology.md
└── scripts/
    └── validate_report.py  # 报告校验脚本
```

## 参考文档

- [SKILL.md 格式规范](../INTEGRATION.md)
- [mattpocock/skills 原始仓库](https://github.com/mattpocock/skills)
