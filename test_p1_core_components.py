#!/usr/bin/env python3
"""
P1 阶段 - 核心组件单元测试
测试统一架构层的 5 个核心组件
"""
import sys
import os
import time
from typing import Dict, Any

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 配置日志
# 设置 Python 使用 UTF-8 模式（Windows 需要）
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    from loguru import logger
    logger.remove()
    # 不使用 Unicode 字符，避免 Windows 控制台编码问题
    logger.add(sys.stdout, format='{time:HH:mm:ss} | {level: <8} | {message}', colorize=False)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
    logger = logging.getLogger(__name__)

#  Monkey-patch print 函数，避免 Unicode 编码错误
import builtins
_original_print = builtins.print
def safe_print(*args, **kwargs):
    try:
        _original_print(*args, **kwargs)
    except UnicodeEncodeError:
        # 移除 emoji，使用 ASCII 替代
        safe_args = []
        for arg in args:
            if isinstance(arg, str):
                # 替换常见 emoji
                arg = arg.replace('✅', '[PASS]').replace('❌', '[FAIL]').replace('📦', '[TEST]').replace('⚡', '[PERF]')
            safe_args.append(arg)
        _original_print(*safe_args, **kwargs)
builtins.print = safe_print

# ==================== 测试计数 ====================
test_count = 0
passed_count = 0
failed_count = 0

