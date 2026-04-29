"""
LivingTreeAI Incentive - 贡献证明与激励系统
=====================================

激励类型：
1. 虚拟积分 - 不可交易的贡献证明
2. 优先权 - 高贡献节点获得优先服务
3. 信誉值 - 影响任务分配权重
4. 荣誉勋章 - 社区认可

贡献度量：
- 在线时长
- 计算任务完成量
- 知识贡献质量
- 网络转发帮助

Author: Hermes Desktop Team
"""

import json
import time
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


class ContributionType(Enum):
    """贡献类型"""
    ONLINE_TIME = "online_time"           # 在线时长
    TASK_COMPLETION = "task_completion"  # 任务完成
    KNOWLEDGE_SHARE = "knowledge_share"   # 知识分享
    BANDWIDTH_DONATION = "bandwidth"      # 带宽贡献
    STORAGE_DONATION = "storage"          # 存储贡献
    COORDINATION = "coordination"         # 协调贡献


@dataclass
class ContributionRecord:
    """贡献记录"""
    record_id: str
    node_id: str
    contribution_type: ContributionType
    timestamp: float
    value: float                    # 贡献量
    weight: float = 1.0             # 权重
    verified: bool = True

    # 关联信息
    task_id: Optional[str] = None
    knowledge_id: Optional[str] = None

    # 积分
    points: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "node_id": self.node_id,
            "type": self.contribution_type.value,
            "timestamp": self.timestamp,
            "value": self.value,
            "weight": self.weight,
            "points": self.points,
            "task_id": self.task_id,
            "knowledge_id": self.knowledge_id,
        }


@dataclass
class NodeReputation:
    """节点信誉"""
    node_id: str

    # 历史贡献
    total_points: float = 0.0
    contribution_records: List[Dict] = field(default_factory=list)

    # 信誉评分（0-100）
    reputation_score: float = 50.0

    # 等级
    level: int = 1
    title: str = "新手"

    # 统计
    tasks_completed: int = 0
    knowledge_shared: int = 0
    online_hours: float = 0.0
    total_contributions: int = 0

    # 时间
    first_contribution: Optional[float] = None
    last_contribution: Optional[float] = None

    # 勋章
    badges: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "reputation_score": self.reputation_score,
            "level": self.level,
            "title": self.title,
            "total_points": self.total_points,
            "tasks_completed": self.tasks_completed,
            "knowledge_shared": self.knowledge_shared,
            "online_hours": self.online_hours,
            "badges": self.badges,
        }


class Badge(Enum):
    """勋章类型"""
    # 在线贡献
    EARLY_BIRD = ("early_bird", "早起鸟", "连续7天在线")
    NIGHT_OWL = ("night_owl", "夜猫子", "夜间在线超过100小时")
    ALWAYS_ONLINE = ("always_online", "永不掉线", "连续30天在线")

    # 任务贡献
    HARD_WORKER = ("hard_worker", "勤劳工人", "完成100个任务")
    TASK_MASTER = ("task_master", "任务大师", "完成1000个任务")

    # 知识贡献
    KNOWLEDGE_SHARER = ("knowledge_sharer", "知识分享者", "分享10条知识")
    WISDOM_KEEPER = ("wisdom_keeper", "智慧守护者", "分享100条知识")

    # 特殊贡献
    NETWORK_BUILDER = ("network_builder", "网络建设者", "帮助10个新节点加入")
    PEACEKEEPER = ("peacekeeper", "网络和平员", "成功转发100条消息")

    def __init__(self, code, name_cn, description):
        self.code = code
        self.name_cn = name_cn
        self.description = description


