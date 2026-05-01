"""
LivingTree AI Agent Platform - 主入口

核心功能：
1. 启动PyQt6 GUI
2. 初始化所有AI子系统
3. 提供统一的系统管理
4. 集成增强功能模块

系统架构：
- 大脑启发记忆系统 (brain_memory)
- 自修复容错系统 (self_healing)
- 持续学习系统 (continual_learning)
- 认知推理系统 (cognitive_reasoning)
- 自我意识系统 (self_awareness)
- MCP服务管理 (mcp_service)
- API网关 (api_gateway)
- 深度集成层 (integration_layer)
- 工具调用增强 (tool_enhancement)
- 对话管理优化 (dialogue_optimization)
- 插件系统扩展 (plugin_extension)
- 可观测性增强 (observability_enhancement)
- 核心UI模块 (presentation/core)
"""

import sys
import logging
import os
import asyncio

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('livingtree.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def initialize_services():
    """异步初始化所有服务"""
    logger.info("初始化服务集成层...")
    
    from client.src.business.integration_layer import ServiceIntegration
    service_integration = ServiceIntegration()
    
    await service_integration.initialize()
    
    dashboard_data = service_integration.get_dashboard_data()
    logger.info(f"服务状态: {dashboard_data['services']}")
    logger.info(f"系统指标: {dashboard_data['metrics']}")
    
    return service_integration


def main():
    """主入口函数"""
    logger.info("========================================")
    logger.info("启动 LivingTree AI Agent Platform")
    logger.info("========================================")
    
    try:
        # 初始化服务集成层（包含所有增强功能）
        logger.info("初始化服务集成层...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        service_integration = loop.run_until_complete(initialize_services())
        
        # 初始化系统管理器（包含深度集成层）
        logger.info("初始化系统管理器...")
        from client.src.business.system_integration import get_system_manager
        system_manager = get_system_manager()
        system_manager.initialize()
        
        # 检查系统状态
        status = system_manager.get_status()
        active_count = len(system_manager.get_active_subsystems())
        logger.info(f"系统初始化完成，活跃子系统: {active_count}")
        
        # 启动UI（使用新的核心模块）
        logger.info("启动UI界面...")
        from client.src.presentation import run_app
        run_app()
        
    except Exception as e:
        logger.error(f"启动失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()