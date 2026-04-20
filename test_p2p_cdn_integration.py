"""
P2P CDN 集成测试

测试 P2P CDN 集成到 LivingTreeAI 节点的功能
"""

import asyncio
import logging

from core.living_tree_ai.node import LivingTreeNode, NodeType

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_cdn_integration():
    """测试 P2P CDN 集成"""
    logger.info("=== 测试 P2P CDN 集成 ===")
    
    # 创建 LivingTreeNode 实例
    node = LivingTreeNode(
        node_type=NodeType.UNIVERSAL,
        specialization="cdn_test"
    )
    
    try:
        # 启动节点
        await node.start()
        
        # 等待节点完全启动
        await asyncio.sleep(1)
        
        # 测试 1: 存储数据到 CDN
        logger.info("\n测试 1: 存储数据到 CDN")
        test_data = {
            "name": "测试数据",
            "type": "knowledge",
            "content": "这是一个测试数据，用于验证 P2P CDN 集成功能",
            "tags": ["test", "cdn", "integration"]
        }
        data_id = await node.store_cdn_data(test_data)
        assert data_id is not None, "存储数据失败"
        logger.info(f"存储数据成功，数据 ID: {data_id}")
        
        # 测试 2: 从 CDN 获取数据
        logger.info("\n测试 2: 从 CDN 获取数据")
        retrieved_data = await node.get_cdn_data(data_id)
        assert retrieved_data is not None, "获取数据失败"
        assert retrieved_data["name"] == test_data["name"], "获取的数据与存储的数据不匹配"
        logger.info("获取数据成功，数据内容匹配")
        
        # 测试 3: 更新 CDN 中的数据
        logger.info("\n测试 3: 更新 CDN 中的数据")
        updated_data = {
            "name": "更新后的测试数据",
            "type": "knowledge",
            "content": "这是更新后的测试数据，用于验证 P2P CDN 集成功能",
            "tags": ["test", "cdn", "integration", "updated"]
        }
        update_result = await node.update_cdn_data(data_id, updated_data)
        assert update_result, "更新数据失败"
        
        # 验证更新后的数据
        updated_retrieved_data = await node.get_cdn_data(data_id)
        assert updated_retrieved_data["name"] == updated_data["name"], "更新后的数据与预期不匹配"
        logger.info("更新数据成功，数据内容已更新")
        
        # 测试 4: 添加 CDN 节点
        logger.info("\n测试 4: 添加 CDN 节点")
        node.add_cdn_node(
            node_id="test_peer_node",
            storage_available=1024 * 1024 * 1024,  # 1GB
            bandwidth=100,  # 100 Mbps
            uptime=3600,  # 1小时
            reliability=0.99  # 99% 可靠性
        )
        
        # 测试 5: 获取 CDN 统计信息
        logger.info("\n测试 5: 获取 CDN 统计信息")
        cdn_stats = node.get_cdn_stats()
        assert cdn_stats is not None, "获取 CDN 统计信息失败"
        logger.info(f"CDN 统计信息: {cdn_stats}")
        assert cdn_stats["known_nodes_count"] >= 1, "没有已知节点"
        assert cdn_stats["data_count"] >= 1, "没有数据"
        
        # 测试 6: 移除 CDN 节点
        logger.info("\n测试 6: 移除 CDN 节点")
        node.remove_cdn_node("test_peer_node")
        
        # 测试 7: 删除 CDN 中的数据
        logger.info("\n测试 7: 删除 CDN 中的数据")
        delete_result = await node.delete_cdn_data(data_id)
        assert delete_result, "删除数据失败"
        
        # 验证数据已删除
        deleted_data = await node.get_cdn_data(data_id)
        assert deleted_data is None, "数据未被删除"
        logger.info("删除数据成功，数据已不存在")
        
        logger.info("\n所有 P2P CDN 集成测试通过！")
        
    finally:
        # 停止节点
        await node.stop()


async def main():
    """主测试函数"""
    logger.info("开始测试 P2P CDN 集成...")
    
    try:
        await test_cdn_integration()
        logger.info("P2P CDN 集成测试完成！")
    except Exception as e:
        logger.error(f"测试失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
