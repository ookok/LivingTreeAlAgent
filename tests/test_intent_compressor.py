# -*- coding: utf-8 -*-
"""
意图保持型压缩器测试
==================

Author: Hermes Desktop Team
Date: 2026-04-24
"""

import sys
import time
sys.path.insert(0, "f:/mhzyapp/LivingTreeAlAgent")

from core.intent_preserving_compressor import (
    IntentPreservingCompressor,
    IntentRecognizer,
    CodeSignatureExtractor,
    ContextPyramid,
    IntentType,
    quick_compress,
)


def test_intent_recognizer():
    """测试意图识别"""
    print("\n" + "=" * 60)
    print("🧪 测试 1: 意图识别器")
    print("=" * 60)

    recognizer = IntentRecognizer()

    test_cases = [
        ("帮我写一个用户登录的函数", "应该识别为代码生成"),
        ("这段代码报错了怎么修复", "应该识别为调试"),
        ("优化一下这个类的性能", "应该识别为重构"),
        ("Python的装饰器是什么", "应该识别为查询"),
        ("你好啊，最近怎么样", "应该识别为对话"),
    ]

    for query, expected in test_cases:
        sig = recognizer.recognize(query)
        print(f"\n📝 Query: {query}")
        print(f"   预期: {expected}")
        print(f"   结果: {sig.intent_type.value} | 动作: {sig.action} | 目标: {sig.target}")
        print(f"   约束: {sig.constraints}")


def test_code_signature_extractor():
    """测试代码签名提取"""
    print("\n" + "=" * 60)
    print("🧪 测试 2: 代码签名提取")
    print("=" * 60)

    extractor = CodeSignatureExtractor()

    python_code = '''
"""用户管理模块"""

class UserService:
    """用户服务类"""

    def __init__(self, db_connection):
        self.db = db_connection

    def get_user(self, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        query = f"SELECT * FROM users WHERE id = {user_id}"
        result = self.db.execute(query)
        return result.fetch_one()

    def create_user(self, username: str, email: str) -> User:
        """创建新用户"""
        query = f"INSERT INTO users (username, email) VALUES ('{username}', '{email}')"
        self.db.execute(query)
        return User(username=username, email=email)

    def _internal_helper(self):
        """内部辅助方法（不应被提取）"""
        pass

def calculate_user_score(user_id: int, actions: List[str]) -> float:
    """计算用户评分"""
    score = 0.0
    for action in actions:
        if action == "login":
            score += 1.0
        elif action == "purchase":
            score += 10.0
    return score
'''

    signatures = extractor.extract_from_code(python_code, "python")

    print(f"\n📊 提取到 {len(signatures)} 个签名:")
    for sig in signatures:
        print(f"\n   类型: {sig.signature_type.value}")
        print(f"   名称: {sig.name}")
        print(f"   签名: {sig.signature}")
        if sig.parameters:
            print(f"   参数: {[p['name'] for p in sig.parameters]}")
        if sig.public_methods:
            print(f"   公开方法: {sig.public_methods}")

    # 测试压缩
    print("\n📦 压缩后的代码:")
    compressed = extractor.compress_code(python_code, "python")
    print(compressed[:500])


def test_context_pyramid():
    """测试分层上下文金字塔"""
    print("\n" + "=" * 60)
    print("🧪 测试 3: 分层上下文金字塔")
    print("=" * 60)

    pyramid = ContextPyramid(max_total_tokens=500)

    # 添加各层内容
    pyramid.add_content(0, "系统提示：你是一个Python编程助手", priority=100)
    pyramid.add_content(1, "用户意图：生成一个用户管理类", priority=95)
    pyramid.add_content(2, "class UserService:\n    def __init__(self)\n    def get_user(self)", priority=80)
    pyramid.add_content(3, "具体实现逻辑：这里有1000行代码...", priority=50)

    print("\n📊 金字塔结构:")
    print(pyramid.get_summary())

    print("\n📦 构建后的上下文:")
    result = pyramid.build()
    print(result)


