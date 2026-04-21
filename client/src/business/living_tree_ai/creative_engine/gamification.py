"""
游戏化与三维创作空间 (Creative Gamification)
===========================================

核心理念：将创作"空间化"，让枯燥的生产力工具变得直观和沉浸。

功能：
1. 三维思维导图：创作大纲悬浮在 3D 空间中，AI 自动整理节点逻辑
2. 语音驱动创作：在 VR/3D 界面中通过语音与 AI 实时对话
3. 进度可视化：长篇创作被可视化为"关卡地图"
4. 成就系统：创作里程碑成就
5. 协作空间：多人实时协作的虚拟创作室
"""

import asyncio
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class SpaceType(Enum):
    """空间类型"""
    MIND_MAP = "mind_map"           # 思维导图空间
    STORY_MAP = "story_map"         # 故事地图（长篇创作）
    CODE_UNIVERSE = "code_universe" # 代码宇宙
    COLLABORATIVE_ROOM = "collab_room"  # 协作房间
    ACHIEVEMENT_HALL = "achievement_hall"  # 成就大厅


class NodeType(Enum):
    """节点类型（用于思维导图）"""
    IDEA = "idea"                   # 创意节点
    TASK = "task"                   # 任务节点
    MILESTONE = "milestone"         # 里程碑
    REFERENCE = "reference"         # 引用节点
    AI_SUGGESTION = "ai_suggestion" # AI 建议
    COMMENT = "comment"             # 评论


@dataclass
class CreativeNode:
    """创作空间中的节点"""
    node_id: str
    node_type: NodeType
    title: str
    content: str = ""
    position_3d: tuple[float, float, float] = (0, 0, 0)  # x, y, z 坐标
    color: str = "#4A90D9"          # 节点颜色
    size: float = 1.0               # 节点大小
    connections: list[str] = field(default_factory=list)  # 连接的节点 ID
    parent_id: Optional[str] = None
    children_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    author_id: str = "local"
    status: str = "active"          # active/completed/archived


@dataclass
class Achievement:
    """成就"""
    achievement_id: str
    name: str
    description: str
    icon: str                       # emoji 或图标
    category: str                   # 创作/协作/学习
    requirement: dict               # 解锁条件
    reward_points: int = 0          # 奖励积分
    unlocked_at: Optional[datetime] = None
    progress: float = 0            # 当前进度 0-1
    secret: bool = False            # 是否是隐藏成就


@dataclass
class CreativeSpace:
    """创作空间"""
    space_id: str
    space_type: SpaceType
    name: str
    owner_id: str
    nodes: list[CreativeNode] = field(default_factory=list)
    connections: list[tuple[str, str]] = field(default_factory=list)  # (node_a, node_b)
    achievements: list[str] = field(default_factory=list)  # 已解锁成就 ID
    total_points: int = 0           # 总积分
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field=field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
    collaborators: list[str] = field(default_factory=list)  # 协作者
    is_public: bool = False


