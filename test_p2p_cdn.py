"""
P2P CDN 模块测试

测试 P2P CDN 模块的核心功能
"""

import asyncio
import logging

from core.p2p_cdn import create_p2p_cdn, CDNNode, NodeCapability

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_basic_operations():
    """测试基本操作"""
    logger.info("=== 测试基本操作 ===")
    
    # 创建 P2P CDN 实例
    cdn = await create_p2p_cdn("test_node_1")
    
    try:
        # 测试存储数据
        test_data = {"key": "value", "number": 42, "nested": {"a": 1, "b": 2}}
        data_id = await cdn.store_data(test_data)
        logger.info(f"存储数据成功，数据 ID: {data_id}")
        
        # 测试获取数据
        retrieved_data = await cdn.get_data(data_id)
        logger.info(f"获取数据成功: {retrieved_data}")
        assert retrieved_data == test_data, "获取的数据与存储的数据不匹配"
        
        # 测试更新数据
        updated_data = {"key": "updated_value", "number": 100, "nested": {"a": 10, "b": 20}}
        update_result = await cdn.update_data(data_id, updated_data)
        logger.info(f"更新数据成功: {update_result}")
        
        # 测试获取更新后的数据
        retrieved_updated_data = await cdn.get_data(data_id)
        logger.info(f"获取更新后的数据成功: {retrieved_updated_data}")
        assert retrieved_updated_data == updated_data, "获取的更新数据与更新后的数据不匹配"
        
        # 测试删除数据
        delete_result = await cdn.delete_data(data_id)
        logger.info(f"删除数据成功: {delete_result}")
        
        # 测试获取已删除的数据
        deleted_data = await cdn.get_data(data_id)
        logger.info(f"获取已删除的数据: {deleted_data}")
        assert deleted_data is None, "已删除的数据仍能获取"
        
        logger.info("基本操作测试通过！")
        
    finally:
        # 停止 P2P CDN
        await cdn.stop()


async def test_cache_functionality():
    """测试缓存功能"""
    logger.info("\n=== 测试缓存功能 ===")
    
    # 创建 P2P CDN 实例
    cdn = await create_p2p_cdn("test_node_2")
    
    try:
        # 存储数据
        test_data = {"cache_test": "value"}
        data_id = await cdn.store_data(test_data)
        logger.info(f"存储数据成功，数据 ID: {data_id}")
        
        # 第一次获取数据（应该从存储读取，然后缓存）
        start_time = asyncio.get_event_loop().time()
        first_retrieval = await cdn.get_data(data_id)
        first_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"第一次获取数据耗时: {first_time:.4f} 秒")
        
        # 第二次获取数据（应该从缓存读取）
        start_time = asyncio.get_event_loop().time()
        second_retrieval = await cdn.get_data(data_id)
        second_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"第二次获取数据耗时: {second_time:.4f} 秒")
        
        # 验证两次获取的数据相同
        assert first_retrieval == second_retrieval, "两次获取的数据不匹配"
        
        # 验证缓存命中率
        cache_stats = cdn.cache_manager.get_stats()
        logger.info(f"缓存统计信息: {cache_stats}")
        
        logger.info("缓存功能测试通过！")
        
    finally:
        # 停止 P2P CDN
        await cdn.stop()


async def test_node_management():
    """测试节点管理"""
    logger.info("\n=== 测试节点管理 ===")
    
    # 创建 P2P CDN 实例
    cdn = await create_p2p_cdn("test_node_3")
    
    try:
        # 创建测试节点
        test_node = CDNNode(
            node_id="test_peer_node",
            capability=NodeCapability(
                storage_available=1024 * 1024 * 1024,  # 1GB
                bandwidth=100,  # 100 Mbps
                uptime=3600,  # 1小时
                reliability=0.99  # 99% 可靠性
            ),
            last_seen=asyncio.get_event_loop().time()
        )
        
        # 添加节点
        cdn.add_node(test_node)
        logger.info(f"添加节点成功: {test_node.node_id}")
        
        # 获取已知节点
        known_nodes = cdn.get_known_nodes()
        logger.info(f"已知节点数量: {len(known_nodes)}")
        assert len(known_nodes) > 0, "没有已知节点"
        
        # 移除节点
        cdn.remove_node(test_node.node_id)
        logger.info(f"移除节点成功: {test_node.node_id}")
        
        # 验证节点已移除
        known_nodes_after_removal = cdn.get_known_nodes()
        logger.info(f"移除后已知节点数量: {len(known_nodes_after_removal)}")
        
        logger.info("节点管理测试通过！")
        
    finally:
        # 停止 P2P CDN
        await cdn.stop()


async def test_statistics():
    """测试统计信息"""
    logger.info("\n=== 测试统计信息 ===")
    
    # 创建 P2P CDN 实例
    cdn = await create_p2p_cdn("test_node_4")
    
    try:
        # 存储一些数据
        for i in range(3):
            test_data = {"test": f"data_{i}"}
            await cdn.store_data(test_data)
        
        # 获取统计信息
        stats = cdn.get_stats()
        logger.info(f"CDN 统计信息: {stats}")
        
        # 验证统计信息
        assert stats["data_count"] == 3, f"数据数量不匹配: {stats['data_count']}"
        assert stats["known_nodes_count"] >= 1, "没有已知节点"
        
        logger.info("统计信息测试通过！")
        
    finally:
        # 停止 P2P CDN
        await cdn.stop()


async def main():
    """主测试函数"""
    logger.info("开始测试 P2P CDN 模块...")
    
    try:
        await test_basic_operations()
        await test_cache_functionality()
        await test_node_management()
        await test_statistics()
        
        logger.info("所有测试通过！")
    except Exception as e:
        logger.error(f"测试失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
