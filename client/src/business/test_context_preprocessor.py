"""
上下文预处理器测试脚本
=====================

测试 ContextPreprocessor 的各项功能：
1. 重要度评分
2. 去重
3. 关键信息提取
4. 内容压缩
5. 窗口优化

运行方式：python core/test_context_preprocessor.py
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from business.context_preprocessor import (
    ContextPreprocessor, ContextSegment, ContentType, ProcessingStats
)


def test_basic_compression():
    """测试基本压缩功能"""
    print("=" * 60)
    print("测试 1: 基本压缩功能")
    print("=" * 60)

    preprocessor = ContextPreprocessor(
        max_context_tokens=8192,
        compression_ratio=0.3,
        enable_compression=True,
        enable_dedup=True,
        enable_extraction=True,
    )

    # 创建测试数据：模拟一个包含冗余内容的对话
    segments = [
        ContextSegment(
            content="你好，请帮我分析这段代码",
            content_type=ContentType.USER,
        ),
        ContextSegment(
            content="```python\ndef hello():\n    print('Hello World')\n```",
            content_type=ContentType.CODE,
        ),
        ContextSegment(
            content="好的，让我来分析这段代码...\n\n这是一个简单的 Python 函数...\n\n" * 10,  # 重复内容
            content_type=ContentType.ASSISTANT,
        ),
        ContextSegment(
            content="Error: NameError: name 'x' is not defined\n" + "Traceback...\n" * 5,
            content_type=ContentType.ERROR,
        ),
        ContextSegment(
            content="\n\n\n\n\n",  # 多余空白
            content_type=ContentType.OUTPUT,
        ),
    ]

    # 处理
    processed = preprocessor.process_context(segments)

    # 打印结果
    stats = preprocessor.get_stats()
    print(f"\n原始 token 数: {stats.original_tokens}")
    print(f"压缩后 token 数: {stats.compressed_tokens}")
    print(f"压缩率: {stats.compression_ratio:.1f}%")
    print(f"移除片段数: {stats.segments_removed}")
    print(f"压缩片段数: {stats.segments_compressed}")
    print(f"处理耗时: {stats.processing_time_ms:.0f}ms")

    print("\n优化后的内容:")
    for i, segment in enumerate(processed):
        print(f"\n--- 片段 {i+1} (类型: {segment.content_type.value}, 重要度: {segment.importance_score:.1f}) ---")
        print(segment.content[:200] + ("..." if len(segment.content) > 200 else ""))

    return stats


def test_deduplication():
    """测试去重功能"""
    print("\n" + "=" * 60)
    print("测试 2: 去重功能")
    print("=" * 60)

    preprocessor = ContextPreprocessor(enable_dedup=True)

    segments = [
        ContextSegment(content="这是第一段内容", content_type=ContentType.USER),
        ContextSegment(content="这是第一段内容", content_type=ContentType.USER),  # 重复
        ContextSegment(content="这是第二段内容", content_type=ContentType.USER),
        ContextSegment(content="  这是第一段内容  ", content_type=ContentType.USER),  # 空白不同但内容相同
    ]

    processed = preprocessor.process_context(segments)

    print(f"\n原始片段数: {len(segments)}")
    print(f"去重后片段数: {len(processed)}")
    print(f"移除重复数: {preprocessor.get_stats().segments_removed}")

    for i, segment in enumerate(processed):
        print(f"  片段 {i+1}: {segment.content[:50]}")

    return len(processed)


def test_key_extraction():
    """测试关键信息提取"""
    print("\n" + "=" * 60)
    print("测试 3: 关键信息提取")
    print("=" * 60)

    preprocessor = ContextPreprocessor(enable_extraction=True)

    # 包含代码和错误的混合内容
    content = """
这是一个测试输出

```python
def calculate(a, b):
    return a + b

result = calculate(1, 2)
print(result)
```

然后出现了一个错误：
Error: ValueError: invalid literal for int()

然后继续输出...
"""

    segments = [
        ContextSegment(content=content, content_type=ContentType.OUTPUT),
    ]

    processed = preprocessor.process_context(segments)

    print(f"\n原始片段数: {len(segments)}")
    print(f"提取后片段数: {len(processed)}")

    for i, segment in enumerate(processed):
        print(f"\n--- 片段 {i+1} (类型: {segment.content_type.value}) ---")
        print(segment.content[:300])


def test_window_optimization():
    """测试窗口优化"""
    print("\n" + "=" * 60)
    print("测试 4: 窗口优化（限制最大 token 数）")
    print("=" * 60)

    # 设置很小的窗口
    preprocessor = ContextPreprocessor(max_context_tokens=500)

    # 创建大量内容
    segments = [
        ContextSegment(content="系统提示：你是一个助手", content_type=ContentType.SYSTEM),
        ContextSegment(content="用户问题 1: " + "x" * 200, content_type=ContentType.USER),
        ContextSegment(content="助手回答 1: " + "y" * 300, content_type=ContentType.ASSISTANT),
        ContextSegment(content="用户问题 2: " + "z" * 200, content_type=ContentType.USER),
        ContextSegment(content="错误信息: Error test", content_type=ContentType.ERROR),
    ]

    processed = preprocessor.process_context(segments)

    print(f"\n原始片段数: {len(segments)}")
    print(f"优化后片段数: {len(processed)}")
    print(f"移除片段数: {preprocessor.get_stats().segments_removed}")

    for i, segment in enumerate(processed):
        print(f"  片段 {i+1} (类型: {segment.content_type.value}, 重要度: {segment.importance_score:.1f}): {segment.content[:50]}...")


def test_importance_scoring():
    """测试重要度评分"""
    print("\n" + "=" * 60)
    print("测试 5: 重要度评分")
    print("=" * 60)

    preprocessor = ContextPreprocessor()

    test_cases = [
        ("Error: Something failed", ContentType.ERROR),
        ("def hello(): pass", ContentType.CODE),
        ("Warning: deprecated", ContentType.WARNING),
        ("Please help me", ContentType.USER),
        ("System prompt", ContentType.SYSTEM),
        ("Regular output text", ContentType.OUTPUT),
    ]

    for content, content_type in test_cases:
        segments = [ContextSegment(content=content, content_type=content_type)]
        processed = preprocessor.process_context(segments)
        score = processed[0].importance_score if processed else 0
        print(f"  {content_type.value:12} | {content:30} | 重要度: {score:.1f}")


def test_token_estimation():
    """测试 token 估算"""
    print("\n" + "=" * 60)
    print("测试 6: Token 估算")
    print("=" * 60)

    preprocessor = ContextPreprocessor()

    test_cases = [
        "Hello World",
        "你好世界",
        "def hello():\n    print('Hello')",
        "这是一段较长的中文文本，用于测试 token 估算功能。" * 10,
        "This is a longer English text for testing token estimation. " * 10,
    ]

    for text in test_cases:
        tokens = preprocessor._estimate_tokens(text)
        chars = len(text)
        print(f"  字符数: {chars:5} | 估算 token: {tokens:5} | 内容: {text[:50]}...")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("上下文预处理器测试")
    print("=" * 60)

    start_time = time.time()

    try:
        test_basic_compression()
        test_deduplication()
        test_key_extraction()
        test_window_optimization()
        test_importance_scoring()
        test_token_estimation()

        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print(f"✅ 所有测试完成，耗时: {elapsed:.2f}秒")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
