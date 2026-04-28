# -*- coding: utf-8 -*-
"""
测试超长 Query 三级压缩策略

验证：
1. Keyword 快缩（≤300字符）
2. LLM 语义压缩（300-500字符）—— Ollama 不可用时跳过
3. QueryChunker 分块（>500字符）
"""
import time
import sys
import io
sys.path.insert(0, '.')

# Windows console UTF-8 修复
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass

from unified_cache import QueryNormalizer, QueryCompressor, QueryChunker


def test_keyword_compress_short():
    """测试1: 短 query 直接 keyword 快缩"""
    print("\n" + "="*60)
    print("测试1: 短 query（≤300字符）→ keyword 快缩")
    print("="*60)

    compressor = QueryCompressor(enable_llm=False)  # 强制禁用 LLM
    normalizer = QueryNormalizer(max_length=200)

    queries = [
        "五一去杭州有什么好玩的地方推荐？",
        "帮我查一下特斯拉股价最近走势",
        "写一段 Python 代码实现快速排序",
    ]

    for q in queries:
        result = normalizer.normalize(q, compressor=compressor)
        print(f"\n原文({len(q)}字): {q}")
        print(f"压缩({len(result['cleaned'])}字): {result['cleaned']}")
        print(f"压缩方式: {result['compression_method']}")
        print(f"关键词: {list(result['keywords'])[:5]}")
        assert result["compression_method"] in ("none", "keyword_fallback"), f"预期 keyword 压缩，实际 {result['compression_method']}"


def test_llm_compress_medium():
    """测试2: 中等长度 query → LLM 语义压缩（如果可用）"""
    print("\n" + "="*60)
    print("测试2: 中等 query（300-500字符）→ LLM 语义压缩")
    print("="*60)

    compressor = QueryCompressor(model="qwen3.5:4b", enable_llm=True)
    normalizer = QueryNormalizer(max_length=200)

    queries = [
        "我想了解一下今年五一假期去杭州旅游的攻略，我计划在4月30日出发，5月4日返回，一共4天3晚的行程，希望能够涵盖西湖周边的著名景点，比如断桥、雷峰塔、灵隐寺等，同时也想去一些不那么热门但很有特色的地方，比如宋城主题公园或者千岛湖，不知道这个时间杭州的天气怎么样，需要提前准备什么衣物，另外住宿方面有什么性价比高的酒店推荐吗？",

        "我需要了解如何从零开始学习机器学习，包括需要掌握哪些数学基础知识，比如线性代数、概率论、微积分等，推荐一些适合初学者的学习资源，包括书籍、在线课程和实战项目，同时也想了解学习机器学习需要多少时间，以及如何规划学习路线，如何评估自己的学习效果，有没有一些学习社区或者论坛可以加入，请推荐一些实践项目来巩固理论知识。",
    ]

    for q in queries:
        q_clean = q.strip()
        print(f"\n原文({len(q_clean)}字): {q_clean[:80]}...")
        print(f"压缩触发: {'YES（超过300字）' if len(q_clean) > 300 else 'NO'}")

        start = time.time()
        result = normalizer.normalize(q_clean, compressor=compressor)
        elapsed = time.time() - start

        print(f"压缩方式: {result['compression_method']}")
        print(f"压缩后({len(result['cleaned'])}字): {result['cleaned']}")
        print(f"耗时: {elapsed:.2f}s")
        print(f"关键词: {list(result['keywords'])[:8]}")

        if result['compression_method'] == 'llm':
            print("✅ LLM 语义压缩成功！")
        elif result['compression_method'] == 'keyword_fallback':
            print("⚠️ LLM 不可用，降级为 keyword 快缩")
        elif result['compression_method'] == 'none':
            print("⚠️ 不足300字，未触发压缩")


def test_chunking_long():
    """测试3: 超长 query → QueryChunker 分块"""
    print("\n" + "="*60)
    print("测试3: 超长 query（>500字符）→ QueryChunker 分块")
    print("="*60)

    compressor = QueryCompressor(enable_llm=False)  # 强制分块
    normalizer = QueryNormalizer(max_length=200)
    chunker = QueryChunker(chunk_size=200, max_chunks=5)

    # 对话模式超长 query
    dialogue_query = (
        "用户：我想了解杭州五一旅游攻略。\n"
        "助手：杭州五一旅游可以安排3-5天。\n"
        "用户：我计划4月30日出发，5月4日返回。\n"
        "助手：这是4天4晚的行程。\n"
        "用户：想看西湖、灵隐寺、宋城。\n"
        "助手：推荐安排：第一天西湖，第二天灵隐寺加法喜寺，第三天宋城，第四天自由活动。\n"
        "用户：住宿有什么推荐吗？\n"
        "助手：推荐住在西湖附近的酒店，出行方便。\n"
        "用户：现在帮我整理一下完整行程，"
        "包括每天的景点安排、推荐的餐厅、需要的门票价格，以及从上海出发的交通方式。"
    )

    print(f"\n原文({len(dialogue_query)}字): 对话模式多轮问答")
    chunks = chunker.chunk(dialogue_query)
    print(f"\n分块结果（共{len(chunks)}块）:")
    for chunk in chunks:
        role = chunk.get("role", "unknown")
        print(f"  块{chunk['index']} [{role}]: {chunk['text'][:60]}...")

    # 测试 normalize 集成压缩
    result = normalizer.normalize(dialogue_query, compressor=compressor)
    print(f"\n压缩后({len(result['cleaned'])}字): {result['cleaned'][:100]}...")
    print(f"压缩方式: {result['compression_method']}")
    assert result['compression_method'] == 'chunking', f"预期 chunking，实际 {result['compression_method']}"
    print("✅ 分块压缩成功！")


