#!/usr/bin/env python3
"""
Phase 2+3 整合测试
测试意图缓存、多代理、领域面板的集成

Author: LivingTreeAI Team
Version: 1.0.0
"""

import unittest
import time
import threading
from typing import Any, Dict

# 导入待测试模块
from client.src.business.intent_engine.intent_cache import (
    IntentCache,
    CacheStrategy,
    CacheStats,
    compute_intent_key,
    get_intent_cache,
    cached_intent,
)
from core.agent.orchestration_viewer import (
    AgentOrchestrationViewer,
    NodeStatus,
    OrchestrationNode,
)
from client.src.presentation.panels.finance_hub_panel import (
    FinanceHubPanel,
    DashboardWidget,
    InvestmentWidget,
    PaymentWidget,
    CreditWidget,
    PanelTab,
)
from client.src.presentation.panels.game_hub_panel import (
    GameHubPanel,
    GameLibraryWidget,
    SessionTrackerWidget,
    AchievementWidget,
    Game,
    GameStatus,
    Achievement,
    AchievementType,
)


class TestIntentCache(unittest.TestCase):
    """测试意图缓存"""
    
    def test_cache_basic_operations(self):
        """测试基本缓存操作"""
        cache = IntentCache(max_size=10)
        
        # 设置和获取
        cache.set("key1", "value1")
        self.assertEqual(cache.get("key1"), "value1")
        
        # 不存在的键
        self.assertIsNone(cache.get("nonexistent"))
        self.assertEqual(cache.get("nonexistent", "default"), "default")
        
        # 删除
        cache.delete("key1")
        self.assertIsNone(cache.get("key1"))
    
    def test_cache_eviction(self):
        """测试缓存驱逐"""
        cache = IntentCache(max_size=3, strategy=CacheStrategy.LRU)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        # 添加新键，触发驱逐
        cache.set("key4", "value4")
        
        # key1应该被驱逐
        self.assertIsNone(cache.get("key1"))
        self.assertIsNotNone(cache.get("key4"))
    
    def test_cache_ttl(self):
        """测试TTL过期"""
        cache = IntentCache(default_ttl=0.1)  # 100ms
        
        cache.set("key1", "value1")
        self.assertEqual(cache.get("key1"), "value1")
        
        # 等待过期
        time.sleep(0.15)
        
        self.assertIsNone(cache.get("key1"))
    
    def test_cache_stats(self):
        """测试缓存统计"""
        cache = IntentCache()
        
        cache.set("key1", "value1")
        
        # 命中
        self.assertEqual(cache.get("key1"), "value1")
        self.assertEqual(cache.get("key1"), "value1")
        
        # 未命中
        cache.get("nonexistent")
        
        stats = cache.get_stats()
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 2/3, places=2)
    
    def test_cache_thread_safety(self):
        """测试线程安全"""
        cache = IntentCache(max_size=100)
        
        def worker(n: int):
            for i in range(50):
                cache.set(f"key_{n}_{i}", f"value_{n}_{i}")
                cache.get(f"key_{n}_{i}")
        
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 所有操作应该成功完成
        self.assertGreater(len(cache), 0)


