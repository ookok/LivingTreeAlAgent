"""
简化的 browser-use 测试

直接测试 browser-use 适配器，避免导入冲突
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


async def test_browser_use_direct():
    """直接测试 browser-use"""
    logger.info("=== 直接测试 browser-use ===")
    
    try:
        # 直接导入 browser-use
        from browser_use import Agent, Browser
        from browser_use import ChatBrowserUse
        
        # 初始化浏览器
        logger.info("初始化浏览器...")
        browser = Browser(
            use_cloud=False
        )
        
        # 初始化代理
        logger.info("初始化代理...")
        agent = Agent(
            task="",
            llm=ChatBrowserUse(),
            browser=browser,
            max_steps=50
        )
        
        # 测试任务
        test_tasks = [
            "导航到 https://example.com",
            "导航到 https://example.com 并提取页面内容",
            "在 google 上搜索 'browser automation' 并返回前 3 个结果",
            "导航到 https://example.com 并截取整个页面的截图，保存为 test_screenshot.png"
        ]
        
        for task in test_tasks:
            logger.info(f"\n执行任务: {task}")
            agent.task = task
            result = await agent.run()
            
            logger.info(f"任务执行结果:")
            logger.info(f"  成功: {result.is_successful()}")
            logger.info(f"  结果: {result.final_result()}")
            logger.info(f"  步骤数: {len(result.history)}")
        
        # 关闭浏览器
        logger.info("\n关闭浏览器...")
        await browser.close()
        
        logger.info("\nbrowser-use 直接测试完成！")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主测试函数"""
    logger.info("开始测试 browser-use...")
    
    try:
        # 测试 browser-use
        await test_browser_use_direct()
        
        logger.info("\n所有 browser-use 测试完成！")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
