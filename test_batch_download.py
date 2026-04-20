#!/usr/bin/env python3
"""
批量下载测试脚本
测试模型批量下载功能是否正常工作
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
        logging.FileHandler(f"batch_download_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath('.'))

try:
    from core.config import load_config, AppConfig
    from core.model_manager import ModelManager
    logger.info("成功导入必要模块")
except Exception as e:
    logger.error(f"导入模块失败: {e}")
    sys.exit(1)

def test_model_download():
    """测试模型下载功能"""
    try:
        # 加载配置
        config = load_config()
        logger.info(f"成功加载配置: {config}")
        
        # 初始化模型管理器
        model_manager = ModelManager(config)
        logger.info("成功初始化模型管理器")
        
        # 获取可用模型
        available_models = model_manager.get_available_models()
        logger.info(f"获取到 {len(available_models)} 个模型")
        for model in available_models:
            logger.info(f"  - {model.name}: available={model.available}, size={model.size}, backend={model.backend}")
        
        # 测试批量下载
        test_models = ["qwen2.5:0.5b", "qwen2.5:1.5b"]
        logger.info(f"开始测试批量下载模型: {test_models}")
        
        for model_name in test_models:
            logger.info(f"开始下载模型: {model_name}")
            
            # 定义进度回调
            def progress_callback(current, total, status):
                if total > 0:
                    progress = (current / total) * 100
                    logger.info(f"  下载进度: {progress:.2f}% - {status}")
                else:
                    logger.info(f"  下载状态: {status}")
            
            # 下载模型
            start_time = time.time()
            success = model_manager.download_model(model_name, progress_callback=progress_callback)
            end_time = time.time()
            
            if success:
                logger.info(f"模型 {model_name} 下载成功，耗时: {end_time - start_time:.2f} 秒")
            else:
                logger.error(f"模型 {model_name} 下载失败")
        
        logger.info("批量下载测试完成")
        
    except Exception as e:
        logger.error(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    logger.info("开始批量下载测试")
    test_model_download()
    logger.info("批量下载测试结束")
