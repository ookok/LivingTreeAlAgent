"""
LivingTreeAI - 平民AI集群 主入口
=============================

使用方法:
    # 客户端模式
    python -m living_tree_ai.client

    # 服务器模式
    python -m living_tree_ai.server

Author: Hermes Desktop Team
"""

import asyncio
import argparse
import sys
from typing import Optional

# 尝试导入 PyQt6，如果不可用则使用 CLI 模式
try:
    from PyQt6.QtWidgets import QApplication
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False


class LivingTreeAIClient:
    """平民AI客户端"""

    def __init__(self):
        from .node import LivingTreeNode, NodeType
        from .network import P2PNetwork
        from .knowledge import KnowledgeBase, KnowledgeShare
        from .incentive import IncentiveSystem

        self.node = LivingTreeNode(
            node_type=NodeType.UNIVERSAL,
            specialization="",
        )
        self.network: Optional[P2PNetwork] = None
        self.knowledge_base = KnowledgeBase(self.node.node_id)
        self.knowledge_share = KnowledgeShare(self.knowledge_base, self.node.node_id)
        self.incentive = IncentiveSystem(self.node.node_id)

    async def start(self):
        """启动客户端"""
        print("正在启动平民AI客户端...")

        # 启动节点
        await self.node.start()

        # 启动网络
        self.network = P2PNetwork(self.node.node_id)
        await self.network.start()

        print(f"客户端已启动，节点ID: {self.node.node_id}")
        print("输入 'help' 查看可用命令")

        # CLI 主循环
        await self.cli_loop()

        # 清理
        await self.stop()

    async def stop(self):
        """停止客户端"""
        if self.network:
            await self.network.stop()
        await self.node.stop()
        print("客户端已停止")

    async def cli_loop(self):
        """命令行主循环"""
        while True:
            try:
                cmd = input("\n> ").strip()

                if not cmd:
                    continue

                elif cmd == "help":
                    self.print_help()

                elif cmd == "status":
                    self.show_status()

                elif cmd == "peers":
                    self.show_peers()

                elif cmd == "submit":
                    await self.submit_task()

                elif cmd == "tasks":
                    self.show_tasks()

                elif cmd == "knowledge":
                    self.show_knowledge()

                elif cmd == "contribution":
                    self.show_contribution()

                elif cmd == "quit":
                    break

                else:
                    print(f"未知命令: {cmd}")
                    print("输入 'help' 查看可用命令")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"错误: {e}")

    def print_help(self):
        """打印帮助"""
        print("""
可用命令:
  status      - 显示节点状态
  peers       - 显示连接的对等节点
  submit      - 提交新任务
  tasks       - 显示任务列表
  knowledge   - 显示知识库
  contribution - 显示贡献统计
  help        - 显示此帮助
  quit        - 退出程序
""")

    def show_status(self):
        """显示状态"""
        status = self.node.get_status()
        print(f"""
节点状态:
  节点ID:    {status['node_id']}
  状态:      {status['status']}
  类型:      {status['node_type']}
  特化:      {status['specialization']}
  在线时长:  {status['online_hours']:.2f} 小时
  已完成任务: {status['task_completed']}
  运行任务:  {status['running_tasks']}
  队列任务:  {status['queue_size']}
""")

    def show_peers(self):
        """显示对等节点"""
        if not self.network:
            print("网络未连接")
            return

        peers = self.network.get_peers()
        print(f"\n已连接 {len(peers)} 个节点:")
        for peer in peers:
            print(f"  - {peer['node_id']} @ {peer['address']} (延迟: {peer.get('latency_ms', 0):.0f}ms)")

    async def submit_task(self):
        """提交任务"""
        print("\n提交任务:")
        print("  类型: 1-推理, 2-训练, 3-存储, 4-协调")
        type_map = {"1": "inference", "2": "training", "3": "storage", "4": "coordination"}

        type_choice = input("选择类型 (1-4): ").strip()
        if type_choice not in type_map:
            print("无效选择")
            return

        task_type = type_map[type_choice]
        prompt = input("输入内容: ").strip()

        if not prompt:
            print("内容不能为空")
            return

        task_id = self.node.submit_task(
            task_type=task_type,
            input_data={"prompt": prompt},
            priority=1,
        )

        print(f"任务已提交: {task_id}")

    def show_tasks(self):
        """显示任务"""
        status = self.node.get_status()
        print(f"\n任务状态:")
        print(f"  运行中: {status['running_tasks']}")
        print(f"  队列中: {status['queue_size']}")

    def show_knowledge(self):
        """显示知识库"""
        stats = self.knowledge_base.get_stats()
        print(f"\n知识库统计:")
        print(f"  总条目: {stats.total_knowledge}")
        for kt, count in stats.by_type.items():
            print(f"    {kt}: {count}")

    def show_contribution(self):
        """显示贡献"""
        rep = self.incentive.get_reputation(self.node.node_id)
        if not rep:
            print("\n暂无贡献记录")
            return

        print(f"""
贡献统计:
  等级:      Lv.{rep.level} {rep.title}
  总积分:    {rep.total_points:.1f}
  信誉评分:  {rep.reputation_score:.1f}/100
  完成任务:  {rep.tasks_completed}
  分享知识:  {rep.knowledge_shared}
  在线时长:  {rep.online_hours:.1f} 小时
  勋章:      {', '.join(rep.badges) if rep.badges else '暂无'}
""")