def test_intent_preserving_compressor():
    """测试完整压缩流程"""
    print("\n" + "=" * 60)
    print("🧪 测试 4: 意图保持型压缩（完整流程）")
    print("=" * 60)

    compressor = IntentPreservingCompressor(max_tokens=8000)

    test_cases = [
        {
            "name": "代码生成请求",
            "query": "帮我创建一个用户服务类，需要支持用户注册、登录、修改密码功能，性能要高效，最好支持异步操作",
            "code": '''
class UserService:
    def __init__(self, db):
        self.db = db

    async def register(self, username, password, email):
        # 实现注册逻辑（500行代码...）
        pass

    async def login(self, username, password):
        # 实现登录逻辑（300行代码...）
        pass

    async def change_password(self, user_id, old_pwd, new_pwd):
        # 实现改密逻辑（200行代码...）
        pass

    def _validate_input(self, data):
        # 内部验证方法
        pass
''',
        },
        {
            "name": "调试请求",
            "query": "这个函数报错了，TypeError: cannot concatenate 'str' and 'int' objects",
            "code": '''
def calculate_total(items, tax_rate):
    total = 0
    for item in items:
        total = total + item["price"]  # 这里可能出错
    total = total + tax_rate
    return total
''',
        },
    ]

    for case in test_cases:
        print(f"\n{'='*50}")
        print(f"📝 测试用例: {case['name']}")
        print(f"{'='*50}")
        print(f"原始查询 ({len(case['query'])} 字): {case['query'][:100]}...")

        result = compressor.compress(
            query=case["query"],
            context="用户正在开发一个电商系统",
            code=case["code"],
        )

        print(f"\n🎯 意图签名:")
        sig = result["intent_signature"]
        print(f"   类型: {sig['type']}")
        print(f"   动作: {sig['action']}")
        print(f"   目标: {sig['target']}")
        print(f"   约束: {sig['constraints']}")

        print(f"\n📊 代码签名 ({len(result['code_signatures'])} 个):")
        for cs in result["code_signatures"]:
            print(f"   {cs['signature']}")

        print(f"\n📦 压缩结果 ({result['stats']['compressed_tokens']} tokens):")
        print(result["compressed"][:300])

        print(f"\n📈 压缩统计:")
        stats = result["stats"]
        print(f"   原始: {stats['original_tokens']} tokens")
        print(f"   压缩后: {stats['compressed_tokens']} tokens")
        print(f"   节省: {stats['compression_ratio']}")


def test_quick_compress():
    """测试快速压缩函数"""
    print("\n" + "=" * 60)
    print("🧪 测试 5: 快速压缩")
    print("=" * 60)

    query = "帮我优化这个排序算法的性能，要求时间复杂度O(nlogn)，空间复杂度O(1)"
    code = "def bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n-i-1):\n            if arr[j] > arr[j+1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]\n    return arr"

    result = quick_compress(query, code=code)
    print(f"\n📦 快速压缩结果:")
    print(result)


def benchmark():
    """性能基准测试"""
    print("\n" + "=" * 60)
    print("⚡ 性能基准测试")
    print("=" * 60)

    compressor = IntentPreservingCompressor()

    # 生成测试数据
    long_code = '''
class LargeService:
    def __init__(self):
        self.data = []

    ''' + '\n'.join([f'''
    def method_{i}(self, param_{j}):
        """方法 {i} 的详细实现，包含大量的业务逻辑代码"""
        result = 0
        for k in range(1000):
            result += param_{j} * k
            if result > 1000000:
                break
        return result
''' for i in range(50)])

    query = "帮我优化这个大服务类的性能，要求支持高并发，安全可靠"

    print(f"代码长度: {len(long_code)} 字符")

    # 测试压缩速度
    times = []
    for _ in range(5):
        start = time.time()
        result = compressor.compress(query, code=long_code)
        elapsed = time.time() - start
        times.append(elapsed)

    avg_time = sum(times) / len(times)
    print(f"平均压缩时间: {avg_time*1000:.2f} ms")
    print(f"压缩率: {result['stats']['compression_ratio']}")


if __name__ == "__main__":
    print("\n" + "🎯" * 30)
    print("意图保持型压缩器测试套件")
    print("🎯" * 30)

    test_intent_recognizer()
    test_code_signature_extractor()
    test_context_pyramid()
    test_intent_preserving_compressor()
    test_quick_compress()
    benchmark()

    print("\n" + "=" * 60)
    print("✅ 所有测试完成!")
    print("=" * 60)
