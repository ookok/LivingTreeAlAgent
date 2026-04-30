"""
记忆系统增强功能集成测试（简化版）
================================

测试新增的记忆系统模块：
1. MemorySummaryGenerator - 记忆摘要生成
2. MultimodalMemorySystem - 多模态记忆
3. SharedMemorySystem - 全局共享记忆

注：AutoMemoryManager 和 IntelligentMemoryRetriever 因依赖复杂外部模块，暂不测试

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import pytest
import time

# 导入测试模块（只导入不依赖复杂外部模块的模块）
from client.src.business.memory_summary_generator import (
    MemorySummaryGenerator,
    SummaryType,
    SummaryMode,
    ConversationContext,
    get_summary_generator,
)
from client.src.business.multimodal_memory import (
    MultimodalMemorySystem,
    MediaType,
    Modality,
    MultimodalContent,
    MultimodalQuery,
    get_multimodal_memory,
)
from client.src.business.shared_memory_system import (
    SharedMemorySystem,
    PermissionLevel,
    SharingScope,
    SyncStatus,
    get_shared_memory,
)


class TestMemorySummaryGenerator:
    """记忆摘要生成器测试"""
    
    def test_create_generator(self):
        """测试创建摘要生成器"""
        generator = get_summary_generator()
        assert isinstance(generator, MemorySummaryGenerator)
    
    def test_generate_summary(self):
        """测试生成摘要"""
        generator = get_summary_generator()
        
        context = ConversationContext(
            conversation_id="test_summary",
            messages=[
                {"role": "user", "content": "我想开发一个电商系统"},
                {"role": "assistant", "content": "好的，需要包含用户模块、商品模块和订单模块"},
            ]
        )
        
        result = generator.generate_summary(context, SummaryType.BRIEF)
        
        assert hasattr(result, 'content')
        assert hasattr(result, 'key_points')
        assert hasattr(result, 'entities')
        assert result.summary_type == SummaryType.BRIEF
    
    def test_extract_key_points(self):
        """测试提取关键要点"""
        generator = get_summary_generator()
        
        text = "我们需要开发一个电商系统，包含用户管理、商品管理和订单管理三个模块。使用微服务架构，确保高可用性和可扩展性。"
        
        # 使用 mock 避免依赖 LLM
        generator._llm_callable = lambda prompt: "1. 开发电商系统\n2. 用户管理模块\n3. 商品管理模块\n4. 订单管理模块\n5. 微服务架构"
        points = generator.extract_key_points(text)
        
        assert isinstance(points, list)
        assert len(points) > 0
    
    def test_get_stats(self):
        """测试获取统计信息"""
        generator = get_summary_generator()
        stats = generator.get_stats()
        
        assert "config" in stats
        assert "summary_types" in stats
        assert "modes" in stats


class TestMultimodalMemorySystem:
    """多模态记忆系统测试"""
    
    def test_create_system(self):
        """测试创建多模态记忆系统"""
        system = get_multimodal_memory()
        assert isinstance(system, MultimodalMemorySystem)
    
    def test_store_text(self):
        """测试存储纯文本"""
        system = get_multimodal_memory()
        
        item_id = system.store_text("这是一段测试文本", "user1")
        
        assert item_id is not None
        assert len(item_id) > 0
        
        # 验证存储
        item = system.get_item(item_id)
        assert item is not None
    
    def test_store_multimodal(self):
        """测试存储图文混合内容"""
        system = get_multimodal_memory()
        
        item_id = system.store_multimodal(
            text="这是产品说明",
            image_paths=["test_image.jpg"],
            conversation_id="conv1",
            tags=["product", "demo"]
        )
        
        assert item_id is not None
        
        # 验证存储
        item = system.get_item(item_id)
        assert item is not None
        assert len(item.contents) == 2  # 文本 + 图像
    
    def test_retrieve_text(self):
        """测试文本检索"""
        system = get_multimodal_memory()
        
        # 先存储一些内容
        system.store_text("电商系统设计文档", "user1")
        system.store_text("订单模块实现", "user1")
        
        results = system.retrieve_text("电商")
        
        assert isinstance(results, list)
    
    def test_get_stats(self):
        """测试获取统计信息"""
        system = get_multimodal_memory()
        stats = system.get_stats()
        
        assert "total_items" in stats
        assert "text_items" in stats
        assert "image_items" in stats


class TestSharedMemorySystem:
    """全局共享记忆系统测试"""
    
    def test_create_system(self):
        """测试创建共享记忆系统"""
        system = get_shared_memory()
        assert isinstance(system, SharedMemorySystem)
    
    def test_store_and_retrieve(self):
        """测试存储和检索共享记忆"""
        system = get_shared_memory()
        
        # 存储记忆
        item_id = system.store("共享知识内容", "user1", SharingScope.PUBLIC)
        
        assert item_id is not None
        
        # 检索记忆（使用不同用户）
        results = system.retrieve("共享知识", "user2")
        
        assert isinstance(results, list)
        assert len(results) > 0
    
    def test_permissions(self):
        """测试权限管理"""
        system = get_shared_memory()
        
        # 存储私有记忆
        item_id = system.store("私有内容", "owner", SharingScope.PRIVATE)
        
        # 其他用户应该无法访问
        results = system.retrieve("私有内容", "other_user")
        assert len(results) == 0
        
        # 授予权限
        system.grant_permission(item_id, "other_user", PermissionLevel.READ)
        
        # 现在可以访问
        results = system.retrieve("私有内容", "other_user")
        assert len(results) > 0
    
    def test_update_and_delete(self):
        """测试更新和删除"""
        system = get_shared_memory()
        
        # 存储记忆
        item_id = system.store("原始内容", "user1")
        
        # 更新内容（所有者应该有权限）
        success = system.update(item_id, "更新后的内容", "user1")
        assert success is True
        
        # 验证更新
        item = system._memory_store.get(item_id)
        assert item.content == "更新后的内容"
        
        # 删除内容
        success = system.delete(item_id, "user1")
        assert success is True
    
    def test_version_history(self):
        """测试版本历史"""
        system = get_shared_memory()
        
        # 存储记忆
        item_id = system.store("v1内容", "user1")
        
        # 更新多次
        system.update(item_id, "v2内容", "user1")
        system.update(item_id, "v3内容", "user1")
        
        # 获取版本历史
        history = system.get_version_history(item_id, "user1")
        
        assert isinstance(history, list)
        assert len(history) >= 3
    
    def test_rollback(self):
        """测试版本回滚"""
        system = get_shared_memory()
        
        # 存储记忆
        item_id = system.store("原始版本", "user1")
        original_content = system._memory_store[item_id].content
        
        # 更新
        system.update(item_id, "更新版本", "user1")
        
        # 获取版本ID
        history = system.get_version_history(item_id, "user1")
        original_version_id = history[0].version_id
        
        # 回滚
        success = system.rollback(item_id, original_version_id, "user1")
        assert success is True
        
        # 验证回滚
        item = system._memory_store.get(item_id)
        assert item.content == original_content
    
    def test_get_stats(self):
        """测试获取统计信息"""
        system = get_shared_memory()
        stats = system.get_stats()
        
        assert "total_items" in stats
        assert "scope_counts" in stats


class TestIntegration:
    """集成测试"""
    
    def test_memory_integration(self):
        """测试记忆系统集成"""
        # 1. 摘要生成
        generator = get_summary_generator()
        context = ConversationContext(
            conversation_id="summary_test",
            messages=[
                {"role": "user", "content": "项目管理系统需求"},
                {"role": "assistant", "content": "包含任务管理、团队协作、进度跟踪"},
            ]
        )
        summary = generator.generate_summary(context)
        assert len(summary.content) > 0
        
        # 2. 多模态存储
        multimodal = get_multimodal_memory()
        item_id = multimodal.store_multimodal("项目文档", [], "user1")
        assert item_id is not None
        
        # 3. 共享记忆
        shared = get_shared_memory()
        shared_item_id = shared.store("团队共享知识", "user1", SharingScope.TEAM)
        assert shared_item_id is not None
        
        print("记忆系统集成测试通过！")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])