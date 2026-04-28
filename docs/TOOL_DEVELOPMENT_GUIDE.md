# 工具开发指南

## 概述

本文档介绍如何在 LivingTree AI Agent 平台上开发自定义工具。平台采用统一工具层架构，所有工具通过 `ToolRegistry` 注册和管理。

## 核心架构

```
智能体层 (Brain)
      ↓
统一工具层 (ToolRegistry)
      ↓
工具实现层 (Implementations)
```

## 开发步骤

### 1. 创建工具类

所有工具必须继承 `BaseTool` 基类：

```python
from client.src.business.tools import BaseTool, ToolResult

class MyTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="工具描述",
            parameters={
                "param1": {"type": "string", "description": "参数1", "required": True},
                "param2": {"type": "integer", "description": "参数2"}
            },
            returns={
                "result": {"type": "object", "description": "返回结果"}
            }
        )
    
    async def _execute(self, **kwargs) -> ToolResult:
        # 实现工具逻辑
        try:
            result = do_something(kwargs)
            return ToolResult(
                success=True,
                error=None,
                data={"result": result}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                data={}
            )
```

### 2. 注册工具

在 `registrar.py` 中注册工具：

```python
from client.src.business.tools.registrar import register_tool

@register_tool
def register_my_tool():
    from .my_tool import MyTool
    return MyTool()
```

### 3. 工具调用

```python
from client.src.business.tools import ToolRegistry

registry = ToolRegistry.get_instance()

# 发现工具
tools = registry.discover("搜索关键词")

# 执行工具
result = await registry.execute("my_tool", param1="value")
```

## 工具元数据规范

### 参数定义

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | 参数类型：string/integer/number/boolean/object/array |
| description | string | 是 | 参数描述 |
| required | boolean | 否 | 是否必填，默认为 False |
| default | any | 否 | 默认值 |

### 返回定义

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | 返回类型 |
| description | string | 是 | 返回描述 |

## 最佳实践

### 错误处理

```python
async def _execute(self, **kwargs) -> ToolResult:
    try:
        # 参数验证
        if "required_param" not in kwargs:
            return ToolResult(
                success=False,
                error="缺少必填参数",
                data={}
            )
        
        # 业务逻辑
        result = process_data(kwargs)
        
        return ToolResult(
            success=True,
            error=None,
            data={"result": result}
        )
    except ValueError as e:
        return ToolResult(
            success=False,
            error=f"参数错误: {e}",
            data={}
        )
    except Exception as e:
        return ToolResult(
            success=False,
            error=f"执行失败: {e}",
            data={}
        )
```

### 异步执行

工具执行方法必须是异步的：

```python
async def _execute(self, **kwargs) -> ToolResult:
    # 使用 async/await
    result = await async_operation()
    return ToolResult(success=True, data={"result": result})
```

### 依赖管理

```python
class MyTool(BaseTool):
    def __init__(self):
        super().__init__(...)
        self._has_dependency = self._check_dependency()
    
    def _check_dependency(self) -> bool:
        try:
            import external_lib
            return True
        except ImportError:
            return False
    
    async def _execute(self, **kwargs) -> ToolResult:
        if not self._has_dependency:
            return ToolResult(
                success=False,
                error="缺少依赖: external_lib",
                data={"fallback_result": "降级处理结果"}
            )
        # 正常执行
```

## 工具分类

### 数据工具
- 数据获取、处理、转换

### 模型工具
- 调用外部模型（水动力、噪声、大气扩散等）

### 系统工具
- 文件操作、进程管理、配置管理

### AI 工具
- LLM 调用、向量检索、语义分析

## 测试指南

### 单元测试

```python
import pytest
from my_tool import MyTool

@pytest.mark.asyncio
async def test_my_tool():
    tool = MyTool()
    
    # 测试正常调用
    result = await tool.execute(param1="test")
    assert result.success
    assert "result" in result.data
    
    # 测试参数缺失
    result = await tool.execute()
    assert not result.success
```

### 集成测试

```python
from client.src.business.tools import ToolRegistry

@pytest.mark.asyncio
async def test_tool_registry_integration():
    registry = ToolRegistry.get_instance()
    
    # 注册工具
    from my_tool import MyTool
    registry.register(MyTool())
    
    # 发现工具
    tools = registry.discover("my_tool")
    assert len(tools) > 0
    
    # 执行工具
    result = await registry.execute("my_tool", param1="test")
    assert result.success
```

## 版本控制

工具应支持版本管理：

```python
class MyTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="工具描述",
            version="1.0.0",
            ...
        )
```

## 安全注意事项

1. **输入验证**：所有输入必须验证，防止注入攻击
2. **权限控制**：敏感操作需要权限检查
3. **日志审计**：记录所有操作日志
4. **资源限制**：限制执行时间和资源使用

## 性能优化

1. **缓存机制**：对于重复查询使用缓存
2. **异步处理**：耗时操作使用异步执行
3. **批量处理**：支持批量操作减少调用次数
4. **资源池**：复用连接和对象

## 示例工具

参考现有工具实现：
- `web_crawler.py` - 网页爬取工具
- `deep_search.py` - 深度搜索工具
- `hydrodynamic_tool.py` - 水动力模型工具
- `noise_model_tool.py` - 噪声模型工具

## 调试技巧

### 启用调试日志

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 使用监控工具

```python
from client.src.business.tools import ToolMonitor

monitor = ToolMonitor()
record_id = monitor.start_call("my_tool", "agent_1")
# 执行工具
monitor.end_call(record_id, success=True)

# 获取统计信息
stats = monitor.get_statistics("my_tool")
```

## 发布流程

1. 编写工具代码
2. 添加单元测试
3. 在 registrar.py 注册
4. 更新 __init__.py 导出
5. 运行测试验证
6. 部署上线

---

*文档版本: 1.0*  
*最后更新: 2024年*  
*所属项目: LivingTree AI Agent*