class TestAgentOrchestrationViewer(unittest.TestCase):
    """测试代理编排可视化"""
    
    def test_workflow_initialization(self):
        """测试工作流初始化"""
        viewer = AgentOrchestrationViewer()
        viewer.initialize_workflow("test_workflow")
        
        stats = viewer.get_workflow_stats()
        self.assertEqual(stats["workflow_id"], "test_workflow")
        self.assertEqual(stats["total_nodes"], 0)
    
    def test_add_nodes_and_edges(self):
        """测试添加节点和边"""
        viewer = AgentOrchestrationViewer()
        viewer.initialize_workflow("test_workflow")
        
        viewer.add_node("node1", "Agent 1", "planner")
        viewer.add_node("node2", "Agent 2", "coder")
        viewer.add_node("node3", "Agent 3", "reviewer")
        
        viewer.add_edge("node1", "node2")
        viewer.add_edge("node2", "node3")
        
        self.assertEqual(len(viewer), 3)
        
        stats = viewer.get_workflow_stats()
        self.assertEqual(stats["total_nodes"], 3)
    
    def test_node_status_update(self):
        """测试节点状态更新"""
        viewer = AgentOrchestrationViewer()
        viewer.initialize_workflow("test_workflow")
        
        viewer.add_node("node1", "Agent 1", "planner")
        
        # 更新状态
        viewer.update_node_status("node1", NodeStatus.RUNNING)
        
        snapshot = viewer.get_latest_snapshot()
        self.assertEqual(snapshot.nodes["node1"].status, NodeStatus.RUNNING)
        
        viewer.update_node_status("node1", NodeStatus.SUCCESS)
        
        stats = viewer.get_workflow_stats()
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["progress"], "100.0%")
    
    def test_snapshot_save(self):
        """测试快照保存"""
        viewer = AgentOrchestrationViewer()
        viewer.initialize_workflow("test_workflow")
        
        viewer.add_node("node1", "Agent 1", "planner")
        viewer.save_snapshot("Initial state")
        
        viewer.update_node_status("node1", NodeStatus.RUNNING)
        viewer.save_snapshot("Running")
        
        self.assertEqual(len(viewer._snapshots), 2)
        self.assertEqual(viewer._snapshots[0].message, "Initial state")
    
    def test_graph_data_export(self):
        """测试图形数据导出"""
        viewer = AgentOrchestrationViewer()
        viewer.initialize_workflow("test_workflow")
        
        viewer.add_node("node1", "Agent 1", "planner")
        viewer.add_node("node2", "Agent 2", "coder")
        viewer.add_edge("node1", "node2")
        
        graph_data = viewer.get_graph_data()
        
        self.assertIn("nodes", graph_data)
        self.assertIn("edges", graph_data)
        self.assertEqual(len(graph_data["nodes"]), 2)
        self.assertEqual(len(graph_data["edges"]), 1)


class TestFinanceHubPanel(unittest.TestCase):
    """测试金融面板"""
    
    def test_dashboard_widget(self):
        """测试总览组件"""
        dashboard = DashboardWidget()
        
        dashboard.total_assets = 100000.0
        dashboard.total_liabilities = 20000.0
        dashboard.assets_breakdown = {
            "股票": 50000.0,
            "债券": 30000.0,
            "现金": 20000.0,
        }
        
        summary = dashboard.get_summary()
        self.assertEqual(summary.total_assets, 100000.0)
        self.assertEqual(summary.net_assets, 80000.0)
    
    def test_investment_widget(self):
        """测试投资组件"""
        from client.src.presentation.panels.finance_hub_panel import InvestmentPosition
        
        investment = InvestmentWidget()
        
        pos = InvestmentPosition(
            symbol="AAPL",
            name="Apple Inc.",
            quantity=100,
            cost=150.0,
            current_price=175.0,
            market_value=17500.0,
            profit_loss=2500.0,
            profit_loss_rate=16.67,
        )
        
        investment.add_position(pos)
        
        self.assertEqual(len(investment.positions), 1)
        self.assertEqual(investment.get_total_market_value(), 17500.0)
        self.assertEqual(investment.get_total_profit_loss(), 2500.0)
    
    def test_payment_widget(self):
        """测试支付组件"""
        payment = PaymentWidget()
        payment.balance = 10000.0
        
        # 存款
        txn = payment.deposit(5000.0, "bank")
        self.assertEqual(txn.type, "deposit")
        self.assertEqual(payment.balance, 15000.0)
        
        # 取款
        txn = payment.withdraw(2000.0)
        self.assertIsNotNone(txn)
        self.assertEqual(payment.balance, 13000.0)
        
        # 转账
        txn = payment.transfer("user123", 1000.0)
        self.assertIsNotNone(txn)
        self.assertEqual(payment.balance, 12000.0)
    
    def test_credit_widget(self):
        """测试积分组件"""
        credit = CreditWidget()
        
        credit.add_credits(100, "login", "每日登录")
        credit.add_credits(50, "task", "完成任务")
        
        self.assertEqual(credit.total_credits, 150)
        
        # 扣除
        result = credit.deduct_credits(30, "兑换商品")
        self.assertTrue(result)
        self.assertEqual(credit.total_credits, 120)
        
        # 余额不足
        result = credit.deduct_credits(200, "兑换商品")
        self.assertFalse(result)
    
    def test_panel_integration(self):
        """测试面板集成"""
        panel = FinanceHubPanel()
        
        # 切换选项卡
        panel.switch_tab(PanelTab.INVESTMENT)
        self.assertEqual(panel.current_tab, PanelTab.INVESTMENT)
        
        # 获取组件
        investment = panel.get_widget(PanelTab.INVESTMENT)
        self.assertIsInstance(investment, InvestmentWidget)
        
        # 获取整体摘要
        summary = panel.get_overall_summary()
        self.assertIn("assets", summary)
        self.assertIn("investment", summary)
        self.assertIn("payment", summary)