class CreativeGamification:
    """
    创作游戏化系统

    用法:
        gamification = CreativeGamification()

        # 创建思维导图空间
        space = await gamification.create_space(
            name="分布式系统设计",
            space_type=SpaceType.MIND_MAP
        )

        # 添加节点
        root = await gamification.add_node(
            space_id=space.space_id,
            node_type=NodeType.IDEA,
            title="分布式系统概述",
            content="包含一致性、可用性、分区容错性..."
        )

        child = await gamification.add_node(
            space_id=space.space_id,
            node_type=NodeType.TASK,
            title="一致性方案",
            parent_id=root.node_id
        )

        # AI 自动整理
        await gamification.auto_organize(space.space_id)

        # 导出为 3D 可视化
        visualization = gamification.export_3d_visualization(space.space_id)
    """

    def __init__(self, data_dir: str = "./data/creative"):
        self.data_dir = data_dir
        self._spaces: dict[str, CreativeSpace] = {}
        self._achievements: dict[str, Achievement] = {}
        self._user_points: dict[str, int] = {}  # user_id -> points
        self._voice_handler: Optional[Callable] = None
        self._3d_renderer: Optional[Callable] = None

        # 存储路径
        self._spaces_dir = os.path.join(data_dir, "spaces")
        self._achievements_file = os.path.join(data_dir, "achievements.json")
        os.makedirs(self._spaces_dir, exist_ok=True)

        # 加载数据
        self._load_achievements()
        self._load_spaces()

        # 初始化内置成就
        self._init_builtin_achievements()

    def set_voice_handler(self, handler: Callable) -> None:
        """设置语音处理器"""
        self._voice_handler = handler

    def set_3d_renderer(self, renderer: Callable) -> None:
        """设置 3D 渲染器"""
        self._3d_renderer = renderer

    def _init_builtin_achievements(self) -> None:
        """初始化内置成就"""
        builtin_achievements = [
            Achievement(
                achievement_id="first_node",
                name="🌱 种下创意",
                description="创建你的第一个思维节点",
                icon="🌱",
                category="创作",
                requirement={"type": "create_node", "count": 1},
                reward_points=10
            ),
            Achievement(
                achievement_id="mind_map_master",
                name="🧠 思维大师",
                description="创建包含 50+ 节点的思维导图",
                icon="🧠",
                category="创作",
                requirement={"type": "create_node", "count": 50},
                reward_points=500
            ),
            Achievement(
                achievement_id="collaborator",
                name="🤝 协作达人",
                description="与 3 个不同协作者共同创作",
                icon="🤝",
                category="协作",
                requirement={"type": "add_collaborator", "count": 3},
                reward_points=200
            ),
            Achievement(
                achievement_id="ai_partner",
                name="🤖 AI 伙伴",
                description="AI 建议被采纳 20 次",
                icon="🤖",
                category="创作",
                requirement={"type": "ai_suggestion_accepted", "count": 20},
                reward_points=300
            ),
            Achievement(
                achievement_id="story_teller",
                name="📖 故事大王",
                description="完成一个包含 100+ 节点的故事地图",
                icon="📖",
                category="创作",
                requirement={"type": "space_type", "space_type": "story_map", "node_count": 100},
                reward_points=1000
            ),
            Achievement(
                achievement_id="voice_commander",
                name="🎤 语音指挥官",
                description="使用语音命令创建 10 个节点",
                icon="🎤",
                category="协作",
                requirement={"type": "voice_command", "count": 10},
                reward_points=150
            ),
            Achievement(
                achievement_id="milestone_reacher",
                name="🏆 里程碑达成者",
                description="完成 10 个里程碑节点",
                icon="🏆",
                category="创作",
                requirement={"type": "complete_milestone", "count": 10},
                reward_points=400
            ),
            Achievement(
                achievement_id="explorer",
                name="🧭 探索者",
                description="访问 5 个不同的创作空间",
                icon="🧭",
                category="学习",
                requirement={"type": "visit_space", "count": 5},
                reward_points=100
            ),
        ]

        for achievement in builtin_achievements:
            self._achievements[achievement.achievement_id] = achievement

    async def create_space(
        self,
        name: str,
        space_type: SpaceType,
        owner_id: str = "local",
        metadata: dict = None
    ) -> CreativeSpace:
        """
        创建创作空间

        Args:
            name: 空间名称
            space_type: 空间类型
            owner_id: 所有者 ID
            metadata: 额外元数据

        Returns:
            CreativeSpace: 创建的空间
        """
        space_id = hashlib.sha256(f"{name}{time.time()}".encode()).hexdigest()[:12]

        space = CreativeSpace(
            space_id=space_id,
            space_type=space_type,
            name=name,
            owner_id=owner_id,
            metadata=metadata or {},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        self._spaces[space_id] = space
        await self._save_space(space)

        # 触发成就检查
        await self._check_achievements(owner_id, "create_space", {"space_id": space_id})

        return space

    async def add_node(
        self,
        space_id: str,
        node_type: NodeType,
        title: str,
        content: str = "",
        parent_id: str = None,
        position_3d: tuple[float, float, float] = None,
        author_id: str = "local"
    ) -> Optional[CreativeNode]:
        """
        添加节点到空间

        Args:
            space_id: 空间 ID
            node_type: 节点类型
            title: 节点标题
            content: 节点内容
            parent_id: 父节点 ID
            position_3d: 3D 位置
            author_id: 作者 ID

        Returns:
            CreativeNode: 创建的节点
        """
        space = self._spaces.get(space_id)
        if not space:
            return None

        node_id = hashlib.sha256(f"{title}{time.time()}".encode()).hexdigest()[:12]

        # 计算位置
        if position_3d is None:
            if parent_id:
                # 在父节点附近
                parent = next((n for n in space.nodes if n.node_id == parent_id), None)
                if parent:
                    position_3d = (
                        parent.position_3d[0] + 2,
                        parent.position_3d[1] + 1,
                        parent.position_3d[2]
                    )
                else:
                    position_3d = (0, 0, 0)
            else:
                # 根节点，使用已有节点的数量决定位置
                position_3d = (len(space.nodes) * 1.5, 0, 0)

        # 确定颜色
        color_map = {
            NodeType.IDEA: "#4A90D9",
            NodeType.TASK: "#50C878",
            NodeType.MILESTONE: "#FFD700",
            NodeType.REFERENCE: "#9B59B6",
            NodeType.AI_SUGGESTION: "#E74C3C",
            NodeType.COMMENT: "#95A5A6",
        }
        color = color_map.get(node_type, "#4A90D9")

        node = CreativeNode(
            node_id=node_id,
            node_type=node_type,
            title=title,
            content=content,
            position_3d=position_3d,
            color=color,
            parent_id=parent_id,
            author_id=author_id
        )

        space.nodes.append(node)

        # 更新父节点的 children_ids
        if parent_id:
            for n in space.nodes:
                if n.node_id == parent_id:
                    n.children_ids.append(node_id)
                    break

        space.updated_at = datetime.now()
        await self._save_space(space)

        # 触发成就检查
        await self._check_achievements(author_id, "create_node", {
            "space_id": space_id,
            "node_id": node_id
        })

        return node

    async def update_node(
        self,
        space_id: str,
        node_id: str,
        updates: dict
    ) -> Optional[CreativeNode]:
        """更新节点"""
        space = self._spaces.get(space_id)
        if not space:
            return None

        node = next((n for n in space.nodes if n.node_id == node_id), None)
        if not node:
            return None

        # 应用更新
        for key, value in updates.items():
            if hasattr(node, key):
                setattr(node, key, value)

        node.updated_at = datetime.now()
        space.updated_at = datetime.now()

        await self._save_space(space)
        return node

    async def delete_node(self, space_id: str, node_id: str) -> bool:
        """删除节点及其子节点"""
        space = self._spaces.get(space_id)
        if not space:
            return False

        # 递归收集所有要删除的节点
        def collect_descendants(node_id: str) -> list[str]:
            descendants = [node_id]
            for node in space.nodes:
                if node.parent_id == node_id:
                    descendants.extend(collect_descendants(node.node_id))
            return descendants

        to_delete = set(collect_descendants(node_id))

        # 移除节点
        space.nodes = [n for n in space.nodes if n.node_id not in to_delete]
        space.updated_at = datetime.now()

        # 重新构建父子关系
        for node in space.nodes:
            node.children_ids = [c for c in node.children_ids if c not in to_delete]

        await self._save_space(space)
        return True

    async def auto_organize(self, space_id: str) -> dict:
        """
        AI 自动整理空间布局

        Args:
            space_id: 空间 ID

        Returns:
            dict: 整理报告
        """
        space = self._spaces.get(space_id)
        if not space:
            return {"success": False, "error": "Space not found"}

        report = {
            "added_connections": 0,
            "repositioned_nodes": 0,
            "suggestions": []
        }

        # 1. 建立相关节点之间的连接
        for i, node_a in enumerate(space.nodes):
            for node_b in space.nodes[i+1:]:
                # 检测相似性（简单的关键词匹配）
                common_words = set(node_a.title.split()) & set(node_b.title.split())
                if len(common_words) >= 2:
                    if node_b.node_id not in node_a.connections:
                        node_a.connections.append(node_b.node_id)
                        report["added_connections"] += 1

        # 2. 自动布局（简单的树形布局）
        root_nodes = [n for n in space.nodes if n.parent_id is None]

        def layout_tree(node: CreativeNode, depth: int = 0, index: int = 0) -> None:
            node.position_3d = (depth * 3, index * 2, 0)
            report["repositioned_nodes"] += 1

            children = [n for n in space.nodes if n.parent_id == node.node_id]
            for i, child in enumerate(children):
                layout_tree(child, depth + 1, i)

        for i, root in enumerate(root_nodes):
            layout_tree(root, 0, i)

        # 3. 生成建议
        suggestions = []
        if len(space.nodes) < 5:
            suggestions.append("💡 建议添加更多节点来丰富你的思维导图")
        if not any(n.node_type == NodeType.MILESTONE for n in space.nodes):
            suggestions.append("🎯 建议添加里程碑节点来标记重要进度")
        if len(root_nodes) > 5:
            suggestions.append("🔄 建议将相关根节点合并到一个主题下")

        report["suggestions"] = suggestions
        space.updated_at = datetime.now()

        await self._save_space(space)
        return report

    async def voice_command(
        self,
        space_id: str,
        command: str,
        user_id: str = "local"
    ) -> dict:
        """
        处理语音命令

        Args:
            space_id: 空间 ID
            command: 语音命令文本
            user_id: 用户 ID

        Returns:
            dict: 执行结果
        """
        command = command.lower()

        # 简单命令解析
        result = {"success": False, "message": "", "action": None}

        if any(kw in command for kw in ["添加", "add", "新建", "create"]):
            # 提取标题
            title = command.replace("添加节点", "").replace("add node", "").strip()
            if not title:
                title = "新节点"

            node = await self.add_node(
                space_id=space_id,
                node_type=NodeType.TASK,
                title=title,
                author_id=user_id
            )
            result = {
                "success": True,
                "message": f"✅ 已添加节点：{title}",
                "action": {"type": "add_node", "node": node}
            }

        elif any(kw in command for kw in ["删除", "delete", "移除", "remove"]):
            # 获取要删除的节点
            space = self._spaces.get(space_id)
            if space and space.nodes:
                last_node = space.nodes[-1]
                await self.delete_node(space_id, last_node.node_id)
                result = {
                    "success": True,
                    "message": f"✅ 已删除节点：{last_node.title}",
                    "action": {"type": "delete_node", "node_id": last_node.node_id}
                }

        elif any(kw in command for kw in ["整理", "organize", "优化"]):
            report = await self.auto_organize(space_id)
            result = {
                "success": True,
                "message": f"✅ 已整理空间，添加了 {report['added_connections']} 个连接",
                "action": {"type": "organize", "report": report}
            }

        elif any(kw in command for kw in ["完成", "done", "finish"]):
            # 标记最后一个节点为完成
            space = self._spaces.get(space_id)
            if space and space.nodes:
                last_node = space.nodes[-1]
                await self.update_node(space_id, last_node.node_id, {"status": "completed"})
                result = {
                    "success": True,
                    "message": f"✅ 已标记完成：{last_node.title}",
                    "action": {"type": "complete_node", "node_id": last_node.node_id}
                }

        # 触发语音命令成就
        if result["success"]:
            await self._check_achievements(user_id, "voice_command", {})

        return result

    async def check_and_unlock_achievements(
        self,
        user_id: str,
        trigger_type: str,
        trigger_data: dict
    ) -> list[Achievement]:
        """
        检查并解锁成就

        Args:
            user_id: 用户 ID
            trigger_type: 触发类型
            trigger_data: 触发数据

        Returns:
            list[Achievement]: 新解锁的成就
        """
        unlocked = []

        for achievement in self._achievements.values():
            if achievement.unlocked_at:
                continue  # 已解锁

            requirement = achievement.requirement
            if requirement.get("type") != trigger_type:
                continue

            progress = 0
            should_unlock = False

            if trigger_type == "create_node":
                progress = 1  # 简化处理
                should_unlock = progress >= requirement.get("count", 1)

            elif trigger_type == "voice_command":
                # 累积计数
                key = f"voice_command_{user_id}"
                count = getattr(self, key, 0) + 1
                setattr(self, key, count)
                progress = count / requirement.get("count", 10)
                should_unlock = progress >= 1

            # 更新进度
            achievement.progress = min(1.0, progress)

            if should_unlock:
                achievement.unlocked_at = datetime.now()
                self._user_points[user_id] = self._user_points.get(user_id, 0) + achievement.reward_points
                unlocked.append(achievement)

                # 保存
                await self._save_achievements()

        return unlocked

    async def _check_achievements(self, user_id: str, trigger_type: str, data: dict) -> None:
        """内部成就检查"""
        await self.check_and_unlock_achievements(user_id, trigger_type, data)

    def export_3d_visualization(self, space_id: str) -> dict:
        """
        导出 3D 可视化数据

        Args:
            space_id: 空间 ID

        Returns:
            dict: 3D 可视化数据
        """
        space = self._spaces.get(space_id)
        if not space:
            return {"success": False, "error": "Space not found"}

        # 构建 Three.js 兼容的数据
        visualization = {
            "success": True,
            "space_id": space_id,
            "space_name": space.name,
            "nodes": [
                {
                    "id": node.node_id,
                    "type": node.node_type.value,
                    "title": node.title,
                    "content": node.content,
                    "position": {
                        "x": node.position_3d[0],
                        "y": node.position_3d[1],
                        "z": node.position_3d[2]
                    },
                    "color": node.color,
                    "size": node.size,
                    "status": node.status
                }
                for node in space.nodes
            ],
            "connections": [
                {"from": conn[0], "to": conn[1]}
                for conn in space.connections
            ],
            "node_connections": [
                {"from": node.node_id, "to": child_id}
                for node in space.nodes
                for child_id in node.children_ids
            ],
            "metadata": {
                "total_nodes": len(space.nodes),
                "total_points": space.total_points,
                "space_type": space.space_type.value
            }
        }

        # 如果有自定义渲染器，使用它
        if self._3d_renderer:
            visualization["render_data"] = self._3d_renderer(space)

        return visualization

    def get_space_summary(self, space_id: str) -> dict:
        """获取空间摘要"""
        space = self._spaces.get(space_id)
        if not space:
            return {"success": False}

        by_type = {}
        by_status = {}

        for node in space.nodes:
            by_type[node.node_type.value] = by_type.get(node.node_type.value, 0) + 1
            by_status[node.status] = by_status.get(node.status, 0) + 1

        return {
            "success": True,
            "space_id": space_id,
            "name": space.name,
            "space_type": space.space_type.value,
            "total_nodes": len(space.nodes),
            "by_type": by_type,
            "by_status": by_status,
            "collaborators": space.collaborators,
            "achievements": space.achievements,
            "total_points": space.total_points,
            "updated_at": space.updated_at.isoformat()
        }

    def get_leaderboard(self, limit: int = 10) -> list[dict]:
        """获取积分排行榜"""
        sorted_users = sorted(
            self._user_points.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [
            {"user_id": user_id, "points": points, "rank": i + 1}
            for i, (user_id, points) in enumerate(sorted_users[:limit])
        ]

    async def _save_space(self, space: CreativeSpace) -> None:
        """保存空间到本地"""
        try:
            filepath = os.path.join(self._spaces_dir, f"{space.space_id}.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    "space_id": space.space_id,
                    "space_type": space.space_type.value,
                    "name": space.name,
                    "owner_id": space.owner_id,
                    "nodes": [
                        {
                            **vars(node),
                            "created_at": node.created_at.isoformat(),
                            "updated_at": node.updated_at.isoformat(),
                            "position_3d": list(node.position_3d)
                        }
                        for node in space.nodes
                    ],
                    "connections": space.connections,
                    "achievements": space.achievements,
                    "total_points": space.total_points,
                    "created_at": space.created_at.isoformat(),
                    "updated_at": space.updated_at.isoformat(),
                    "metadata": space.metadata,
                    "collaborators": space.collaborators,
                    "is_public": space.is_public
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CreativeGamification] 保存空间失败: {e}")

    def _load_spaces(self) -> None:
        """加载本地空间"""
        try:
            for filename in os.listdir(self._spaces_dir):
                if filename.endswith('.json'):
                    with open(os.path.join(self._spaces_dir, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)

                        # 转换节点
                        nodes = []
                        for node_data in data.get("nodes", []):
                            node_data["position_3d"] = tuple(node_data["position_3d"])
                            node_data["created_at"] = datetime.fromisoformat(node_data["created_at"])
                            node_data["updated_at"] = datetime.fromisoformat(node_data["updated_at"])
                            nodes.append(CreativeNode(**node_data))

                        # 转换空间
                        data["created_at"] = datetime.fromisoformat(data["created_at"])
                        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
                        data["nodes"] = nodes
                        data["space_type"] = SpaceType(data["space_type"])

                        space = CreativeSpace(**{k: v for k, v in data.items() if k not in ["nodes"]})
                        space.nodes = nodes
                        self._spaces[space.space_id] = space
        except Exception as e:
            print(f"[CreativeGamification] 加载空间失败: {e}")

    async def _save_achievements(self) -> None:
        """保存成就数据"""
        try:
            data = {
                "achievements": [
                    {
                        **vars(a),
                        "unlocked_at": a.unlocked_at.isoformat() if a.unlocked_at else None
                    }
                    for a in self._achievements.values()
                ],
                "user_points": self._user_points
            }
            with open(self._achievements_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CreativeGamification] 保存成就失败: {e}")

    def _load_achievements(self) -> None:
        """加载成就数据"""
        try:
            if os.path.exists(self._achievements_file):
                with open(self._achievements_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    self._user_points = data.get("user_points", {})

                    for a_data in data.get("achievements", []):
                        if a_data["unlocked_at"]:
                            a_data["unlocked_at"] = datetime.fromisoformat(a_data["unlocked_at"])
                        achievement = Achievement(**a_data)
                        self._achievements[achievement.achievement_id] = achievement
        except Exception as e:
            print(f"[CreativeGamification] 加载成就失败: {e}")


def create_gamification(data_dir: str = "./data/creative") -> CreativeGamification:
    """创建游戏化系统实例"""
    return CreativeGamification(data_dir=data_dir)