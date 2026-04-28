# LivingTreeAlAgent 开发指南

**文档版本**: v2.0
**更新日期**: 2026-04-28
**状态**: ✅ 核心规范

---

## 一、架构原则

### 三层架构

```
智能体层 (Agent) → 统一工具层 (ToolRegistry) → 工具实现层
```

### 代码位置

| 类型 | 目录 |
|------|------|
| 业务逻辑 | `client/src/business/` |
| UI组件 | `client/src/presentation/` |

### LLM调用规范

```
✅ 必须通过 GlobalModelRouter
❌ 禁止直接调用 Ollama API
```

---

## 二、工具开发规范

### BaseTool 基类

```python
from client.src.business.tools.base_tool import BaseTool, ToolResult

class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    def execute(self, **kwargs) -> ToolResult:
        try:
            # 业务逻辑
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

### ToolResult 返回格式

| 字段 | 说明 |
|------|------|
| success | bool - 执行是否成功 |
| data | Any - 成功时返回数据 |
| error | str - 失败时错误信息 |
| message | str - 可选提示信息 |

---

## 三、极简设计三原则

```
┌─────────────────────────────────────────────┐
│  会话优先    需求澄清    渐进渲染           │
│  (自然语言)  (多问)      (先轮廓后细节)    │
└─────────────────────────────────────────────┘
```

### 自我进化三禁止

```
❌ 禁止预置模板      → ✅ 从样本学习
❌ 禁止硬编码规则    → ✅ 动态知识图谱
❌ 禁止不可变流程    → ✅ 可演进工作流
```

---

## 四、代码规范

### 导入规范

```python
# ✅ 正确
from client.src.business.hermes_agent import HermesAgent
from client.src.business.tools.tool_registry import ToolRegistry

# ❌ 错误 (core/ui 已废弃)
from core.xxx
from ui.xxx
```

### 异步规范

```python
# ✅ PyQt6 异步使用 QThread
class Worker(QThread):
    finished = Signal()
    
    def run(self):
        # 业务逻辑
        self.finished.emit()

# ❌ 错误
import threading
```

### 思考模型处理

```python
# qwen3.6/qwen3.5:4b 是思考模型
result = router.call_model_sync(...)
if hasattr(result, 'thinking'):
    answer = result.thinking  # 答案在 thinking 字段
else:
    answer = result.content
```

---

## 五、Git提交规范

### 提交格式

```
<类型>: <简短描述>

[可选] 详细说明

# 类型: feat/fix/docs/refactor/test/chore
```

### 示例

```
feat: 新增 ProgressiveUIRenderer 组件

- 实现分步式地图生成向导
- 支持坐标转换预览
- 集成到底图服务
```

---

## 六、开发检查清单

### 新功能开发

- [ ] 需求澄清完成
- [ ] 继承 BaseTool
- [ ] 返回 ToolResult
- [ ] 注册到 ToolRegistry
- [ ] 通过 GlobalModelRouter 调用 LLM
- [ ] 单元测试覆盖
- [ ] 文档更新

### UI组件开发

- [ ] 放在 `client/src/presentation/`
- [ ] 使用 PyQt6 组件
- [ ] 遵循现有样式
- [ ] 集成到面板

---

## 七、开源项目借鉴

高匹配度项目逐一借鉴（详见架构指南）：

| 项目 | 匹配度 | 借鉴重点 |
|------|--------|----------|
| EIA报告系统 | 96% | 任务驱动工作流 |
| 内置LLM方案 | 93% | nanoGPT+增量学习 |
| AnyDoc通用文档 | 92% | 通用引擎+领域插件 |
| 渐进式UI | 82% | 会话式+渐进渲染 |

---

**相关文档**: [架构指南](./LIVINGTREE_ARCHITECTURE_GUIDE.md) | [工具层规范](./统一工具层开发指南.md)
