"""
虚拟云盘功能测试

测试虚拟云盘引擎的核心功能，包括：
- 多驱动管理
- 虚拟路径解析
- 额度感知调度
- 大文件上传下载
- 任务队列管理
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from core.virtual_cloud_engine import get_virtual_cloud_engine, TransferTask, TaskStatus
from core.cloud_drivers.aliyun_driver import AliDriver
from core.cloud_drivers.base_driver import DriverConfig, CloudProvider

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_virtual_cloud_basic():
    """测试虚拟云盘基本功能"""
    logger.info("=== 测试虚拟云盘基本功能 ===")
    
    # 获取虚拟云盘引擎
    engine = get_virtual_cloud_engine()
    
    # 测试 1: 列出挂载点
    logger.info("\n测试 1: 列出挂载点")
    mount_points = engine.get_mount_points()
    logger.info(f"挂载点: {mount_points}")
    
    # 测试 2: 测试虚拟路径解析
    logger.info("\n测试 2: 测试虚拟路径解析")
    test_paths = [
        "/clouds/aliyun/test/file.txt",
        "/clouds/onedrive/docs",
        "/"
    ]
    
    for path in test_paths:
        driver_name, driver = engine.resolve_driver(path)
        logger.info(f"路径: {path} -> 驱动: {driver_name}")
    
    # 测试 3: 测试缓存功能
    logger.info("\n测试 3: 测试缓存功能")
    cache_stats = engine.get_cache_stats()
    logger.info(f"缓存统计: {cache_stats}")
    
    # 测试 4: 测试任务管理
    logger.info("\n测试 4: 测试任务管理")
    # 创建一个测试文件
    test_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    test_file.write("This is a test file for virtual cloud engine")
    test_file.close()
    
    try:
        # 提交上传任务
        file_size = os.path.getsize(test_file.name)
        task_id = await engine.submit_upload(
            source_path=test_file.name,
            virtual_path="/clouds/aliyun/test/test_file.txt",
            size=file_size
        )
        logger.info(f"提交上传任务成功，任务 ID: {task_id}")
        
        # 获取任务信息
        task = engine.get_task(task_id)
        logger.info(f"任务信息: {task}")
        
        # 列出所有任务
        tasks = engine.list_tasks()
        logger.info(f"所有任务: {len(tasks)} 个")
        
    finally:
        # 清理测试文件
        if os.path.exists(test_file.name):
            os.unlink(test_file.name)
    
    logger.info("\n虚拟云盘基本功能测试完成！")


async def test_large_file_handling():
    """测试大文件处理能力"""
    logger.info("\n=== 测试大文件处理能力 ===")
    
    # 获取虚拟云盘引擎
    engine = get_virtual_cloud_engine()
    
    # 创建一个较大的测试文件（100MB）
    test_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.bin', delete=False)
    try:
        # 写入100MB数据
        chunk_size = 1024 * 1024  # 1MB
        for i in range(100):
            test_file.write(b'x' * chunk_size)
        test_file.close()
        
        file_size = os.path.getsize(test_file.name)
        logger.info(f"创建测试文件成功，大小: {file_size / (1024*1024):.2f} MB")
        
        # 测试上传大文件
        logger.info("测试上传大文件...")
        task_id = await engine.submit_upload(
            source_path=test_file.name,
            virtual_path="/clouds/aliyun/test/large_file.bin",
            size=file_size
        )
        logger.info(f"提交大文件上传任务成功，任务 ID: {task_id}")
        
        # 模拟任务执行
        # 注意：实际环境中需要启动任务处理器
        logger.info("大文件上传任务已提交，等待执行...")
        
    finally:
        # 清理测试文件
        if os.path.exists(test_file.name):
            os.unlink(test_file.name)
    
    logger.info("大文件处理能力测试完成！")


async def test_cloud_quota():
    """测试云盘配额获取"""
    logger.info("\n=== 测试云盘配额获取 ===")
    
    # 获取虚拟云盘引擎
    engine = get_virtual_cloud_engine()
    
    try:
        # 获取所有驱动的配额
        quotas = await engine.get_all_quotas()
        logger.info(f"云盘配额: {quotas}")
        
        # 计算总配额
        total_free = 0
        total_used = 0
        total_total = 0
        
        for name, quota in quotas.items():
            total_free += quota.free
            total_used += quota.used
            total_total += quota.total
            logger.info(f"{name}: 总容量 {quota.total/(1024**3):.2f} GB, 已用 {quota.used/(1024**3):.2f} GB, 剩余 {quota.free/(1024**3):.2f} GB")
        
        logger.info(f"总计: 总容量 {total_total/(1024**3):.2f} GB, 已用 {total_used/(1024**3):.2f} GB, 剩余 {total_free/(1024**3):.2f} GB")
        
    except Exception as e:
        logger.error(f"获取云盘配额失败: {e}")
    
    logger.info("云盘配额获取测试完成！")


async def test_driver_selection():
    """测试驱动选择策略"""
    logger.info("\n=== 测试驱动选择策略 ===")
    
    # 获取虚拟云盘引擎
    engine = get_virtual_cloud_engine()
    
    try:
        # 测试上传驱动选择
        upload_driver = await engine._select_driver_for_upload()
        logger.info(f"选择的上传驱动: {upload_driver}")
        
        # 测试下载驱动选择
        download_driver = await engine._select_driver_for_download()
        logger.info(f"选择的下载驱动: {download_driver}")
        
    except Exception as e:
        logger.error(f"测试驱动选择失败: {e}")
    
    logger.info("驱动选择策略测试完成！")


async def main():
    """主测试函数"""
    logger.info("开始测试虚拟云盘功能...")
    
    try:
        # 测试基本功能
        await test_virtual_cloud_basic()
        
        # 测试大文件处理
        await test_large_file_handling()
        
        # 测试云盘配额
        await test_cloud_quota()
        
        # 测试驱动选择
        await test_driver_selection()
        
        logger.info("\n所有虚拟云盘功能测试完成！")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
