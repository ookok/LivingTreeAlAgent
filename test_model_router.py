#!/usr/bin/env python3
"""
测试 ModelRouter - 多后端 LLM 路由器
"""
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入 ModelRouter
from client.src.business.model_router import (
    ModelRouter, BackendType, BackendConfig,
    get_model_router, setup_default_backends
)

# 配置日志
try:
    from loguru import logger
    logger.remove()
    logger.add(sys.stdout, format='{message}', colorize=False)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger(__name__)

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

# ==================== 测试函数 ====================
@test_case("ModelRouter - 单例模式")
def test_singleton():
    """测试 ModelRouter 单例"""
    router1 = get_model_router()
    router2 = get_model_router()
    
    assert router1 is router2
    return True

@test_case("ModelRouter - 注册 Ollama 后端")
def test_register_ollama():
    """测试注册 Ollama 后端"""
    router = get_model_router()
    
    config = BackendConfig(
        backend_type=BackendType.OLLAMA,
        base_url="http://localhost:11434",
        priority=1,
        enabled=True
    )
    
    result = router.register_backend("ollama_test", config)
    assert result == True
    assert "ollama_test" in router.backends
    
    # 清理
    router.unregister_backend("ollama_test")
    return True

@test_case("ModelRouter - 注册 Shimmy 后端")
def test_register_shimmy():
    """测试注册 Shimmy 后端"""
    router = get_model_router()
    
    config = BackendConfig(
        backend_type=BackendType.SHIMMY,
        base_url="http://localhost:8000",
        priority=2,
        enabled=True
    )
    
    result = router.register_backend("shimmy_test", config)
    assert result == True
    assert "shimmy_test" in router.backends
    
    # 清理
    router.unregister_backend("shimmy_test")
    return True

@test_case("ModelRouter - 注册 OpenAI 后端")
def test_register_openai():
    """测试注册 OpenAI 后端"""
    router = get_model_router()
    
    config = BackendConfig(
        backend_type=BackendType.OPENAI,
        base_url="https://api.openai.com",
        api_key="test-api-key",
        priority=3,
        enabled=False  # 默认禁用
    )
    
    result = router.register_backend("openai_test", config)
    assert result == True
    assert "openai_test" in router.backends
    
    # 清理
    router.unregister_backend("openai_test")
    return True

@test_case("ModelRouter - 注销后端")
def test_unregister():
    """测试注销后端"""
    router = get_model_router()
    
    # 注册
    config = BackendConfig(
        backend_type=BackendType.OLLAMA,
        base_url="http://localhost:11434"
    )
    router.register_backend("test_backend", config)
    assert "test_backend" in router.backends
    
    # 注销
    router.unregister_backend("test_backend")
    assert "test_backend" not in router.backends
    
    return True

@test_case("ModelRouter - 启用/禁用后端")
def test_enable_disable():
    """测试启用/禁用后端"""
    router = get_model_router()
    
    # 注册（默认启用）
    config = BackendConfig(
        backend_type=BackendType.OLLAMA,
        base_url="http://localhost:11434",
        enabled=True
    )
    router.register_backend("test_enable", config)
    
    # 禁用
    router.disable_backend("test_enable")
    assert config.enabled == False
    assert "test_enable" not in router.enabled_backends
    
    # 启用
    router.enable_backend("test_enable")
    assert config.enabled == True
    assert "test_enable" in router.enabled_backends
    
    # 清理
    router.unregister_backend("test_enable")
    return True

@test_case("ModelRouter - 列出后端")
def test_list_backends():
    """测试列出后端"""
    router = get_model_router()
    
    # 注册两个后端
    config1 = BackendConfig(
        backend_type=BackendType.OLLAMA,
        base_url="http://localhost:11434",
        priority=1
    )
    config2 = BackendConfig(
        backend_type=BackendType.SHIMMY,
        base_url="http://localhost:8000",
        priority=2
    )
    
    router.register_backend("list_test_1", config1)
    router.register_backend("list_test_2", config2)
    
    # 列出
    backends = router.list_backends()
    assert len(backends) >= 2
    
    # 清理
    router.unregister_backend("list_test_1")
    router.unregister_backend("list_test_2")
    
    return True

