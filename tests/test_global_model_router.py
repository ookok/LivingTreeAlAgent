"""
单元测试：GlobalModelRouter
"""

import unittest
from client.src.business.global_model_router import (
    GlobalModelRouter,
    ModelInfo,
    ModelBackend,
    ModelCapability,
    RoutingStrategy,
)


class TestGlobalModelRouter(unittest.TestCase):
    """测试 GlobalModelRouter"""

    def setUp(self):
        """设置测试环境"""
        self.router = GlobalModelRouter()

        # 添加测试模型
        self.router.models = {
            "test-ollama": ModelInfo(
                model_id="test-ollama",
                name="Test Ollama",
                backend=ModelBackend.OLLAMA,
                capabilities=[ModelCapability.CHAT, ModelCapability.REASONING],
                config={"url": "http://localhost:11434", "model": "qwen2.5"},
                is_available=True,
                quality_score=0.8,
                speed_score=0.6,
            ),
            "test-openai": ModelInfo(
                model_id="test-openai",
                name="Test OpenAI",
                backend=ModelBackend.OPENAI,
                capabilities=[ModelCapability.CHAT, ModelCapability.STREAMING],
                config={"base_url": "https://api.openai.com/v1", "api_key": "test"},
                is_available=True,
                quality_score=0.9,
                speed_score=0.9,
            ),
        }

    def test_route_auto(self):
        """测试自动路由"""
        model = self.router.route(ModelCapability.CHAT, RoutingStrategy.AUTO)
        self.assertIsNotNone(model)
        # AUTO 策略使用 TASK_STRATEGY_MAP，CHAT 默认用 BALANCED
        # BALANCED 综合评分，OpenAI quality=0.9, speed=0.9 应该更高
        self.assertEqual(model.model_id, "test-openai")

    def test_route_quality(self):
        """测试质量优先路由"""
        model = self.router.route(ModelCapability.CHAT, RoutingStrategy.QUALITY)
        self.assertIsNotNone(model)
        # QUALITY 策略选择 quality_score 最高的
        self.assertEqual(model.model_id, "test-openai")

    def test_route_nonexistent_capability(self):
        """测试不存在的能力"""
        model = self.router.route(ModelCapability.EMBEDDING, RoutingStrategy.AUTO)
        self.assertIsNone(model)

    def test_route_specific_model(self):
        """测试指定模型路由（直接访问）"""
        model = self.router.models.get("test-ollama")
        self.assertIsNotNone(model)
        self.assertEqual(model.model_id, "test-ollama")

    def test_get_stats(self):
        """测试获取统计信息"""
        stats = self.router.get_stats()
        self.assertEqual(stats["total_models"], 2)
        self.assertEqual(stats["available_models"], 2)

    def test_update_stats(self):
        """测试更新统计信息"""
        model = self.router.models["test-ollama"]
        self.assertEqual(model.success_rate, 1.0)
        model.update_stats(success=True, response_time=0.5)
        # success_rate 会变化（指数移动平均）
        self.assertLessEqual(model.success_rate, 1.0)
        self.assertGreaterEqual(model.success_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
