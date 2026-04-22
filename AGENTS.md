# LivingTree AI Agent - Knowledge Base

**Generated:** 2026-04-22
**Commit:** ef41a3e
**Project:** 基于 PyQt6 的智能代理开发平台, Python 3.11+, 3402 files

## OVERVIEW

跨模块 AI Agent 桌面应用 (Hermes)。集成分层 Agent 架构、虚拟会议、数字分身、积分经济、P2P 存储、电商系统。2026-04-21 完成三层架构重构 (Presentation/Business/Infrastructure)。

## STRUCTURE

```
root/
├── client/src/             # 重构后主代码 (1562 files)
│   ├── main.py             # 统一入口
│   ├── business/           # 业务逻辑 (151 子模块, ~1350 files)
│   ├── infrastructure/     # 基础设施层 (config/database/network)
│   └── presentation/       # UI 层 (presentation/)
├── core/                   # 旧核心模块 (1354 files, 逐步迁移中)
├── ui/                     # 旧 UI 模块 (173 files, mirrors presentation/)
├── server/                 # FastAPI relay + tracker 服务端 (57 files)
├── app/                    # 独立企业应用
├── packages/               # 共享包 (living_tree_naming 法典)
├── scripts/                # 启动/部署脚本
└── main.py                 # 根入口: python main.py [client|relay|tracker|app|all]
```

## WHERE TO LOOK

| Task | Location |
|------|----------|
| UI 功能面板 | `client/src/presentation/panels/` (90+ panels) |
| 业务逻辑模块 | `client/src/business/` → 按功能域划分 |
| 底层基础设施 | `client/src/infrastructure/{config,database,network}/` |
| 旧代码 (仍可能在使用) | `core/` + `ui/` (逐步迁移) |
| 服务端 API | `server/relay_server/` |
| 迁移追踪 | `README.md` 重构前/后对比表 |
| 模型管理 | `core/model_hub/`, `core/model_store/` |
| 技能系统 | `packages/` + `client/src/business/skill_evolution/` |

## CONVENTIONS

- 新代码写 `client/src/business/`, 旧代码保留在 `core/`
- UI 面板继承 `client/src/presentation/` 中的基础类
- Import: `from client.src.business.{domain}.{module}` (重构后)
- `core/__init__.py` 仍导出旧路径: `HermesAgent`, `OllamaClient`, `SessionDB`, `MemoryManager`, `ToolRegistry`
- 每个业务模块通常有 `__init__.py` 做入口 + 多个实现文件
- 大型模块使用 `__init__.py` 聚合导出 (99k+ 行的 `personal_mode`, `universal_asset_ecosystem` 等)

## ANTI-PATTERNS

- ❌ 不要在 `core/` 中新增模块, 统一用 `client/src/business/`
- ❌ 旧 import 路径 (`from core.xxx`) 逐步被新路径替换中, 两系统并存
- ❌ 不要大文件 (>60k 行) 硬读, 模块内部用子文件拆分
- ❌ `core/` 中的大 `__init__.py` (99k/74k/70k 行) 是单文件上帝对象, 需渐进重构

## COMMANDS

```bash
# 启动
python main.py client           # 桌面客户端
python main.py relay            # 中继服务器
python main.py tracker          # 追踪服务器
python main.py all              # 全部启动
python run.bat                  # Windows 快速启动

# 安装
pip install -e ./client
pip install -e ./server/relay_server
pip install -e ./app

# 项目配置
pyproject.toml                  # 项目级配置 (setuptools, livingtree CLI)
pytest.ini                      # 测试配置
```

## NOTES

- `client/src/business/` 有 151 个业务子模块 (living_tree_ai, credit_economy, virtual_avatar_social, smart_deploy 等)
- `client/src/presentation/panels/` 下有 90+ UI 面板, 多数在 `legacy ui/` 也有副本
- 代码库有大量单文件 >25k 行的模块 (上帝对象模式)
- 根目录有大量未使用的 `test_*.py` 文件 (约 80 个), 实际测试在 `tests/` 和 `test_cloud/`