@test_case("ModelRouter - 路由功能")
def test_route():
    """测试路由功能"""
    router = get_model_router()
    
    # 注册两个后端
    config1 = BackendConfig(
        backend_type=BackendType.OLLAMA,
        base_url="http://localhost:11434",
        priority=1,
        enabled=True
    )
    config2 = BackendConfig(
        backend_type=BackendType.SHIMMY,
        base_url="http://localhost:8000",
        priority=2,
        enabled=True
    )
    
    router.register_backend("route_test_1", config1)
    router.register_backend("route_test_2", config2)
    
    # 路由（应该返回优先级最高的）
    routed = router.route("test-model")
    assert routed == "route_test_1"  # 优先级 1
    
    # 禁用优先级最高的
    router.disable_backend("route_test_1")
    routed = router.route("test-model")
    assert routed == "route_test_2"  # 现在应该是这个
    
    # 清理
    router.unregister_backend("route_test_1")
    router.unregister_backend("route_test_2")
    
    return True

@test_case("ModelRouter - 获取统计信息")
def test_get_stats():
    """测试获取统计信息"""
    router = get_model_router()
    
    stats = router.get_stats()
    
    assert "total_backends" in stats
    assert "enabled_backends" in stats
    assert "backends" in stats
    
    return True

@test_case("setup_default_backends - 快速配置")
def test_setup_default():
    """测试快速配置默认后端"""
    router = get_model_router()
    
    # 清空现有后端
    for name in list(router.backends.keys()):
        router.unregister_backend(name)
    
    # 配置默认后端
    setup_default_backends(router)
    
    # 验证
    assert "ollama" in router.backends
    assert "shimmy" in router.backends
    assert len(router.enabled_backends) == 2
    
    # 验证优先级
    assert router.enabled_backends[0] == "ollama"  # 优先级 1
    assert router.enabled_backends[1] == "shimmy"  # 优先级 2
    
    return True

# ==================== 主函数 ====================
def main():
    """运行所有测试"""
    global test_count, passed_count, failed_count
    
    logger.info("=" * 60)
    logger.info("ModelRouter 测试")
    logger.info("=" * 60)
    logger.info("")
    
    # 1. 单例模式测试
    logger.info("[1] 单例模式测试")
    test_singleton()
    logger.info("")
    
    # 2. 注册后端测试
    logger.info("[2] 注册后端测试")
    test_register_ollama()
    test_register_shimmy()
    test_register_openai()
    logger.info("")
    
    # 3. 注销后端测试
    logger.info("[3] 注销后端测试")
    test_unregister()
    logger.info("")
    
    # 4. 启用/禁用测试
    logger.info("[4] 启用/禁用测试")
    test_enable_disable()
    logger.info("")
    
    # 5. 列出后端测试
    logger.info("[5] 列出后端测试")
    test_list_backends()
    logger.info("")
    
    # 6. 路由功能测试
    logger.info("[6] 路由功能测试")
    test_route()
    logger.info("")
    
    # 7. 统计信息测试
    logger.info("[7] 统计信息测试")
    test_get_stats()
    logger.info("")
    
    # 8. 快速配置测试
    logger.info("[8] 快速配置测试")
    test_setup_default()
    logger.info("")
    
    # 输出总结
    logger.info("=" * 60)
    logger.info("测试总结")
    logger.info("=" * 60)
    logger.info(f"总测试数: {test_count}")
    logger.info(f"通过: {passed_count} [PASS]")
    logger.info(f"失败: {failed_count} [FAIL]")
    if test_count > 0:
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