class LivingTreeAIServer:
    """平民AI服务器（协调节点）"""

    def __init__(self):
        from .node import LivingTreeNode, NodeType
        from .network import P2PNetwork
        from .federation import FederatedLearning, FLConfig
        from .incentive import IncentiveSystem

        self.node = LivingTreeNode(
            node_type=NodeType.COORDINATOR,
            specialization="coordination",
        )
        self.network: Optional[P2PNetwork] = None
        self.fl: Optional[FederatedLearning] = None
        self.incentive = IncentiveSystem(self.node.node_id)

    async def start(self):
        """启动服务器"""
        print("正在启动平民AI服务器（协调节点）...")

        # 启动节点
        await self.node.start()

        # 启动网络
        self.network = P2PNetwork(self.node.node_id)
        await self.network.start()

        # 启动联邦学习（可选）
        print("\n是否启动联邦学习？ (y/n)")
        if input("> ").strip().lower() == 'y':
            config = FLConfig()
            self.fl = FederatedLearning(config, self.node.node_id, self.network)
            print("联邦学习系统已启动")

        print(f"\n服务器已启动，节点ID: {self.node.node_id}")
        print("输入 'help' 查看可用命令")

        await self.cli_loop()
        await self.stop()

    async def stop(self):
        """停止服务器"""
        if self.fl:
            await self.fl.stop_fl()
        if self.network:
            await self.network.stop()
        await self.node.stop()
        print("服务器已停止")

    async def cli_loop(self):
        """命令行主循环"""
        while True:
            try:
                cmd = input("\n> ").strip()

                if not cmd:
                    continue

                elif cmd == "help":
                    self.print_help()

                elif cmd == "status":
                    self.show_status()

                elif cmd == "peers":
                    self.show_peers()

                elif cmd == "leaderboard":
                    self.show_leaderboard()

                elif cmd == "fl start":
                    await self.start_fl()

                elif cmd == "fl status":
                    self.show_fl_status()

                elif cmd == "quit":
                    break

                else:
                    print(f"未知命令: {cmd}")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"错误: {e}")

    def print_help(self):
        """打印帮助"""
        print("""
可用命令:
  status       - 显示服务器状态
  peers        - 显示连接节点
  leaderboard  - 显示贡献排行榜
  fl start     - 启动联邦学习
  fl status    - 显示FL状态
  help         - 显示此帮助
  quit         - 退出程序
""")

    def show_status(self):
        """显示状态"""
        status = self.node.get_status()
        network_stats = self.network.get_network_stats() if self.network else {}
        print(f"""
服务器状态:
  节点ID:    {status['node_id']}
  状态:      {status['status']}
  连接节点:  {network_stats.get('peer_count', 0)}
  已完成任务: {status['task_completed']}
""")

    def show_peers(self):
        """显示节点"""
        if not self.network:
            return

        peers = self.network.get_peers()
        print(f"\n已连接 {len(peers)} 个节点:")
        for peer in peers:
            print(f"  - {peer['node_id']} @ {peer['address']}")

    def show_leaderboard(self):
        """显示排行榜"""
        leaderboard = self.incentive.get_leaderboard(10)
        print("\n贡献排行榜 TOP 10:")
        for entry in leaderboard:
            print(f"  #{entry['rank']} {entry['node_id']}: {entry['total_points']:.0f}分 ({entry['title']})")

    async def start_fl(self):
        """启动联邦学习"""
        if not self.fl:
            print("联邦学习系统未初始化")
            return

        print("启动联邦学习（共10轮）...")
        await self.fl.start_fl(num_rounds=10)
        print("联邦学习完成")

    def show_fl_status(self):
        """显示FL状态"""
        if not self.fl:
            print("联邦学习系统未初始化")
            return

        stats = self.fl.get_stats()
        print(f"\n联邦学习状态:")
        print(f"  总轮次: {stats['total_rounds']}")
        print(f"  当前阶段: {stats['current_phase']}")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="平民AI集群")
    parser.add_argument(
        "mode",
        nargs="?",
        default="client",
        choices=["client", "server"],
        help="运行模式: client 或 server"
    )
    parser.add_argument("--node-type", "-t", help="节点类型")
    parser.add_argument("--specialization", "-s", help="专业领域")

    args = parser.parse_args()

    # 选择运行模式
    if args.mode == "client":
        app = LivingTreeAIClient()
    else:
        app = LivingTreeAIServer()

    # 运行
    try:
        asyncio.run(app.start())
    except KeyboardInterrupt:
        print("\n已退出")


if __name__ == "__main__":
    main()
