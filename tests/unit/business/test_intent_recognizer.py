"""
单元测试：IntentRecognizer 意图识别器
测试动态意图识别和模式学习功能
"""

import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "client" / "src"))

from business.hermes_agent.intent_recognizer import IntentRecognizer, Intent, IntentCategory


class TestIntent(unittest.TestCase):
    """测试 Intent 数据类"""
    
    def test_intent_creation(self):
        """测试创建 Intent 对象"""
        intent = Intent(
            category=IntentCategory.CODE,
            action="implement",
            objects=["function", "class"],
            context={"language": "python"},
            confidence=0.9
        )
        
        self.assertEqual(intent.category, IntentCategory.CODE)
        self.assertEqual(intent.action, "implement")
        self.assertEqual(intent.objects, ["function", "class"])
        self.assertEqual(intent.context["language"], "python")
        self.assertEqual(intent.confidence, 0.9)
    
    def test_intent_to_dict(self):
        """测试转换为字典"""
        intent = Intent(
            category=IntentCategory.CHAT,
            action="greet",
            objects=[],
            context={},
            confidence=0.95
        )
        
        data = intent.to_dict()
        self.assertEqual(data["category"], "chat")
        self.assertEqual(data["action"], "greet")
        self.assertEqual(data["confidence"], 0.95)


class TestIntentRecognizer(unittest.TestCase):
    """测试 IntentRecognizer 类"""
    
    def setUp(self):
        """测试前准备"""
        self.recognizer = IntentRecognizer()
    
    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(len(self.recognizer.intent_patterns), 0)
        self.assertTrue(self.recognizer.learning_enabled)
        self.assertEqual(self.recognizer.min_confidence, 0.6)
    
    def test_recognize_simple_intent(self):
        """测试识别简单意图"""
        # 测试代码相关意图
        intent = self.recognizer.recognize("帮我写一个Python函数")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.category, IntentCategory.CODE)
        self.assertGreater(intent.confidence, 0.6)
    
    def test_recognize_chat_intent(self):
        """测试识别聊天意图"""
        intent = self.recognizer.recognize("你好")
        self.assertEqual(intent.category, IntentCategory.CHAT)
    
    def test_recognize_search_intent(self):
        """测试识别搜索意图"""
        intent = self.recognizer.recognize("搜索一下Python的最佳实践")
        self.assertEqual(intent.category, IntentCategory.SEARCH)
    
    def test_learn_from_feedback(self):
        """测试从反馈中学习"""
        # 初始模式数量
        initial_count = len(self.recognizer.intent_patterns)
        
        # 学习新意图模式
        self.recognizer.learn_from_feedback(
            user_input="帮我创建一个深度学习模型",
            interpreted_intent="code_implement",
            was_correct=True
        )
        
        # 验证模式已学习
        self.assertGreater(len(self.recognizer.intent_patterns), initial_count)
    
    def test_get_learned_patterns(self):
        """测试获取已学习的模式"""
        # 先学习一些模式
        self.recognizer.learn_from_feedback(
            user_input="写一个排序算法",
            interpreted_intent="code_implement",
            was_correct=True
        )
        
        patterns = self.recognizer.get_learned_patterns()
        self.assertGreater(len(patterns), 0)


if __name__ == "__main__":
    unittest.main()
