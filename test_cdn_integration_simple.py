"""
简化的 P2P CDN 集成测试

测试 LivingTreeAI 节点与 P2P CDN 的集成，避免导入 numpy 等不必要的依赖
"""

import asyncio
import logging
import sys
import os

# 添加核心目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "core"))

# 直接导入 P2P CDN 模块
from p2p_cdn import create_p2p_cdn, CDNNode, NodeCapability

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_cdn_basic():
    """测试 P2P CDN 基本功能"""
    logger.info("=== 测试 P2P CDN 基本功能 ===")
    
    # 创建 P2P CDN 实例
    cdn = await create_p2p_cdn("test_node")
    
    try:
        # 测试 1: 存储结构化数据
        logger.info("\n测试 1: 存储结构化数据")
        knowledge_data = {
            "type": "knowledge",
            "title": "Python 基础知识",
            "content": "Python 是一种高级编程语言，易于学习和使用。",
            "tags": ["python", "programming", "basics"],
            "version": 1
        }
        data_id = await cdn.store_data(knowledge_data)
        assert data_id is not None, "存储数据失败"
        logger.info(f"存储知识数据成功，数据 ID: {data_id}")
        
        # 测试 2: 存储工作流模板
        logger.info("\n测试 2: 存储工作流模板")
        workflow_template = {
            "type": "workflow_template",
            "name": "数据处理工作流",
            "nodes": [
                {"id": "1", "type": "input", "name": "输入数据"},
                {"id": "2", "type": "process", "name": "处理数据"},
                {"id": "3", "type": "output", "name": "输出结果"}
            ],
            "connections": [
                {"source": "1", "target": "2"},
                {"source": "2", "target": "3"}
            ]
        }
        workflow_id = await cdn.store_data(workflow_template)
        assert workflow_id is not None, "存储工作流模板失败"
        logger.info(f"存储工作流模板成功，数据 ID: {workflow_id}")
        
        # 测试 3: 存储配置数据
        logger.info("\n测试 3: 存储配置数据")
        config_data = {
            "type": "config",
            "node_type": "universal",
            "max_memory_usage": 0.5,
            "timeout": 300,
            "retries": 3
        }
        config_id = await cdn.store_data(config_data)
        assert config_id is not None, "存储配置数据失败"
        logger.info(f"存储配置数据成功，数据 ID: {config_id}")
        
        # 测试 4: 获取数据
        logger.info("\n测试 4: 获取数据")
        retrieved_knowledge = await cdn.get_data(data_id)
        assert retrieved_knowledge is not None, "获取知识数据失败"
        assert retrieved_knowledge["title"] == knowledge_data["title"], "知识数据不匹配"
        logger.info("获取知识数据成功")
        
        retrieved_workflow = await cdn.get_data(workflow_id)
        assert retrieved_workflow is not None, "获取工作流模板失败"
        assert retrieved_workflow["name"] == workflow_template["name"], "工作流模板不匹配"
        logger.info("获取工作流模板成功")
        
        retrieved_config = await cdn.get_data(config_id)
        assert retrieved_config is not None, "获取配置数据失败"
        assert retrieved_config["node_type"] == config_data["node_type"], "配置数据不匹配"
        logger.info("获取配置数据成功")
        
        # 测试 5: 更新数据
        logger.info("\n测试 5: 更新数据")
        updated_knowledge = knowledge_data.copy()
        updated_knowledge["content"] = "Python 是一种高级编程语言，易于学习和使用。它具有丰富的库和框架。"
        updated_knowledge["version"] = 2
        update_result = await cdn.update_data(data_id, updated_knowledge)
        assert update_result, "更新知识数据失败"
        
        # 验证更新后的数据
        updated_retrieved = await cdn.get_data(data_id)
        assert updated_retrieved["version"] == 2, "更新后的数据版本不匹配"
        logger.info("更新知识数据成功")
        
        # 测试 6: 删除数据
        logger.info("\n测试 6: 删除数据")
        delete_result = await cdn.delete_data(config_id)
        assert delete_result, "删除配置数据失败"
        
        # 验证数据已删除
        deleted_config = await cdn.get_data(config_id)
        assert deleted_config is None, "配置数据未被删除"
        logger.info("删除配置数据成功")
        
        # 测试 7: 获取统计信息
        logger.info("\n测试 7: 获取统计信息")
        stats = cdn.get_stats()
        assert stats is not None, "获取统计信息失败"
        logger.info(f"CDN 统计信息: {stats}")
        assert stats["data_count"] >= 2, "数据数量不匹配"
        
        logger.info("\n所有 P2P CDN 基本功能测试通过！")
        
    finally:
        # 停止 CDN
        await cdn.stop()


async def main():
    """主测试函数"""
    logger.info("开始测试 P2P CDN 基本功能...")
    
    try:
        await test_cdn_basic()
        logger.info("P2P CDN 基本功能测试完成！")
    except Exception as e:
        logger.error(f"测试失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
