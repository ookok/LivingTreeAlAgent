#!/usr/bin/env python3
"""
测试模型下载功能
使用统一下载中心下载 ggUF 文件，然后通过 Ollama 加载
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
_root = Path(__file__).parent
sys.path.insert(0, str(_root))

from core.model_manager import ModelManager
from core.config import AppConfig


def test_model_download():
    """测试模型下载功能"""
    print("=== 测试模型下载功能 ===")
    
    # 创建配置
    cfg = AppConfig()
    print("配置创建完成")
    
    # 创建模型管理器
    model_manager = ModelManager(cfg)
    print("模型管理器创建完成")
    
    # 获取可用模型
    models = model_manager.get_available_models()
    print(f"获取到 {len(models)} 个模型")
    for model in models:
        print(f"  - {model.name} (可用: {model.available}) - {model.description}")
    
    # 选择一个未下载的模型进行测试
    model_to_download = None
    for model in models:
        if not model.available:
            model_to_download = model
            break
    
    if model_to_download:
        print(f"\n测试下载模型: {model_to_download.name}")
        print(f"模型描述: {model_to_download.description}")
        
        # 定义进度回调
        def progress_callback(current, total, status):
            print(f"  进度: {current}/{total}% - {status}")
        
        # 开始下载
        print("开始下载...")
        import time
        start_time = time.time()
        
        # 定义一个线程来监控下载状态
        import threading
        def monitor_download():
            from core.unified_downloader import get_download_center
            download_center = get_download_center()
            
            while time.time() - start_time < 60:  # 最多监控60秒
                tasks = download_center.get_all_tasks()
                print(f"\n监控: {len(tasks)} 个任务")
                for task in tasks:
                    print(f"  任务: {task.filename}, 状态: {task.status.value}, 进度: {task.progress:.1f}%")
                    if task.error:
                        print(f"  错误: {task.error}")
                time.sleep(5)
        
        # 启动监控线程
        monitor_thread = threading.Thread(target=monitor_download)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # 开始下载
        success = model_manager.download_model(model_to_download.name, progress_callback)
        
        if success:
            print("\n✅ 模型下载成功！")
            # 检查模型是否可用
            models = model_manager.get_available_models()
            for model in models:
                if model.name == model_to_download.name:
                    print(f"  模型 {model.name} 现在可用: {model.available}")
                    break
        else:
            print("\n❌ 模型下载失败！")
        
        # 等待监控线程结束
        monitor_thread.join(timeout=5)
    else:
        print("\n所有模型都已可用，无需下载")
    
    print("\n测试完成")


if __name__ == "__main__":
    test_model_download()
