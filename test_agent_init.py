#!/usr/bin/env python3
"""
Agent初始化测试脚本
测试Agent初始化功能是否正常工作
"""

import os
import sys
import time
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"agent_init_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath('.'))

try:
    from core.config import load_config, AppConfig
    from client.src.business.agent import HermesAgent, AgentCallbacks
    logger.info("成功导入必要模块")
except Exception as e:
    logger.error(f"导入模块失败: {e}")
    sys.exit(1)

def test_agent_init():
    """测试Agent初始化功能"""
    try:
        # 加载配置
        config = load_config()
        logger.info(f"成功加载配置: {config}")
        
        # 定义回调函数
        def stream_delta(delta: str):
            logger.info(f"收到流式delta: {delta}")
        
        def thinking(text: str):
            logger.info(f"Agent思考: {text}")
        
        def tool_start(tool_name: str, args: str):
            logger.info(f"工具开始: {tool_name}, 参数: {args}")
        
        def tool_result(tool_name: str, result: str, success: bool):
            logger.info(f"工具结果: {tool_name}, 成功: {success}, 结果: {result}")
        
        # 创建回调对象
        cbs = AgentCallbacks(
            stream_delta=stream_delta,
            thinking=thinking,
            tool_start=tool_start,
            tool_result=tool_result,
        )
        logger.info("成功创建回调对象")
        
        # 初始化Agent
        logger.info("开始初始化Hermes Agent")
        start_time = time.time()
        agent = HermesAgent(
            config=config,
            session_id="test_session",
            callbacks=cbs,
        )
        end_time = time.time()
        logger.info(f"Agent初始化完成，耗时: {end_time - start_time:.2f} 秒")
        
        # 测试Agent是否可用
        logger.info("测试Agent是否可用")
        try:
            # 发送一个简单的测试消息
            response = agent.send_message("你好，Hermes")
            logger.info(f"收到Agent响应: {response}")
        except Exception as e:
            logger.error(f"测试Agent消息发送失败: {e}")
        
        logger.info("Agent初始化测试完成")
        
    except Exception as e:
        logger.error(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    logger.info("开始Agent初始化测试")
    test_agent_init()
    logger.info("Agent初始化测试结束")
