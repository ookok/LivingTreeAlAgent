"""
P2P CDN 直接测试

直接测试 P2P CDN 模块的功能，不通过 LivingTreeAI 节点
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


async def test_cdn_direct():
    """直接测试 P2P CDN 功能"""
    logger.info("=== 测试 P2P CDN 直接功能 ===")
    
    # 创建 P2P CDN 实例
    cdn = await create_p2p_cdn("test_node")
    
    try:
        # 测试 1: 存储数据
        logger.info("\n测试 1: 存储数据")
        test_data = {
            "name": "测试数据",
            "type": "knowledge",
            "content": "这是一个测试数据，用于验证 P2P CDN 功能",
            "tags": ["test", "cdn"]
        }
        data_id = await cdn.store_data(test_data)
        assert data_id is not None, "存储数据失败"
        logger.info(f"存储数据成功，数据 ID: {data_id}")
        
        # 测试 2: 获取数据
        logger.info("\n测试 2: 获取数据")
        retrieved_data = await cdn.get_data(data_id)
        assert retrieved_data is not None, "获取数据失败"
        assert retrieved_data["name"] == test_data["name"], "获取的数据与存储的数据不匹配"
        logger.info("获取数据成功，数据内容匹配")
        
        # 测试 3: 更新数据
        logger.info("\n测试 3: 更新数据")
        updated_data = {
            "name": "更新后的测试数据",
            "type": "knowledge",
            "content": "这是更新后的测试数据，用于验证 P2P CDN 功能",
            "tags": ["test", "cdn", "updated"]
        }
        update_result = await cdn.update_data(data_id, updated_data)
        assert update_result, "更新数据失败"
        
        # 验证更新后的数据
        updated_retrieved_data = await cdn.get_data(data_id)
        assert updated_retrieved_data["name"] == updated_data["name"], "更新后的数据与预期不匹配"
        logger.info("更新数据成功，数据内容已更新")
        
        # 测试 4: 添加节点
        logger.info("\n测试 4: 添加节点")
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
        cdn.add_node(test_node)
        logger.info("添加节点成功")
        
        # 测试 5: 获取统计信息
        logger.info("\n测试 5: 获取统计信息")
        stats = cdn.get_stats()
        assert stats is not None, "获取统计信息失败"
        logger.info(f"CDN 统计信息: {stats}")
        assert stats["known_nodes_count"] >= 1, "没有已知节点"
        assert stats["data_count"] >= 1, "没有数据"
        
        # 测试 6: 移除节点
        logger.info("\n测试 6: 移除节点")
        cdn.remove_node("test_peer_node")
        logger.info("移除节点成功")
        
        # 测试 7: 删除数据
        logger.info("\n测试 7: 删除数据")
        delete_result = await cdn.delete_data(data_id)
        assert delete_result, "删除数据失败"
        
        # 验证数据已删除
        deleted_data = await cdn.get_data(data_id)
        assert deleted_data is None, "数据未被删除"
        logger.info("删除数据成功，数据已不存在")
        
        logger.info("\n所有 P2P CDN 直接测试通过！")
        
    finally:
        # 停止 CDN
        await cdn.stop()


async def main():
    """主测试函数"""
    logger.info("开始测试 P2P CDN 直接功能...")
    
    try:
        await test_cdn_direct()
        logger.info("P2P CDN 直接测试完成！")
    except Exception as e:
        logger.error(f"测试失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