class TestGameHubPanel(unittest.TestCase):
    """测试游戏面板"""
    
    def test_game_library(self):
        """测试游戏库"""
        library = GameLibraryWidget()
        
        game = Game(
            id="game1",
            name="Test Game",
            genre="RPG",
            platform="PC",
        )
        
        library.add_game(game)
        
        self.assertEqual(len(library.games), 1)
        self.assertEqual(library.get_game("game1").name, "Test Game")
        
        # 按类型查询
        rpg_games = library.get_games_by_genre("RPG")
        self.assertEqual(len(rpg_games), 1)
    
    def test_session_tracker(self):
        """测试会话跟踪"""
        tracker = SessionTrackerWidget()
        
        # 开始会话
        session = tracker.start_session("game1")
        self.assertIsNotNone(session)
        self.assertEqual(tracker.active_session.game_id, "game1")
        
        # 结束会话
        ended_session = tracker.end_session()
        self.assertIsNotNone(ended_session)
        self.assertIsNone(tracker.active_session)
        
        # 统计
        stats = tracker.get_session_stats()
        self.assertEqual(stats["total_sessions"], 1)
        self.assertGreater(stats["total_duration"], 0)
    
    def test_achievement_system(self):
        """测试成就系统"""
        achievements = AchievementWidget()
        
        achievement = Achievement(
            id="ach1",
            name="First Blood",
            description="完成第一场战斗",
            game_id="game1",
            achievement_type=AchievementType.STORY,
        )
        
        achievements.add_achievement(achievement)
        
        # 未解锁
        self.assertFalse(achievements.achievements["ach1"].unlocked)
        
        # 解锁
        achievements.unlock_achievement("ach1")
        self.assertTrue(achievements.achievements["ach1"].unlocked)
        
        # 进度
        progress = achievements.get_achievement_progress()
        self.assertEqual(progress["total"], 1)
        self.assertEqual(progress["unlocked"], 1)
        self.assertEqual(progress["progress"], 100.0)
    
    def test_panel_integration(self):
        """测试面板集成"""
        panel = GameHubPanel()
        
        # 添加游戏
        game = Game(
            id="game1",
            name="Test Game",
            genre="RPG",
            platform="PC",
        )
        panel.add_game(game)
        
        # 开始游戏
        panel.start_playing("game1")
        
        # 检查状态
        stats = panel.get_overall_stats()
        self.assertEqual(stats["library"]["total_games"], 1)
        
        # 停止游戏
        panel.stop_playing()
    
    def test_achievement_unlocked_event(self):
        """测试成就解锁事件"""
        panel = GameHubPanel()
        
        unlocked_events = []
        
        def on_unlock(data):
            unlocked_events.append(data)
        
        panel.on_event("achievement_unlocked", on_unlock)
        
        # 添加成就
        achievement = Achievement(
            id="ach1",
            name="First Blood",
            description="完成第一场战斗",
            game_id="game1",
            achievement_type=AchievementType.STORY,
        )
        panel.achievements.add_achievement(achievement)
        
        # 解锁
        panel.unlock_achievement("ach1")
        
        self.assertEqual(len(unlocked_events), 1)
        self.assertEqual(unlocked_events[0]["achievement_id"], "ach1")


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    
    suite = unittest.TestSuite()
    
    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestIntentCache))
    suite.addTests(loader.loadTestsFromTestCase(TestAgentOrchestrationViewer))
    suite.addTests(loader.loadTestsFromTestCase(TestFinanceHubPanel))
    suite.addTests(loader.loadTestsFromTestCase(TestGameHubPanel))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出摘要
    print("\n" + "="*60)
    print("测试摘要")
    print("="*60)
    print(f"运行测试: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
