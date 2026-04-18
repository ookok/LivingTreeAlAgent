"""
学习世界模块示例
展示如何使用 Learning World 模块
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json


# 模拟 LLM 回调
def mock_llm_callback(prompt: str) -> str:
    if "隋朝" in prompt:
        return """
## 回答

隋朝（581年-618年）是中国历史上一个重要的朝代，虽然仅存在37年，但对后世影响深远。

### 建立与统一
隋朝由隋文帝杨坚建立，于589年统一南北朝，结束了近300年的分裂局面。

### 重要成就
- **大运河**：隋炀帝时期开凿，是世界上最长的运河之一
- **科举制度**：开创了通过考试选拔人才的先河

### 灭亡原因
隋炀帝好大喜功，三征高句丽、大兴土木，导致民不聊生。

## 知识标签
大运河 - 地点 - 隋朝修建的伟大水利工程
隋炀帝 - 人物 - 隋朝第二位皇帝
科举制度 - 制度 - 中国古代选拔官员的考试制度
杨坚 - 人物 - 隋朝开国皇帝

## 延伸问题
1. 大运河是如何开凿的？
2. 科举制度对中国有什么影响？
3. 隋炀帝为什么要修建大运河？
"""
    elif "大运河" in prompt:
        return """
## 回答

大运河是中国古代一项伟大的水利工程，全长约1794公里。

### 开凿背景
隋炀帝为了加强南北交通，于605年开始修建大运河。

## 知识标签
隋炀帝 - 人物 - 大运河的决策者和建设者
京杭大运河 - 地点 - 今天的运河名称
水利工程 - 技术 - 大运河属于古代水利工程
"""
    else:
        return """
## 回答

这是一个很有趣的话题。

## 知识标签
相关概念 - 概念 - 需要进一步探索的领域

## 延伸问题
1. 这个主题的起源是什么？
2. 它与哪些历史事件相关？
"""


async def main():
    print("=" * 60)
    print("Learning World Module Demo")
    print("=" * 60)
    
    # 1. 导入模块
    print("\n1. Import module...")
    from learning_world import (
        LearningWorld,
        KnowledgeTag,
        TagType,
    )
    print("   [OK] Module imported")
    
    # 2. 创建实例
    print("\n2. Create instance...")
    learning_world = LearningWorld(
        llm_callback=mock_llm_callback,
        model_name="qwen2.5:7b",
    )
    print("   [OK] Instance created")
    
    # 3. 设置用户兴趣
    print("\n3. Configure interests...")
    profile = learning_world.get_user_profile()
    profile.interests = ["历史", "工程", "文化"]
    profile.difficulty_preference = "normal"
    learning_world.save_profile()
    print(f"   [OK] Interests: {profile.interests}")
    
    # 4. 开始探索
    print("\n4. Start exploration: 隋朝历史")
    response = await learning_world.explore("隋朝历史")
    
    print(f"\n   Answer length: {len(response.answer)} chars")
    print(f"   Tags count: {len(response.tags)}")
    print(f"   Duration: {response.duration:.2f}s")
    
    # 5. 显示标签
    print("\n5. Generated tags:")
    for i, tag in enumerate(response.tags, 1):
        tag_type = tag.type.value if hasattr(tag.type, 'value') else str(tag.type)
        print(f"   {i}. [{tag_type}] {tag.text}")
        print(f"      - {tag.description}")
    
    # 6. 显示面包屑
    print("\n6. Exploration path:")
    breadcrumbs = learning_world.get_breadcrumbs()
    print(f"   {' -> '.join(breadcrumbs)}")
    
    # 7. 通过标签继续探索
    if response.tags:
        first_tag = response.tags[0]
        print(f"\n7. Explore by tag: {first_tag.text}")
        new_response = await learning_world.explore_by_tag(first_tag)
        
        print(f"\n   New answer length: {len(new_response.answer)} chars")
        print(f"   New tags count: {len(new_response.tags)}")
        
        print("\n   Updated path:")
        new_breadcrumbs = learning_world.get_breadcrumbs()
        print(f"   {' -> '.join(new_breadcrumbs)}")
    
    # 8. 显示用户画像统计
    print("\n8. User profile stats:")
    profile = learning_world.get_user_profile()
    print(f"   Explored topics: {len(profile.explored_topics)}")
    print(f"   Tag click stats: {profile.tag_click_stats}")
    print(f"   Preferred types: {profile.preferred_tag_types}")
    
    # 9. 导出数据结构
    print("\n9. Export data structure:")
    response_dict = response.to_dict()
    print(f"   - query: {response_dict['query']}")
    print(f"   - tags: {len(response_dict['tags'])} items")
    print(f"   - sources: {len(response_dict['sources'])} items")
    print(f"   - suggested_next: {response_dict['suggested_next'][:2]}...")
    
    print("\n" + "=" * 60)
    print("Demo completed!")
    print("=" * 60)


def demo_without_async():
    """不使用 async 的简化演示"""
    print("\n" + "=" * 60)
    print("Simple Demo (no async)")
    print("=" * 60)
    
    from learning_world.models import KnowledgeTag, TagType
    from learning_world.core import TagGenerator
    
    generator = TagGenerator()
    
    answer = """
隋朝大运河是隋炀帝时期修建的伟大水利工程，全长约1800公里。
隋文帝杨坚建立了隋朝，统一了南北朝。
"""
    
    tags = generator.generate_tags(
        query="大运河",
        answer=answer,
        user_interests=["历史", "工程"]
    )
    
    print("\nExtracted tags:")
    for tag in tags:
        tag_type = tag.type.value if hasattr(tag.type, 'value') else str(tag.type)
        print(f"  [{tag_type}] {tag.text} (weight: {tag.weight:.2f})")


if __name__ == "__main__":
    asyncio.run(main())
    demo_without_async()