class IncentiveSystem:
    """
    激励系统管理器

    功能：
    - 贡献记录和积分
    - 信誉评分
    - 等级系统
    - 勋章颁发
    - 优先权分配
    """

    # 积分权重配置
    POINTS_CONFIG = {
        ContributionType.ONLINE_TIME: 1.0,       # 每小时1积分
        ContributionType.TASK_COMPLETION: 10.0, # 每个任务10积分
        ContributionType.KNOWLEDGE_SHARE: 5.0,  # 每条知识5积分
        ContributionType.BANDWIDTH_DONATION: 0.5,  # 每GB带宽0.5积分
        ContributionType.STORAGE_DONATION: 0.1,  # 每GB存储0.1积分
        ContributionType.COORDINATION: 3.0,      # 每次协调3积分
    }

    # 等级阈值
    LEVEL_THRESHOLDS = [
        0,      # 1级
        100,    # 2级
        500,    # 3级
        2000,   # 4级
        10000,  # 5级
        50000,  # 6级
        200000, # 7级
        1000000,# 8级
    ]

    # 等级名称
    LEVEL_TITLES = [
        "新手", "学徒", "贡献者", "达人", "专家",
        "大师", "传奇", "宗师"
    ]

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.records: List[ContributionRecord] = []
        self.node_reputations: Dict[str, NodeReputation] = {}

        # 今日统计
        self.today_contributions: Dict[str, float] = {}
        self.today_start: float = time.time()

    def record_contribution(
        self,
        node_id: str,
        contribution_type: ContributionType,
        value: float,
        task_id: str = None,
        knowledge_id: str = None,
        weight: float = 1.0,
    ) -> ContributionRecord:
        """记录贡献"""
        # 计算积分
        base_points = self.POINTS_CONFIG.get(contribution_type, 1.0)
        points = value * base_points * weight

        # 创建记录
        record = ContributionRecord(
            record_id=str(uuid.uuid4())[:12],
            node_id=node_id,
            contribution_type=contribution_type,
            timestamp=time.time(),
            value=value,
            weight=weight,
            points=points,
            task_id=task_id,
            knowledge_id=knowledge_id,
        )

        self.records.append(record)

        # 更新信誉
        self._update_reputation(node_id, record)

        # 检查勋章
        self._check_badges(node_id)

        return record

    def _update_reputation(self, node_id: str, record: ContributionRecord):
        """更新信誉"""
        if node_id not in self.node_reputations:
            self.node_reputations[node_id] = NodeReputation(node_id=node_id)

        rep = self.node_reputations[node_id]

        # 添加积分
        rep.total_points += record.points
        rep.total_contributions += 1
        rep.last_contribution = time.time()

        if not rep.first_contribution:
            rep.first_contribution = time.time()

        # 更新统计
        if record.contribution_type == ContributionType.TASK_COMPLETION:
            rep.tasks_completed += int(record.value)
        elif record.contribution_type == ContributionType.KNOWLEDGE_SHARE:
            rep.knowledge_shared += int(record.value)
        elif record.contribution_type == ContributionType.ONLINE_TIME:
            rep.online_hours += record.value

        # 重新计算信誉评分
        self._recalculate_score(node_id)

        # 检查升级
        self._check_level_up(node_id)

        # 记录历史
        rep.contribution_records.append(record.to_dict())

    def _recalculate_score(self, node_id: str):
        """重新计算信誉评分"""
        rep = self.node_reputations[node_id]

        # 基础评分：积分对数
        base_score = min(50, (rep.total_points ** 0.3) * 10)

        # 活跃度加成
        days_active = 1
        if rep.first_contribution:
            days_active = max(1, (time.time() - rep.first_contribution) / 86400)
        activity_bonus = min(20, days_active * 0.5)

        # 稳定性加成
        stability_bonus = min(15, rep.online_hours * 0.1)

        # 质量加成（基于成功率）
        quality_score = min(15, rep.tasks_completed * 0.1)

        rep.reputation_score = base_score + activity_bonus + stability_bonus + quality_score
        rep.reputation_score = min(100, max(0, rep.reputation_score))

    def _check_level_up(self, node_id: str):
        """检查升级"""
        rep = self.node_reputations[node_id]

        for i, threshold in enumerate(self.LEVEL_THRESHOLDS):
            if rep.total_points < threshold:
                rep.level = i + 1
                rep.title = self.LEVEL_TITLES[i]
                break
        else:
            rep.level = len(self.LEVEL_TITLES)
            rep.title = self.LEVEL_TITLES[-1]

    def _check_badges(self, node_id: str):
        """检查并颁发勋章"""
        rep = self.node_reputations.get(node_id)
        if not rep:
            return

        new_badges = []

        # 在线勋章
        if rep.online_hours >= 7200:  # 300天 * 24小时（简化）
            new_badges.append(Badge.ALWAYS_ONLINE.code)

        # 任务勋章
        if rep.tasks_completed >= 1000:
            new_badges.append(Badge.TASK_MASTER.code)
        elif rep.tasks_completed >= 100:
            new_badges.append(Badge.HARD_WORKER.code)

        # 知识勋章
        if rep.knowledge_shared >= 100:
            new_badges.append(Badge.WISDOM_KEEPER.code)
        elif rep.knowledge_shared >= 10:
            new_badges.append(Badge.KNOWLEDGE_SHARER.code)

        # 添加新勋章
        for badge in new_badges:
            if badge not in rep.badges:
                rep.badges.append(badge)
                logger.info(f"节点 {node_id} 获得勋章: {badge}")

    def get_reputation(self, node_id: str) -> Optional[NodeReputation]:
        """获取节点信誉"""
        return self.node_reputations.get(node_id)

    def get_priority_score(self, node_id: str) -> float:
        """
        获取优先级评分

        用于任务分配和资源调度的优先级计算
        """
        rep = self.node_reputations.get(node_id)
        if not rep:
            return 0.5  # 默认中等优先级

        # 信誉评分归一化到优先级
        return rep.reputation_score / 100.0

    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """获取贡献排行榜"""
        sorted_nodes = sorted(
            self.node_reputations.values(),
            key=lambda r: r.total_points,
            reverse=True
        )

        return [
            {
                "rank": i + 1,
                "node_id": rep.node_id,
                "title": rep.title,
                "level": rep.level,
                "total_points": rep.total_points,
                "reputation_score": rep.reputation_score,
                "tasks_completed": rep.tasks_completed,
                "knowledge_shared": rep.knowledge_shared,
                "badges": rep.badges,
            }
            for i, rep in enumerate(sorted_nodes[:limit])
        ]

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total_records = len(self.records)
        total_points = sum(r.points for r in self.records)

        # 按类型统计
        by_type = {}
        for record in self.records:
            ct = record.contribution_type.value
            by_type[ct] = by_type.get(ct, 0) + record.points

        return {
            "node_id": self.node_id,
            "total_records": total_records,
            "total_points": total_points,
            "tracked_nodes": len(self.node_reputations),
            "by_type": by_type,
            "leaderboard": self.get_leaderboard(5),
        }

    def export_record(self, record: ContributionRecord) -> Dict:
        """导出贡献记录"""
        return record.to_dict()

    def get_reputation_report(self, node_id: str) -> str:
        """生成信誉报告"""
        rep = self.node_reputations.get(node_id)
        if not rep:
            return f"节点 {node_id} 暂无信誉记录"

        return f"""
╔══════════════════════════════════════════════════╗
║           🌾 贡献者信誉报告 🌾                   ║
╠══════════════════════════════════════════════════╣
║  节点ID:     {rep.node_id:<35}║
║  等级:       Lv.{rep.level} {rep.title:<28}║
║  信誉评分:   {rep.reputation_score:.1f}/100                         ║
╠══════════════════════════════════════════════════╣
║  总积分:     {rep.total_points:<35.1f}║
║  贡献次数:   {rep.total_contributions:<35}║
╠══════════════════════════════════════════════════╣
║  📊 统计                                                    ║
║  已完成任务: {rep.tasks_completed:<35}║
║  分享知识:   {rep.knowledge_shared:<35}║
║  在线时长:   {rep.online_hours:.1f} 小时                        ║
╠══════════════════════════════════════════════════╣
║  🏅 勋章                                                    ║
{"║  " + ", ".join(rep.badges) if rep.badges else "║  暂无勋章":<64}║
╚══════════════════════════════════════════════════╝
"""


# 导入logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    # 测试激励系统
    incentive = IncentiveSystem("test_coordinator")

    # 模拟贡献
    nodes = ["node_001", "node_002", "node_003"]

    for node in nodes:
        # 在线贡献
        incentive.record_contribution(
            node, ContributionType.ONLINE_TIME, 10.0  # 10小时
        )

        # 任务贡献
        for i in range(5):
            incentive.record_contribution(
                node, ContributionType.TASK_COMPLETION, 1.0
            )

        # 知识贡献
        incentive.record_contribution(
            node, ContributionType.KNOWLEDGE_SHARE, 3.0
        )

    # 打印排行榜
    print("\n排行榜:")
    for entry in incentive.get_leaderboard():
        print(f"  #{entry['rank']} {entry['node_id']}: {entry['total_points']:.1f}分 ({entry['title']})")

    # 打印信誉报告
    print(incentive.get_reputation_report("node_001"))
