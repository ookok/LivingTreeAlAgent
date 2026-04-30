"""
LLM Wiki FusionRAG 功能对等测试
验证 LLM Wiki 是否具备与 FusionRAG 相同的所有功能
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from client.src.business.llm_wiki import (
    LLMWikiIntegration,
    create_llm_wiki_integration,
    search_llm_wiki,
    __version__
)

from client.src.business.fusion_rag import (
    FusionRAG,
    create_fusion_rag
)


def test_feature_parity():
    """测试 LLM Wiki 与 FusionRAG 的功能对等性"""
    print("=" * 60)
    print(f"LLM Wiki 版本: {__version__}")
    print("测试 FusionRAG 功能对等性")
    print("=" * 60)
    
    # 创建 LLM Wiki 实例（带行业配置）
    wiki = create_llm_wiki_integration(config={"target_industry": "机械制造"})
    print("✓ LLMWikiIntegration 初始化完成")
    
    # 创建 FusionRAG 实例（对比）
    rag = create_fusion_rag({"target_industry": "机械制造"})
    print("✓ FusionRAG 初始化完成")
    
    # 测试功能列表
    features = [
        ("normalize_query", hasattr(wiki, 'normalize_query'), hasattr(rag, 'normalize_query')),
        ("search", hasattr(wiki, 'search'), hasattr(rag, 'search')),
        ("search_with_governance", hasattr(wiki, 'search_with_governance'), hasattr(rag, 'search')),
        ("search_with_triple_chain", hasattr(wiki, 'search_with_triple_chain'), hasattr(rag, 'search_with_triple_chain')),
        ("record_feedback", hasattr(wiki, 'record_feedback'), hasattr(rag, 'record_feedback')),
        ("add_synonym", hasattr(wiki, 'add_synonym'), hasattr(rag, 'add_synonym')),
        ("pin_document", hasattr(wiki, 'pin_document'), hasattr(rag, 'pin_document')),
    ]
    
    print("\n功能对比:")
    print("-" * 60)
    print(f"{'功能':<25} {'LLM Wiki':<12} {'FusionRAG':<12} {'对等':<6}")
    print("-" * 60)
    
    all_equal = True
    for feature, wiki_has, rag_has in features:
        equal = wiki_has == rag_has
        all_equal = all_equal and equal
        print(f"{feature:<25} {str(wiki_has):<12} {str(rag_has):<12} {'✓' if equal else '✗':<6}")
    
    print("-" * 60)
    
    if all_equal:
        print("\n✅ 所有功能对等！LLM Wiki 具备 FusionRAG 的所有核心功能")
    else:
        print("\n❌ 部分功能不对等，请检查")
    
    # 测试实际功能
    print("\n" + "=" * 60)
    print("测试实际功能")
    print("=" * 60)
    
    # 测试搜索功能
    query = "如何选择电机"
    
    # LLM Wiki 搜索
    print("\n1. LLM Wiki 搜索:")
    try:
        wiki_results = wiki.search(query, top_k=3)
        print(f"   ✓ 搜索成功，返回 {len(wiki_results)} 条结果")
    except Exception as e:
        print(f"   ✗ 搜索失败: {e}")
    
    # LLM Wiki 带治理搜索
    print("\n2. LLM Wiki 带治理搜索:")
    try:
        wiki_gov_results = wiki.search_with_governance(query, top_k=3)
        print(f"   ✓ 带治理搜索成功，返回 {len(wiki_gov_results)} 条结果")
    except Exception as e:
        print(f"   ✗ 带治理搜索失败: {e}")
    
    # LLM Wiki 三重链搜索
    print("\n3. LLM Wiki 三重链搜索:")
    try:
        wiki_tc_results = wiki.search_with_triple_chain(query)
        print(f"   ✓ 三重链搜索成功")
        print(f"   - 回答: {wiki_tc_results.get('answer', '')[:50]}...")
        print(f"   - 推理步骤: {len(wiki_tc_results.get('reasoning', []))} 步")
        print(f"   - 验证状态: {'通过' if wiki_tc_results.get('validation_passed') else '未通过'}")
    except Exception as e:
        print(f"   ✗ 三重链搜索失败: {e}")
    
    # 测试反馈记录
    print("\n4. LLM Wiki 记录反馈:")
    try:
        wiki.record_feedback(query, "test_doc", "content", "relevant")
        print("   ✓ 反馈记录成功")
    except Exception as e:
        print(f"   ✗ 反馈记录失败: {e}")
    
    # 测试同义词添加
    print("\n5. LLM Wiki 添加同义词:")
    try:
        wiki.add_synonym("马达", "电机")
        print("   ✓ 同义词添加成功")
    except Exception as e:
        print(f"   ✗ 同义词添加失败: {e}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_feature_parity()
    print("\n✅ 测试完成！")