#!/usr/bin/env python3
"""
检查下载中心的状态
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
_root = Path(__file__).parent
sys.path.insert(0, str(_root))

from core.unified_downloader import get_download_center


def check_download_status():
    """检查下载中心的状态"""
    print("=== 检查下载中心状态 ===")
    
    # 获取下载中心
    download_center = get_download_center()
    
    # 获取所有任务
    tasks = download_center.get_all_tasks()
    print(f"当前有 {len(tasks)} 个下载任务")
    
    for task in tasks:
        print(f"\n任务 ID: {task.id}")
        print(f"  文件名: {task.filename}")
        print(f"  状态: {task.status.value}")
        print(f"  进度: {task.progress:.1f}%")
        print(f"  大小: {task.size_str}")
        print(f"  速度: {task.speed_str}")
        print(f"  剩余时间: {task.eta_str}")
        print(f"  保存路径: {task.save_path}")
        if task.error:
            print(f"  错误: {task.error}")
        print(f"  连接状态: {task.connection_status.value}")
        print(f"  连接信息: {task.connection_info}")


if __name__ == "__main__":
    check_download_status()