def test_case(name: str):
    """测试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            global test_count, passed_count, failed_count
            test_count += 1
            logger.info(f"[TEST {test_count}] {name}")
            try:
                result = func(*args, **kwargs)
                if result:
                    passed_count += 1
                    logger.info(f"  [PASS] PASSED")
                else:
                    failed_count += 1
                    logger.error(f"  [FAIL] FAILED")
                return result
            except Exception as e:
                failed_count += 1
                logger.error(f"  [FAIL] FAILED: {e}")
                return False
        return wrapper
    return decorator

# ==================== 1. ToolResult 测试 ====================
@test_case("ToolResult - 创建成功结果")
def test_tool_result_success():
    from client.src.business.tools.tool_result import ToolResult
    
    result = ToolResult(success=True, data={"key": "value"}, error=None)
    
    assert result.success == True
    assert result.data == {"key": "value"}
    assert result.error is None
    return True

@test_case("ToolResult - 创建失败结果")
def test_tool_result_failure():
    from client.src.business.tools.tool_result import ToolResult
    
    result = ToolResult(success=False, data=None, error="Error message")
    
    assert result.success == False
    assert result.data is None
    assert result.error == "Error message"
    return True

@test_case("ToolResult - to_dict 方法")
def test_tool_result_to_dict():
    from client.src.business.tools.tool_result import ToolResult
    
    result = ToolResult(success=True, data={"test": 123}, error=None)
    d = result.to_dict()
    
    assert d["success"] == True
    assert d["data"] == {"test": 123}
    assert d["error"] is None
    return True

@test_case("ToolResult - 字符串表示")
def test_tool_result_str():
    from client.src.business.tools.tool_result import ToolResult
    
    result = ToolResult(success=True, data="test", error=None)
    s = str(result)
    
    assert "success" in s.lower()
    return True

# ==================== 2. ToolDefinition 测试 ====================
@test_case("ToolDefinition - 创建工具定义")
def test_tool_definition_create():
    from client.src.business.tools.tool_definition import ToolDefinition
    
    def dummy_func():
        return "test"
    
    tool_def = ToolDefinition(
        name="test_tool",
        description="Test tool",
        func=dummy_func,
        parameters={"param1": "string"},
        returns={"type": "string"}
    )
    
    assert tool_def.name == "test_tool"
    assert tool_def.description == "Test tool"
    assert tool_def.func == dummy_func
    return True

@test_case("ToolDefinition - 验证参数")
def test_tool_definition_validate_params():
    from client.src.business.tools.tool_definition import ToolDefinition
    
    def dummy_func():
        return "test"
    
    tool_def = ToolDefinition(
        name="test_tool",
        description="Test tool",
        func=dummy_func,
        parameters={
            "required_param": {"type": "string", "required": True},
            "optional_param": {"type": "int", "required": False}
        },
        returns={"type": "string"}
    )
    
    # 测试有效参数
    valid = tool_def.validate_parameters({
        "required_param": "value",
        "optional_param": 123
    })
    assert valid == True
    
    # 测试缺少必需参数
    try:
        tool_def.validate_parameters({
            "optional_param": 123
        })
        return False  # 应该抛出异常
    except ValueError:
        return True

@test_case("ToolDefinition - to_dict 方法")
def test_tool_definition_to_dict():
    from client.src.business.tools.tool_definition import ToolDefinition
    
    def dummy_func():
        return "test"
    
    tool_def = ToolDefinition(
        name="test_tool",
        description="Test tool",
        func=dummy_func,
        parameters={},
        returns={"type": "string"}
    )
    
    d = tool_def.to_dict()
    assert d["name"] == "test_tool"
    assert d["description"] == "Test tool"
    assert "func" not in d  # 函数不应该被序列化
    return True

# ==================== 3. BaseTool 测试 ====================
@test_case("BaseTool - 创建具体工具类")
def test_base_tool_create():
    from client.src.business.tools.base_tool import BaseTool
    from client.src.business.tools.tool_result import ToolResult
    
    class TestTool(BaseTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data="test", error=None)
    
    tool = TestTool(name="test_tool", description="Test tool")
    
    assert tool.name == "test_tool"
    assert tool.description == "Test tool"
    assert tool.enabled == True
    return True

@test_case("BaseTool - 执行工具")
def test_base_tool_execute():
    from client.src.business.tools.base_tool import BaseTool
    from client.src.business.tools.tool_result import ToolResult
    
    class TestTool(BaseTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data=kwargs, error=None)
    
    tool = TestTool(name="test_tool", description="Test tool")
    result = tool.execute(param1="value1")
    
    assert result.success == True
    assert result.data["param1"] == "value1"
    return True

@test_case("BaseTool - 启用/禁用")
def test_base_tool_enable_disable():
    from client.src.business.tools.base_tool import BaseTool
    from client.src.business.tools.tool_result import ToolResult
    
    class TestTool(BaseTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data=None, error=None)
    
    tool = TestTool(name="test_tool", description="Test tool")
    
    # 默认启用
    assert tool.enabled == True
    
    # 禁用
    tool.set_enabled(False)
    assert tool.enabled == False
    
    # 启用
    tool.set_enabled(True)
    assert tool.enabled == True
    
    return True

@test_case("BaseTool - 调用 __call__")
def test_base_tool_call():
    from client.src.business.tools.base_tool import BaseTool
    from client.src.business.tools.tool_result import ToolResult
    
    class TestTool(BaseTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data="called", error=None)
    
    tool = TestTool(name="test_tool", description="Test tool")
    result = tool()
    
    assert result.success == True
    assert result.data == "called"
    return True

# ==================== 4. ToolRegistry 测试 ====================
@test_case("ToolRegistry - 单例模式")
def test_tool_registry_singleton():
    from client.src.business.tools.tool_registry import ToolRegistry
    
    registry1 = ToolRegistry.get_instance()
    registry2 = ToolRegistry.get_instance()
    
    assert registry1 is registry2
    return True

@test_case("ToolRegistry - 注册工具")
def test_tool_registry_register():
    from client.src.business.tools.tool_registry import ToolRegistry
    from client.src.business.tools.base_tool import BaseTool
    from client.src.business.tools.tool_result import ToolResult
    
    registry = ToolRegistry.get_instance()
    registry.clear()  # 清空注册表
    
    class TestTool(BaseTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data=None, error=None)
    
    tool = TestTool(name="test_tool", description="Test tool")
    registry.register(tool)
    
    assert registry.has_tool("test_tool")
    assert len(registry.get_all_tools()) == 1
    
    registry.clear()  # 清理
    return True

@test_case("ToolRegistry - 注销工具")
def test_tool_registry_unregister():
    from client.src.business.tools.tool_registry import ToolRegistry
    from client.src.business.tools.base_tool import BaseTool
    from client.src.business.tools.tool_result import ToolResult
    
    registry = ToolRegistry.get_instance()
    registry.clear()
    
    class TestTool(BaseTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data=None, error=None)
    
    tool = TestTool(name="test_tool", description="Test tool")
    registry.register(tool)
    assert registry.has_tool("test_tool") == True
    
    registry.unregister("test_tool")
    assert registry.has_tool("test_tool") == False
    
    registry.clear()
    return True

@test_case("ToolRegistry - 执行工具")
def test_tool_registry_execute():
    from client.src.business.tools.tool_registry import ToolRegistry
    from client.src.business.tools.base_tool import BaseTool
    from client.src.business.tools.tool_result import ToolResult
    
    registry = ToolRegistry.get_instance()
    registry.clear()
    
    class TestTool(BaseTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data=f"Hello, {kwargs.get('name', 'World')}!", error=None)
    
    tool = TestTool(name="greet", description="Greet someone")
    registry.register(tool)
    
    result = registry.execute("greet", name="Alice")
    
    assert result.success == True
    assert result.data == "Hello, Alice!"
    
    registry.clear()
    return True

@test_case("ToolRegistry - 工具不存在")
def test_tool_registry_tool_not_found():
    from client.src.business.tools.tool_registry import ToolRegistry
    
    registry = ToolRegistry.get_instance()
    registry.clear()
    
    result = registry.execute("non_existent_tool")
    
    assert result.success == False
    assert "找不到工具" in result.error
    
    registry.clear()
    return True

@test_case("ToolRegistry - 禁用工具")
def test_tool_registry_disabled_tool():
    from client.src.business.tools.tool_registry import ToolRegistry
    from client.src.business.tools.base_tool import BaseTool
    from client.src.business.tools.tool_result import ToolResult
    
    registry = ToolRegistry.get_instance()
    registry.clear()
    
    class TestTool(BaseTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data=None, error=None)
    
    tool = TestTool(name="test_tool", description="Test tool")
    tool.set_enabled(False)
    registry.register(tool)
    
    result = registry.execute("test_tool")
    
    assert result.success == False
    assert "禁用" in result.error
    
    registry.clear()
    return True

@test_case("ToolRegistry - 搜索工具")
def test_tool_registry_search():
    from client.src.business.tools.tool_registry import ToolRegistry
    from client.src.business.tools.base_tool import BaseTool
    from client.src.business.tools.tool_result import ToolResult
    
    registry = ToolRegistry.get_instance()
    registry.clear()
    
    class WebSearchTool(BaseTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data=None, error=None)
    
    class DocumentParserTool(BaseTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data=None, error=None)
    
    registry.register(WebSearchTool(name="web_search", description="Search the web"))
    registry.register(DocumentParserTool(name="doc_parser", description="Parse documents"))
    
    # 搜索 "web"
    results = registry.search_tools("web")
    assert len(results) >= 1
    assert any(t.name == "web_search" for t in results)
    
    # 搜索 "document"
    results = registry.search_tools("document")
    assert len(results) >= 1
    assert any(t.name == "doc_parser" for t in results)
    
    registry.clear()
    return True

@test_case("ToolRegistry - 获取统计信息")
def test_tool_registry_stats():
    from client.src.business.tools.tool_registry import ToolRegistry
    from client.src.business.tools.base_tool import BaseTool
    from client.src.business.tools.tool_result import ToolResult
    
    registry = ToolRegistry.get_instance()
    registry.clear()
    
    class Tool1(BaseTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data=None, error=None)
    
    class Tool2(BaseTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data=None, error=None)
    
    registry.register(Tool1(name="tool1", description="Tool 1"))
    registry.register(Tool2(name="tool2", description="Tool 2", enabled=False))
    
    stats = registry.get_stats()
    
    assert stats["total"] == 2
    assert stats["enabled"] == 1
    assert stats["disabled"] == 1
    
    registry.clear()
    return True

# ==================== 5. ToolRegistrar 测试 ====================
@test_case("ToolRegistrar - 创建实例")
def test_tool_registrar_create():
    from client.src.business.tools.registrar import ToolRegistrar
    
    registrar = ToolRegistrar()
    
    assert registrar is not None
    assert hasattr(registrar, 'registry')
    return True

@test_case("ToolRegistrar - 扫描工具目录")
def test_tool_registrar_scan():
    from client.src.business.tools.registrar import ToolRegistrar
    
    registrar = ToolRegistrar()
    
    # 扫描 tools 目录
    tool_files = registrar.scan_tool_directory()
    
    assert isinstance(tool_files, list)
    assert len(tool_files) > 0
    assert any("tool.py" in f for f in tool_files)
    
    return True

# ==================== 性能测试 ====================
@test_case("性能 - ToolRegistry 注册 1000 个工具")
def test_performance_register_1000():
    from client.src.business.tools.tool_registry import ToolRegistry
    from client.src.business.tools.base_tool import BaseTool
    from client.src.business.tools.tool_result import ToolResult
    
    registry = ToolRegistry.get_instance()
    registry.clear()
    
    # 创建 1000 个工具
    class PerfTool(BaseTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data=None, error=None)
    
    start_time = time.time()
    
    for i in range(1000):
        tool = PerfTool(name=f"perf_tool_{i}", description=f"Performance tool {i}")
        registry.register(tool)
    
    elapsed = time.time() - start_time
    
    logger.info(f"  ⏱️  注册 1000 个工具耗时: {elapsed:.3f}s")
    assert elapsed < 10.0  # 应该在 10 秒内完成
    
    registry.clear()
    return True

@test_case("性能 - ToolRegistry 查找工具")
def test_performance_search():
    from client.src.business.tools.tool_registry import ToolRegistry
    from client.src.business.tools.base_tool import BaseTool
    from client.src.business.tools.tool_result import ToolResult
    
    registry = ToolRegistry.get_instance()
    registry.clear()
    
    # 注册 100 个工具
    class PerfTool(BaseTool):
        def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data=None, error=None)
    
    for i in range(100):
        tool = PerfTool(name=f"perf_tool_{i}", description=f"Performance tool {i}")
        registry.register(tool)
    
    # 搜索性能
    start_time = time.time()
    
    for _ in range(100):
        results = registry.search_tools("perf")
    
    elapsed = time.time() - start_time
    
    logger.info(f"  ⏱️  100 次搜索耗时: {elapsed:.3f}s")
    assert elapsed < 1.0  # 100 次搜索应该在 1 秒内完成
    
    registry.clear()
    return True

# ==================== 主函数 ====================
def main():
    """运行所有测试"""
    global test_count, passed_count, failed_count
    
    logger.info("=" * 60)
    logger.info("P1 阶段 - 核心组件单元测试")
    logger.info("=" * 60)
    logger.info("")
    
    # 1. ToolResult 测试
    logger.info("[TEST] 1. ToolResult 测试")
    test_tool_result_success()
    test_tool_result_failure()
    test_tool_result_to_dict()
    test_tool_result_str()
    logger.info("")
    
    # 2. ToolDefinition 测试
    logger.info("[TEST] 2. ToolDefinition 测试")
    test_tool_definition_create()
    test_tool_definition_validate_params()
    test_tool_definition_to_dict()
    logger.info("")
    
    # 3. BaseTool 测试
    logger.info("[TEST] 3. BaseTool 测试")
    test_base_tool_create()
    test_base_tool_execute()
    test_base_tool_enable_disable()
    test_base_tool_call()
    logger.info("")
    
    # 4. ToolRegistry 测试
    logger.info("[TEST] 4. ToolRegistry 测试")
    test_tool_registry_singleton()
    test_tool_registry_register()
    test_tool_registry_unregister()
    test_tool_registry_execute()
    test_tool_registry_tool_not_found()
    test_tool_registry_disabled_tool()
    test_tool_registry_search()
    test_tool_registry_stats()
    logger.info("")
    
    # 5. ToolRegistrar 测试
    logger.info("[TEST] 5. ToolRegistrar 测试")
    test_tool_registrar_create()
    test_tool_registrar_scan()
    logger.info("")
    
    # 6. 性能测试
    logger.info("[PERF] 6. 性能测试")
    test_performance_register_1000()
    test_performance_search()
    logger.info("")
    
    # 输出总结
    logger.info("=" * 60)
    logger.info("测试总结")
    logger.info("=" * 60)
    logger.info(f"总测试数: {test_count}")
    logger.info(f"通过: {passed_count} [PASS]")
    logger.info(f"失败: {failed_count} [FAIL]")
    logger.info(f"通过率: {passed_count/test_count*100:.1f}%")
    logger.info("=" * 60)
    
    if failed_count == 0:
        logger.info("[SUCCESS] 所有测试通过！")
        return 0
    else:
        logger.error(f"[FAIL] {failed_count} 个测试失败")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
