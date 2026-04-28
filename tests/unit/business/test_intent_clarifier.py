"""
单元测试：IntentClarifier 自适应意图澄清
测试自适应澄清策略和学习功能
"""

import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "client" / "src"))

from business.hermes_agent.intent_clarifier import AdaptiveClarifier, ClarificationResult, ClarificationStrategy
from business.hermes_agent.intent_recognizer import Intent


class TestAdaptiveClarifier(unittest.TestCase):
    """测试 AdaptiveClarifier 类"""
    
    def setUp(self):
        """测试前准备"""
        self.clarifier = AdaptiveClarifier()
    
    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(len(self.clarifier.clarification_history), 0)
    
    def test_intent_structure(self):
        """测试 Intent 数据结构"""
        intent = Intent(
            raw_input="帮我实现一个函数",
            task_type="task",
            fields={"task_description": "实现函数"},
            confidence=0.9
        )
        self.assertEqual(intent.raw_input, "帮我实现一个函数")
        self.assertEqual(intent.task_type, "task")
        self.assertIn("task_description", intent.fields)
        self.assertEqual(intent.confidence, 0.9)
    
    def test_intent_missing_fields(self):
        """测试获取缺失字段"""
        intent = Intent(
            raw_input="搜索",
            task_type="search",
            fields={},
            confidence=0.5
        )
        missing = intent.get_missing_fields()
        self.assertIn("query", missing)
    
    def test_intent_known_fields(self):
        """测试获取已知字段"""
        intent = Intent(
            raw_input="搜索 Python",
            task_type="search",
            fields={"query": "Python", "limit": None, "offset": 10},
            confidence=0.7
        )
        known = intent.known_fields()
        self.assertEqual(known, {"query": "Python", "offset": 10})


class TestIntentRecognizer(unittest.TestCase):
    """测试 IntentRecognizer 类"""
    
    def test_intent_to_dict(self):
        """测试 Intent 序列化"""
        intent = Intent(
            raw_input="测试输入",
            task_type="test",
            fields={"key": "value"},
            confidence=0.8
        )
        result = intent.to_dict()
        self.assertEqual(result["raw_input"], "测试输入")
        self.assertEqual(result["task_type"], "test")
        self.assertEqual(result["fields"]["key"], "value")
        self.assertEqual(result["confidence"], 0.8)


if __name__ == "__main__":
    unittest.main()