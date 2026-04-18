"""
首页推荐系统演示脚本
展示推荐流程：用户画像 -> 召回 -> 排序 -> 展示
"""

import sys
import asyncio


def main():
    # -*- coding: utf-8 -*-
    import os
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from core.recommendation import (
        get_profile_manager,
        get_recall_engine,
        get_ranking_engine,
        adapt_items
    )
    from core.module_manager import get_module_manager
    
    print("=" * 60)
    print("🏠 首页推荐系统演示")
    print("=" * 60)
    
    # 1. 用户画像
    print("\n📊 [步骤1] 用户画像管理")
    print("-" * 40)
    
    profile_manager = get_profile_manager()
    profile = profile_manager.get_profile()
    
    print(f"用户ID: {profile.user_id}")
    print(f"冷启动状态: {'是' if profile.is_cold_start else '否'}")
    print(f"兴趣标签: {profile.get_top_interests() or '(暂无)'}")
    
    # 添加一些模拟兴趣
    profile_manager.update_from_tags(['科技', 'AI', '数码'])
    print(f"更新后兴趣: {profile.get_top_interests()}")
    
    # 2. 召回
    print("\n📡 [步骤2] 多源内容召回")
    print("-" * 40)
    
    recall_engine = get_recall_engine(profile_manager)
    
    # 模拟召回
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    items = loop.run_until_complete(
        recall_engine.recall_all(profile, limit_per_source=5)
    )
    loop.close()
    
    print(f"召回结果: {len(items)} 条")
    for item in items[:3]:
        print(f"  - [{item.source}] {item.title[:30]}...")
    
    # 3. 排序
    print("\n🎯 [步骤3] 智能排序混排")
    print("-" * 40)
    
    ranking_engine = get_ranking_engine()
    ranked_items = ranking_engine.rank(items, profile, top_k=5)
    
    print(f"排序结果 (Top 5):")
    for i, item in enumerate(ranked_items, 1):
        print(f"  {i}. [{item.content_type.value}] {item.title[:25]}...")
        print(f"     得分: {item.score:.3f} | 来源: {item.source}")
    
    # 4. 统一格式
    print("\n📋 [步骤4] 统一数据格式")
    print("-" * 40)
    
    unified = adapt_items(ranked_items)
    for item in unified[:3]:
        print(f"  [{item.type}] {item.title[:30]}...")
        print(f"    URL: {item.url}")
        print(f"    Tags: {item.tags}")
    
    # 5. 模块管理
    print("\n⚙️ [步骤5] 模块配置管理")
    print("-" * 40)
    
    module_manager = get_module_manager()
    print("首页模块:")
    for mod in module_manager.get_all_modules():
        status = "可见" if mod.visible else "隐藏"
        print(f"  {mod.icon} {mod.name}: {status}")
    
    # 测试隐藏模块
    module_manager.set_visible("game_hall", False)
    print("\n隐藏游戏世界后:")
    for mod in module_manager.get_visible_modules():
        print(f"  {mod.icon} {mod.name} ✓")
    
    # 恢复
    module_manager.set_visible("game_hall", True)
    
    print("\n" + "=" * 60)
    print("✅ 演示完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
