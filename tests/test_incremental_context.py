"""
测试增量上下文管理器

测试内容：
1. 增量更新功能测试
2. L0/L1/L2 分层摘要测试
3. Token预算管理测试
4. 差分渲染支持测试
5. 上下文保存/加载测试

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import asyncio
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from client.src.business.incremental_context import IncrementalContextManager, ContextLayer


async def test_incremental_context():
    """测试增量上下文管理器"""
    print("测试增量上下文管理器...")
    print("=" * 60)
    
    # 1. 创建实例
    print("\n[1] 测试创建实例...")
    try:
        manager = IncrementalContextManager()
        print(f"    ✓ 实例创建成功")
        print(f"    ✓ 默认最大Token: {manager.get_max_tokens()}")
    except Exception as e:
        print(f"    ✗ 创建失败: {e}")
        return
    
    # 2. 测试增量更新
    print("\n[2] 测试增量更新...")
    try:
        session_id = "test_session_001"
        
        messages1 = [
            {"role": "user", "content": "你好，我想了解人工智能"},
            {"role": "assistant", "content": "您好！人工智能是研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统的一门新的技术科学。"},
        ]
        manager.update_incremental(session_id, messages1)
        print(f"    ✓ 第一次更新: 添加 {len(messages1)} 条消息")
        
        messages2 = [
            {"role": "user", "content": "什么是机器学习？"},
            {"role": "assistant", "content": "机器学习是人工智能的一个分支，它使计算机系统能够从数据中学习和改进，而无需进行明确编程。"},
        ]
        manager.update_incremental(session_id, messages2)
        print(f"    ✓ 第二次更新: 增量添加 {len(messages2)} 条消息")
        
        context = manager.get_context(session_id)
        print(f"    ✓ 上下文总消息数: {len(context)}")
    except Exception as e:
        print(f"    ✗ 增量更新失败: {e}")
    
    # 3. 测试分层摘要
    print("\n[3] 测试分层摘要...")
    try:
        l0_summary = manager.get_l0_summary(session_id)
        print(f"    ✓ L0摘要生成成功: {l0_summary[:50]}...")
        
        manager.set_l1_summary(session_id, "这是一个关于AI和机器学习基础概念的对话，用户询问了人工智能的定义和机器学习的概念。")
        l1_summary = manager.get_l1_summary(session_id)
        print(f"    ✓ L1摘要设置成功")
        
        # 测试获取增强上下文
        enhanced_context = manager._get_enhanced_context(session_id, 8192)
        print(f"    ✓ 增强上下文消息数: {len(enhanced_context)}")
    except Exception as e:
        print(f"    ✗ 分层摘要测试失败: {e}")
    
    # 4. 测试Token计数和预算管理
    print("\n[4] 测试Token计数和预算管理...")
    try:
        tokens = manager.get_token_count(session_id)
        print(f"    ✓ Token计数: {tokens}")
        
        # 测试压缩上下文
        compressed_context = manager._get_compressed_context(session_id, 100)
        print(f"    ✓ 压缩上下文消息数: {len(compressed_context)}")
        
        # 测试不同Token限制
        manager.set_max_tokens(4096)
        print(f"    ✓ 设置最大Token: {manager.get_max_tokens()}")
    except Exception as e:
        print(f"    ✗ Token管理测试失败: {e}")
    
    # 5. 测试脏标记
    print("\n[5] 测试脏标记...")
    try:
        print(f"    ✓ 更新后是否脏: {manager.is_dirty(session_id)}")
        
        manager.mark_clean(session_id)
        print(f"    ✓ 标记干净后: {manager.is_dirty(session_id)}")
        
        # 再次更新
        manager.update_incremental(session_id, [{"role": "user", "content": "深度学习是什么？"}])
        print(f"    ✓ 再次更新后是否脏: {manager.is_dirty(session_id)}")
    except Exception as e:
        print(f"    ✗ 脏标记测试失败: {e}")
    
    # 6. 测试差异获取
    print("\n[6] 测试差异获取...")
    try:
        diff, count = manager.get_diff(session_id, 4)
        print(f"    ✓ 新增消息数: {len(diff)}, 当前总数: {count}")
        
        for msg in diff:
            print(f"      - {msg['role']}: {msg['content']}")
    except Exception as e:
        print(f"    ✗ 差异获取失败: {e}")
    
    # 7. 测试保存和加载
    print("\n[7] 测试保存和加载...")
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        manager.save_context(session_id, temp_path)
        print(f"    ✓ 保存上下文成功")
        
        loaded_session_id = manager.load_context(temp_path)
        print(f"    ✓ 加载上下文成功，会话ID: {loaded_session_id}")
        
        loaded_context = manager.get_context(loaded_session_id)
        print(f"    ✓ 加载后消息数: {len(loaded_context)}")
        
        os.unlink(temp_path)
    except Exception as e:
        print(f"    ✗ 保存/加载失败: {e}")
    
    # 8. 测试多会话管理
    print("\n[8] 测试多会话管理...")
    try:
        session_id2 = "test_session_002"
        manager.update_incremental(session_id2, [{"role": "user", "content": "你好"}])
        
        session_ids = manager.get_session_ids()
        print(f"    ✓ 会话数量: {len(session_ids)}")
        print(f"    ✓ 会话列表: {session_ids}")
        
        manager.clear_session(session_id)
        print(f"    ✓ 清除会话后数量: {manager.get_session_count()}")
    except Exception as e:
        print(f"    ✗ 多会话管理失败: {e}")
    
    # 9. 测试清空所有
    print("\n[9] 测试清空所有...")
    try:
        manager.clear_all()
        print(f"    ✓ 清空后会话数量: {manager.get_session_count()}")
    except Exception as e:
        print(f"    ✗ 清空失败: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_incremental_context())