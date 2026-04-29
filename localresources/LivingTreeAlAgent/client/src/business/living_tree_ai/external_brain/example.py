"""
ExternalBrain 使用示例
=====================

演示如何使用多通道回退机制调用外部AI服务

Author: LivingTreeAI Community
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_basic_usage():
    """
    基础用法：调用外脑服务
    """
    from core.living_tree_ai import (
        get_channel_manager,
        get_network_diagnoser,
        get_offline_queue,
    )

    # 获取组件
    channel_manager = get_channel_manager()
    diagnoser = get_network_diagnoser()
    offline_queue = get_offline_queue()

    # 设置关联
    channel_manager.set_diagnoser(diagnoser)
    channel_manager.set_offline_queue(offline_queue)

    # 启动组件
    await channel_manager.start()

    # 执行诊断
    logger.info("=== 网络诊断 ===")
    report = await diagnoser.diagnose()
    logger.info(f"可用服务: {report.get_available_services()}")
    logger.info(f"最佳服务: {report.get_best_service()}")

    # 调用外脑（示例：调用DeepSeek）
    logger.info("\n=== 调用外脑 ===")
    result = await channel_manager.execute(
        task_name="deepseek_chat",
        target_url="https://api.deepseek.com/v1/chat/completions",
        request_data={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "你好"}],
        },
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )

    logger.info(f"执行结果: success={result.success}, channel={result.channel_type.value}")
    if result.success:
        logger.info(f"响应数据: {result.data}")
    else:
        logger.info(f"错误: {result.error}")

    # 停止
    await channel_manager.stop()


async def example_with_proxy():
    """
    示例：配置用户代理
    """
    from core.living_tree_ai import (
        get_channel_manager,
        UserProxyConfig,
    )

    channel_manager = get_channel_manager()

    # 配置代理（需用户显式授权）
    proxy_config = UserProxyConfig(
        enabled=True,
        proxy_type="http",
        proxy_host="192.168.1.100",
        proxy_port=7890,
        proxy_user="myuser",  # 可选
        proxy_pass="mypass",  # 可选
    )

    channel_manager.set_user_proxy(proxy_config)
    logger.info("代理配置已更新")

    # 后续调用将自动使用代理


async def example_with_api_key():
    """
    示例：配置API Key
    """
    from core.living_tree_ai import (
        get_channel_manager,
        APIKeyConfig,
    )

    channel_manager = get_channel_manager()

    # 配置DeepSeek API Key
    api_config = APIKeyConfig(
        service_name="deepseek",
        api_key="your-api-key-here",
        base_url="https://api.deepseek.com/v1/chat/completions",
        enabled=True,
    )

    channel_manager.set_api_key(api_config)
    logger.info("API Key配置已更新")


async def example_with_local_llm():
    """
    示例：配置本地LLM降级
    """
    from core.living_tree_ai import (
        get_channel_manager,
        LocalLLMConfig,
    )

    channel_manager = get_channel_manager()

    # 配置Ollama
    llm_config = LocalLLMConfig(
        enabled=True,
        endpoint="http://localhost:11434",
        model="llama3.2",
        timeout=120.0,
    )

    channel_manager.set_local_llm_config(llm_config)
    logger.info("本地LLM配置已更新")


async def example_offline_queue():
    """
    示例：管理离线队列
    """
    from core.living_tree_ai import get_offline_queue

    queue = get_offline_queue()

    # 查看队列统计
    stats = queue.get_stats()
    logger.info(f"队列统计: {stats}")

    # 获取待处理任务
    pending = await queue.get_pending_tasks()
    logger.info(f"待处理任务数: {len(pending)}")

    # 获取所有任务
    all_tasks = await queue.get_all_tasks()
    for task in all_tasks:
        logger.info(f"任务: {task.task_name} - {task.status.value}")


async def example_ui_panel():
    """
    示例：在PyQt6中使用UI面板
    """
    from PyQt6.QtWidgets import QApplication
    from core.living_tree_ai import create_external_brain_panel

    app = QApplication([])

    # 创建面板
    panel = create_external_brain_panel()
    panel.show()

    app.exec()


if __name__ == "__main__":
    # 运行基础示例
    asyncio.run(example_basic_usage())