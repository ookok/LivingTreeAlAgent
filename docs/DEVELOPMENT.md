# 开发手册

## 1. 环境搭建

### 要求
- Python 3.14
- Git
- Windows Terminal (自动安装)

### 开发环境

```bash
git clone https://github.com/ookok/LivingTreeAlAgent.git
cd LivingTreeAlAgent
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux
pip install -e .
```

### 调试启动

```bash
python debug_tui.py           # 直接启动 TUI
python relay_server.py --port 8888  # 启动中继服务器
```

## 2. 添加新 LLM Provider

1. 在 `config/settings.py` 的 `ModelConfig` 中添加字段
2. 在 `dna/dual_consciousness.py` 中注册 provider
3. 在 `integration/hub.py` 中传递配置
4. 存储 API key 到加密 vault

## 3. 添加新 Tool

```python
from livingtree.core.unified_registry import get_registry, RegistryTool
registry = get_registry()
registry.register_tool(RegistryTool(
    name="my_tool", description="新工具描述",
    category="my_category", formula="x^2 + y^2 = R^2",
    params={"x": "参数1", "y": "参数2"},
    source="custom",
))
```

## 4. 添加新命令

在 `livingtree/tui/td/widgets/conversation.py` 中：

1. 在 `slash_command()` 方法的命令列表中添加
2. 在 `_handle_livingtree_command()` 中添加处理逻辑
3. 在 `livingtree/tui/i18n.py` 中添加中英文翻译

## 5. 架构约定

### 全局注册表

所有工具/技能/角色通过 `UnifiedRegistry.instance()` 统一管理，不再创建新的全局单例。

### 异步持久化

热路径保存使用 `save_json(path, data)` 而非 `path.write_text()`。

### 任务防护

长时间运行的任务使用 `TaskGuard.run()` 包装：

```python
from livingtree.core.task_guard import get_guard
result = await get_guard().run("task_type", coroutine, timeout=120)
```

### 错误处理

所有模块级错误通过 `ErrorInterceptor` 捕获，写入 `.livingtree/errors.json`。

## 6. 测试

```bash
python -m pytest tests/
python -m livingtree test
```

## 7. 发布流程

```bash
git add -A
git commit -m "feat: description"
git push origin master
# 自动版本检测 → 客户端启动时提示更新
```
