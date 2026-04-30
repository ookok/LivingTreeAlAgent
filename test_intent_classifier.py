"""测试增强意图分类器"""
import sys
sys.path.insert(0, 'client/src')

from business.memory import get_intent_classifier

print("=" * 60)
print("增强意图分类器测试")
print("=" * 60)

# 初始化分类器
classifier = get_intent_classifier()

# 降低置信度阈值以便测试
classifier.set_threshold("intent_confidence_threshold", 0.3)

# 添加更多训练示例
training_data = [
    ("你好", "greet"),
    ("您好", "greet"),
    ("hi", "greet"),
    ("hello", "greet"),
    ("嗨", "greet"),
    ("早上好", "greet"),
    ("晚上好", "greet"),
    ("再见", "goodbye"),
    ("拜拜", "goodbye"),
    ("谢谢", "thanks"),
    ("感谢", "thanks"),
    ("什么是人工智能", "query_knowledge"),
    ("解释一下机器学习", "query_knowledge"),
    ("介绍一下深度学习", "query_knowledge"),
    ("帮我写代码", "code_generation"),
    ("写一个Python函数", "code_generation"),
    ("修复错误", "error_recovery"),
    ("代码出错了", "error_recovery"),
    ("查找文档", "document_query"),
    ("用户手册", "document_query"),
    ("系统升级", "evolution"),
    ("训练模型", "evolution"),
    ("我的资料", "personal_info"),
    ("个人设置", "personal_info"),
    ("帮助", "help"),
    ("怎么用", "help")
]

for text, intent in training_data:
    classifier.add_training_example(text, intent)

# 测试意图分类
print("\n[1] 意图分类测试")
test_queries = [
    "你好！",
    "帮我写一个Python函数来计算斐波那契数列",
    "如何修复代码中的错误？",
    "不要帮我写代码",
    "什么是人工智能？",
    "谢谢！",
    "再见",
    "用户手册在哪里？",
    "系统如何升级？",
    "我的个人资料",
    "这个功能怎么用？"
]

for query in test_queries:
    result = classifier.classify(query)
    print(f'"{query}"')
    print(f'  -> 意图: {result.intent}, 置信度: {result.confidence:.2f}')

# 测试多意图识别
print("\n[2] 多意图识别测试")
query = "帮我写代码并解释一下"
results = classifier.classify_multi_intent(query)
print(f'"{query}"')
for i, result in enumerate(results):
    print(f'  {i+1}. 意图: {result["intent"]}, 置信度: {result["confidence"]:.2f}')

# 测试实体识别
print("\n[3] 实体识别测试")
test_texts = [
    "明天下午3:30开会",
    "邮箱是 test@example.com",
    "访问 https://example.com",
    "价格是 99.99 元",
    "日期是 2024-01-15"
]
for text in test_texts:
    result = classifier.classify(text)
    print(f'"{text}"')
    if result.entities:
        print(f'  -> 实体:')
        for entity in result.entities:
            print(f'     - {entity["entity"]}: {entity["value"]} (位置: {entity["start"]}-{entity["end"]})')
    else:
        print(f'  -> 无实体')

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)