def test_sentence_chunking():
    """测试4: 非对话超长文本 → 按句子分块"""
    print("\n" + "="*60)
    print("测试4: 长文档模式 → 按句子分块")
    print("="*60)

    normalizer = QueryNormalizer(max_length=200)
    chunker = QueryChunker(chunk_size=150, max_chunks=4)

    long_doc = (
        "杭州是中国著名的历史文化名城，也是世界文化遗产城市。西湖是杭州最著名的景点，也是中国最著名的湖泊之一。灵隐寺是杭州最古老的佛教寺庙，建于东晋时期。龙井茶是杭州特产，产于西湖龙井村附近的山地。宋城是一个以宋代文化为主题的大型主题公园，再现了南宋时期的繁华景象。千岛湖位于杭州淳安县，是一个人工湖，因湖中有1078个岛屿而得名。"
    )

    chunks = chunker.chunk(long_doc)
    print(f"原文({len(long_doc)}字) → {len(chunks)} 块:")
    for chunk in chunks:
        print(f"  块{chunk['index']}: {chunk['text'][:60]}...")

    merged = chunker.merge_chunks(chunks, normalizer)
    print(f"\n合并后({len(merged)}字): {merged[:100]}...")


def test_compressor_stats():
    """测试5: 压缩统计"""
    print("\n" + "="*60)
    print("测试5: QueryCompressor 统计")
    print("="*60)

    compressor = QueryCompressor(enable_llm=False)
    normalizer = QueryNormalizer(max_length=200)

    queries = [
        "短 query",
        "中 query " * 30,   # ~300字
        "长 query " * 60,   # ~600字
    ]

    for q in queries:
        result = normalizer.normalize(q, compressor=compressor)

    stats = compressor.stats()
    print(f"压缩统计: {stats}")
    print(f"✅ keyword_compress: {stats['keyword_compress']}")
    print(f"✅ llm_compress: {stats['llm_compress']}")
    print(f"✅ chunk: {stats['chunk']}")


def test_comparison_old_vs_new():
    """对比测试: 旧粗暴截断 vs 新语义压缩"""
    print("\n" + "="*60)
    print("对比测试: 旧粗暴截断 vs 新语义压缩")
    print("="*60)

    normalizer = QueryNormalizer(max_length=200)
    compressor = QueryCompressor(enable_llm=False)
    long_query = "我想了解一下今年五一假期去杭州旅游的详细攻略，包括景点推荐、美食推荐、住宿推荐、交通路线以及需要注意的事项，最好能够有具体的行程安排和预算参考。"

    print(f"\n原文({len(long_query)}字): {long_query}")

    # 旧方案（粗暴截断）
    old_clean = long_query[:200]
    old_keywords = normalizer.extract_keywords(old_clean)
    print(f"\n❌ 旧方案（粗暴截断200字）:")
    print(f"   结果: {old_clean[:80]}...")
    print(f"   关键词: {list(old_keywords)[:5]}")

    # 新方案（语义压缩）
    result = normalizer.normalize(long_query, compressor=compressor)
    print(f"\n✅ 新方案（QueryCompressor 分块压缩）:")
    print(f"   结果: {result['cleaned'][:80]}...")
    print(f"   压缩方式: {result['compression_method']}")
    print(f"   关键词: {list(result['keywords'])[:8]}")


if __name__ == "__main__":
    print("[TEST] 超长 Query 三级压缩策略测试")
    print("="*60)

    test_keyword_compress_short()
    test_llm_compress_medium()     # 如果 Ollama 可用则测 LLM
    test_chunking_long()           # 强制测试分块
    test_sentence_chunking()       # 句子分块
    test_compressor_stats()        # 统计
    test_comparison_old_vs_new()   # 对比

    print("\n" + "="*60)
    print("✅ 所有测试完成！")
    print("="*60)
