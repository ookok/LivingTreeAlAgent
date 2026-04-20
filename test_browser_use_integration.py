"""
browser-use 集成测试

测试 browser-use 适配器的基本功能
"""

import asyncio
import logging
import sys
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_browser_use_adapter():
    """测试 browser-use 适配器"""
    logger.info("=== 测试 browser-use 适配器 ===")
    
    try:
        # 导入 browser-use 适配器
        from core.living_tree_ai.browser_gateway.browser_use_adapter import create_browser_use_adapter
        
        # 创建适配器
        adapter = create_browser_use_adapter()
        
        # 初始化
        logger.info("初始化 browser-use 适配器...")
        initialized = await adapter.initialize()
        logger.info(f"初始化结果: {initialized}")
        
        if not initialized:
            logger.error("初始化失败，测试结束")
            return
        
        # 测试导航功能
        logger.info("\n测试导航功能...")
        result = await adapter.navigate("https://example.com")
        logger.info(f"导航结果: {result}")
        
        # 测试内容提取
        logger.info("\n测试内容提取...")
        result = await adapter.extract_content("https://example.com")
        logger.info(f"内容提取结果: {result}")
        
        # 测试搜索功能
        logger.info("\n测试搜索功能...")
        result = await adapter.search("browser automation", "google")
        logger.info(f"搜索结果: {result}")
        
        # 测试截图功能
        logger.info("\n测试截图功能...")
        result = await adapter.screenshot("https://example.com", "example_screenshot.png")
        logger.info(f"截图结果: {result}")
        
        # 测试表单填写（使用示例表单）
        logger.info("\n测试表单填写...")
        form_data = {
            "q": "browser-use test"
        }
        result = await adapter.fill_form("https://www.google.com", form_data)
        logger.info(f"表单填写结果: {result}")
        
        # 测试执行自定义任务
        logger.info("\n测试执行自定义任务...")
        task = "导航到 https://github.com 并提取页面标题"
        result = await adapter.execute_task(task)
        logger.info(f"自定义任务执行结果: {result}")
        
        # 关闭浏览器
        logger.info("\n关闭浏览器...")
        await adapter.close()
        
        logger.info("\nbrowser-use 适配器测试完成！")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_browser_gateway_integration():
    """测试浏览器网关集成"""
    logger.info("\n=== 测试浏览器网关集成 ===")
    
    try:
        # 导入浏览器网关
        from core.living_tree_ai.browser_gateway.gateway import create_browser_gateway
        
        # 创建浏览器网关
        gateway = create_browser_gateway()
        
        # 测试 RPC 方法
        logger.info("测试 browser-use RPC 方法...")
        
        # 测试执行任务
        task = "导航到 https://example.com 并提取页面内容"
        result = await gateway.rpc.handle_request_async({
            "method": "browserUseExecute",
            "params": {"task": task}
        })
        logger.info(f"RPC 执行结果: {result}")
        
        # 测试导航
        result = await gateway.rpc.handle_request_async({
            "method": "browserUseNavigate",
            "params": {"url": "https://example.com"}
        })
        logger.info(f"RPC 导航结果: {result}")
        
        logger.info("浏览器网关集成测试完成！")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主测试函数"""
    logger.info("开始测试 browser-use 集成...")
    
    try:
        # 测试浏览器适配器
        await test_browser_use_adapter()
        
        # 测试浏览器网关集成
        await test_browser_gateway_integration()
        
        logger.info("\n所有 browser-use 集成测试完成！")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
