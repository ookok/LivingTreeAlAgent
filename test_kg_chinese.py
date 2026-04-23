#!/usr/bin/env python3
"""
知识图谱增强中文优化测试
========================

测试中文实体和关系提取的优化效果
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.knowledge_innovation import KnowledgeGraphEnhancer

def test_chinese_extraction():
    """测试中文实体和关系提取"""
    
    print("=" * 70)
    print("Knowledge Graph Enhancement - Chinese Optimization Test")
    print("=" * 70)
    
    # 创建增强器
    enhancer = KnowledgeGraphEnhancer()
    
    # 测试文本1：科技新闻
    text1 = """
    华为公司发布了新款Mate手机，采用鸿蒙操作系统。
    华为消费者业务CEO余承东表示，这是华为自主研发的重要成果。
    鸿蒙系统基于微内核架构，支持分布式计算。
    苹果公司则继续使用iOS系统。
    """
    
    print("\n[Test 1] Tech News:")
    print("-" * 50)
    print(text1.strip())
    
    entities1 = enhancer.extract_entities(text1)
    relations1 = enhancer.extract_relations(text1)
    
    print(f"\n[+] Extracted {len(entities1)} entities:")
    for e in entities1[:10]:
        print(f"   [{e.type:12}] {e.name} (conf: {e.confidence:.2f})")
    
    print(f"\n[*] Extracted {len(relations1)} relations:")
    for r in relations1[:10]:
        print(f"   [{r.relation:12}] {r.source} -> {r.target} (conf: {r.confidence:.2f})")
    
    # 测试文本2：学术论文
    text2 = """
    深度学习是机器学习的一个分支，基于神经网络的算法。
    Transformer模型由谷歌公司提出，广泛应用于自然语言处理。
    BERT模型是由谷歌大脑团队开发，基于Transformer的双向编码器。
    GPT系列由OpenAI公司提出，包括GPT、GPT-2、GPT-3等版本。
    """
    
    print("\n\n[Test 2] Academic Paper:")
    print("-" * 50)
    print(text2.strip())
    
    entities2 = enhancer.extract_entities(text2)
    relations2 = enhancer.extract_relations(text2)
    
    print(f"\n[+] Extracted {len(entities2)} entities:")
    for e in entities2[:10]:
        print(f"   [{e.type:12}] {e.name} (conf: {e.confidence:.2f})")
    
    print(f"\n[*] Extracted {len(relations2)} relations:")
    for r in relations2[:10]:
        print(f"   [{r.relation:12}] {r.source} -> {r.target} (conf: {r.confidence:.2f})")
    
    # 测试文本3：旅游信息
    text3 = """
    郑州是河南省的省会，位于中原地区。
    五一劳动节期间，郑州推出了多项旅游活动。
    嵩山少林寺是著名的旅游景点，属于世界文化遗产。
    郑州方特欢乐世界是大型主题公园，包括飞越极限等项目。
    """
    
    print("\n\n[Test 3] Travel Info:")
    print("-" * 50)
    print(text3.strip())
    
    entities3 = enhancer.extract_entities(text3)
    relations3 = enhancer.extract_relations(text3)
    
    print(f"\n[+] Extracted {len(entities3)} entities:")
    for e in entities3[:10]:
        print(f"   [{e.type:12}] {e.name} (conf: {e.confidence:.2f})")
    
    print(f"\n[*] Extracted {len(relations3)} relations:")
    for r in relations3[:10]:
        print(f"   [{r.relation:12}] {r.source} -> {r.target} (conf: {r.confidence:.2f})")
    
    # 增强知识条目测试
    print("\n\n" + "=" * 70)
    print("[Test 4] Enhance Knowledge Entry")
    print("=" * 70)
    
    result = enhancer.enhance_knowledge(
        doc_id="test_001",
        content=text1,
        title="华为发布鸿蒙系统"
    )
    
    print(f"\nEnhancement Result:")
    print(f"   doc_id: {result['doc_id']}")
    print(f"   entities_extracted: {result['entities_extracted']}")
    print(f"   relations_extracted: {result['relations_extracted']}")
    print(f"   linked_entities: {result['linked_entities']}")
    print(f"   entity_types: {result['entity_types']}")
    
    # 查找路径测试
    print("\n\n" + "=" * 70)
    print("[Test 5] Find Relationship Paths")
    print("=" * 70)
    
    paths = enhancer.find_paths("华为公司", "鸿蒙系统", max_depth=3)
    if paths:
        print(f"\nFound paths:")
        for path in paths:
            print(f"   {' -> '.join(path)}")
    else:
        print("\nNo paths found (need more data)")
    
    # 实体信息查询
    print("\n\n" + "=" * 70)
    print("[Test 6] Entity Info Query")
    print("=" * 70)
    
    info = enhancer.get_entity_info("华为公司")
    if info:
        print(f"\nHuawei Company Info:")
        print(f"   type: {info['type']}")
        print(f"   confidence: {info['confidence']:.2f}")
        print(f"   mentions: {info['mentions']}")
        print(f"   relations: {info['relations']}")
        print(f"   related_entities: {info['related_entities']}")
    else:
        print("\nEntity not found")
    
    print("\n\n" + "=" * 70)
    print("Test Complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_chinese_extraction()
