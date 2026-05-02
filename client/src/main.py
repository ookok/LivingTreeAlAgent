"""
LivingTree AI Agent Platform - 主入口

核心功能：
1. 启动PyQt6 GUI
2. 初始化统一生命系统
3. 提供统一的系统管理
4. 集成增强功能模块

系统架构：
┌─────────────────────────────────────────────────────────────┐
│  L1: 数字生命层 (Digital Life)                             │
│  • 自我意识系统 • 主动推理引擎 • 预测推演系统               │
├─────────────────────────────────────────────────────────────┤
│  L2: 细胞协作层 (Cell Collaboration)                       │
│  • 推理细胞 • 记忆细胞 • 学习细胞 • 感知细胞 • 行动细胞    │
├─────────────────────────────────────────────────────────────┤
│  L3: 系统保障层 (System Safeguard)                        │
│  • 免疫系统 • 代谢系统 • 进化引擎                         │
├─────────────────────────────────────────────────────────────┤
│  L4: 基础设施层 (Infrastructure)                          │
│  • 数据库 • 网络 • 存储 • 计算资源                         │
└─────────────────────────────────────────────────────────────┘
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


async def initialize_living_system():
    """初始化生命系统"""
    logger.info("🧬 初始化生命系统...")
    
    from client.src.business.cell_framework.living_system import get_living_system
    
    living_system = get_living_system()
    await living_system.initialize()
    
    # 设置初始目标
    await living_system.set_goal({
        'name': '系统启动',
        'description': '完成系统初始化并进入稳定运行状态',
        'priority': 'high'
    })
    
    # 启动生命系统
    await living_system.start()
    
    return living_system


def get_system_dashboard(living_system):
    """获取系统仪表盘数据"""
    return living_system.get_dashboard()


def main():
    """主入口函数"""
    logger.info("========================================")
    logger.info("启动 LivingTree AI Agent Platform")
    logger.info("========================================")
    
    try:
        # 创建事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 初始化生命系统
        logger.info("🧬 初始化生命系统...")
        living_system = loop.run_until_complete(initialize_living_system())
        
        # 启动后输出系统状态
        status = living_system.get_system_status()
        logger.info(f"✅ 生命系统初始化完成")
        logger.info(f"   - 状态: {status['state']}")
        logger.info(f"   - 意识水平: {status['consciousness_level']}")
        logger.info(f"   - 健康: {status['health']}")
        logger.info(f"   - 能量: {status['energy']}")
        
        # 获取仪表盘数据
        dashboard = get_system_dashboard(living_system)
        logger.info(f"📊 系统仪表盘:")
        logger.info(f"   - 子系统数量: {len(dashboard['subsystems'])}")
        logger.info(f"   - 活跃目标: {dashboard['system'].get('active_goals', 0)}")
        
        # 启动UI
        logger.info("🖥️ 启动UI界面...")
        try:
            from client.src.presentation import run_app
            run_app()
        except ImportError:
            logger.warning("⚠️ UI模块不可用，将以命令行模式运行")
            # 命令行模式：持续运行生命系统
            loop.run_forever()
        
    except Exception as e:
        logger.error(f"❌ 启动失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()