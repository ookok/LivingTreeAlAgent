# Agent Skills 集成模块
# ====================

# 核心模块
agent_skills/
├── __init__.py
├── skill_registry.py        # 技能注册中心
├── skill_loader.py          # Markdown 技能加载器
├── skill_executor.py        # 技能执行引擎
├── slash_commands.py        # 斜杠命令系统
├── context_aware.py         # 上下文感知加载
└── workflows/               # 工作流技能
    ├── __init__.py
    ├── spec_driven.py       # Spec 驱动开发
    ├── test_driven.py       # 测试驱动开发
    ├── code_review.py       # 代码审查
    └── security.py          # 安全加固
