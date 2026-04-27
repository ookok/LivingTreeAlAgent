"""
数字分身系统
三层分身模型 + 成长系统 + 主动交互
"""

import json
import time
import sqlite3
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
import threading


class AvatarLevel(Enum):
    """分身等级"""
    NOVICE = 1      # 初学者
    APPRENTICE = 5  # 学徒
    PRACTITIONER = 10 # 执业者
    EXPERT = 20     # 专家
    MASTER = 50     # 大师


@dataclass
class DigitalAvatar:
    """数字分身"""
    id: int = 0
    user_id: str = ""
    
    # 核心层 (低频更新)
    core_identity: Dict[str, Any] = field(default_factory=dict)
    declared_interests: List[str] = field(default_factory=list)
    
    # 行为层 (中频更新)
    behavioral_patterns: Dict[str, Any] = field(default_factory=dict)
    inferred_roles: Dict[str, float] = field(default_factory=dict)  # role -> confidence
    decision_biases: Dict[str, Any] = field(default_factory=dict)
    
    # 记忆层 (高频更新)
    conversation_milestones: List[Dict[str, Any]] = field(default_factory=list)
    learned_concepts: Dict[str, Any] = field(default_factory=dict)  # concept -> details
    knowledge_gaps: List[str] = field(default_factory=list)
    
    # 成长系统
    experience: int = 0
    level: int = 1
    unlocked_features: List[str] = field(default_factory=list)
    
    # 时间戳
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class GrowthEvent:
    """成长事件"""
    type: str
    description: str
    exp_gained: int
    timestamp: float = field(default_factory=time.time)


class AvatarDatabase:
    """分身数据库"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS avatars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                core_identity TEXT DEFAULT '{}',
                declared_interests TEXT DEFAULT '[]',
                behavioral_patterns TEXT DEFAULT '{}',
                inferred_roles TEXT DEFAULT '{}',
                decision_biases TEXT DEFAULT '{}',
                conversation_milestones TEXT DEFAULT '[]',
                learned_concepts TEXT DEFAULT '{}',
                knowledge_gaps TEXT DEFAULT '[]',
                experience INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                unlocked_features TEXT DEFAULT '[]',
                created_at REAL DEFAULT 0,
                updated_at REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS growth_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT,
                exp_gained INTEGER DEFAULT 0,
                timestamp REAL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES avatars(user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS avatar_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                snapshot_name TEXT,
                avatar_data TEXT NOT NULL,
                created_at REAL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES avatars(user_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_avatars_user ON avatars(user_id);
            CREATE INDEX IF NOT EXISTS idx_growth_user ON growth_events(user_id);
        """)
        conn.close()

    def get_avatar(self, user_id: str) -> Optional[DigitalAvatar]:
        """获取分身"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT * FROM avatars WHERE user_id=?", (user_id,)
            ).fetchone()
            if row:
                return self._row_to_avatar(row)
            return None
        finally:
            conn.close()

    def create_avatar(self, user_id: str, name: str = "") -> DigitalAvatar:
        """创建分身"""
        avatar = DigitalAvatar(
            user_id=user_id,
            core_identity={"name": name} if name else {}
        )
        
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                INSERT INTO avatars 
                (user_id, core_identity, declared_interests, behavioral_patterns,
                 inferred_roles, decision_biases, conversation_milestones,
                 learned_concepts, knowledge_gaps, experience, level,
                 unlocked_features, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                avatar.user_id, json.dumps(avatar.core_identity),
                json.dumps(avatar.declared_interests),
                json.dumps(avatar.behavioral_patterns),
                json.dumps(avatar.inferred_roles),
                json.dumps(avatar.decision_biases),
                json.dumps(avatar.conversation_milestones),
                json.dumps(avatar.learned_concepts),
                json.dumps(avatar.knowledge_gaps),
                avatar.experience, avatar.level,
                json.dumps(avatar.unlocked_features),
                avatar.created_at, avatar.updated_at
            ))
            conn.commit()
            avatar.id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            return avatar
        finally:
            conn.close()

    def save_avatar(self, avatar: DigitalAvatar):
        """保存分身"""
        avatar.updated_at = time.time()
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                UPDATE avatars SET
                    core_identity = ?,
                    declared_interests = ?,
                    behavioral_patterns = ?,
                    inferred_roles = ?,
                    decision_biases = ?,
                    conversation_milestones = ?,
                    learned_concepts = ?,
                    knowledge_gaps = ?,
                    experience = ?,
                    level = ?,
                    unlocked_features = ?,
                    updated_at = ?
                WHERE user_id = ?
            """, (
                json.dumps(avatar.core_identity),
                json.dumps(avatar.declared_interests),
                json.dumps(avatar.behavioral_patterns),
                json.dumps(avatar.inferred_roles),
                json.dumps(avatar.decision_biases),
                json.dumps(avatar.conversation_milestones),
                json.dumps(avatar.learned_concepts),
                json.dumps(avatar.knowledge_gaps),
                avatar.experience, avatar.level,
                json.dumps(avatar.unlocked_features),
                avatar.updated_at,
                avatar.user_id
            ))
            conn.commit()
        finally:
            conn.close()

    def add_growth_event(self, event: GrowthEvent):
        """添加成长事件"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                INSERT INTO growth_events (user_id, event_type, description, exp_gained, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (event.type, event.description, event.exp_gained, event.timestamp))
            conn.commit()
        finally:
            conn.close()

    def get_growth_events(self, user_id: str, limit: int = 50) -> List[GrowthEvent]:
        """获取成长事件"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                "SELECT * FROM growth_events WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
            return [
                GrowthEvent(
                    type=r[1], description=r[2],
                    exp_gained=r[3], timestamp=r[4]
                ) for r in rows
            ]
        finally:
            conn.close()

    def save_snapshot(self, user_id: str, name: str, avatar: DigitalAvatar):
        """保存快照"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                INSERT INTO avatar_snapshots (user_id, snapshot_name, avatar_data, created_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, name, json.dumps({
                "core_identity": avatar.core_identity,
                "behavioral_patterns": avatar.behavioral_patterns,
                "learned_concepts": avatar.learned_concepts,
                "experience": avatar.experience,
                "level": avatar.level
            }), time.time()))
            conn.commit()
        finally:
            conn.close()

    def get_snapshots(self, user_id: str) -> List[Dict[str, Any]]:
        """获取快照列表"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                "SELECT id, snapshot_name, created_at FROM avatar_snapshots WHERE user_id=? ORDER BY created_at DESC",
                (user_id,)
            ).fetchall()
            return [{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]
        finally:
            conn.close()

    def _row_to_avatar(self, row: sqlite3.Row) -> DigitalAvatar:
        """行转分身"""
        return DigitalAvatar(
            id=row[0], user_id=row[1],
            core_identity=json.loads(row[2] or "{}"),
            declared_interests=json.loads(row[3] or "[]"),
            behavioral_patterns=json.loads(row[4] or "{}"),
            inferred_roles=json.loads(row[5] or "{}"),
            decision_biases=json.loads(row[6] or "{}"),
            conversation_milestones=json.loads(row[7] or "[]"),
            learned_concepts=json.loads(row[8] or "{}"),
            knowledge_gaps=json.loads(row[9] or "[]"),
            experience=row[10], level=row[11],
            unlocked_features=json.loads(row[12] or "[]"),
            created_at=row[13], updated_at=row[14]
        )


class AvatarGrowthSystem:
    """分身成长系统"""

    EXPERIENCE_MAP = {
        "deep_conversation": 50,      # 深度专业对话
        "new_concept_learned": 30,    # 学习新概念
        "profile_refined": 20,        # 修正画像
        "tool_used": 10,              # 使用工具
        "task_completed": 25,         # 完成任务
        "creative_work": 40,         # 创意工作
        "long_session": 15,           # 长会话
    }

    LEVEL_THRESHOLDS = {
        1: 0,      # 0 EXP
        2: 100,    # 100 EXP
        3: 250,    # 250 EXP
        4: 500,    # 500 EXP
        5: 1000,   # 1000 EXP - 学徒
        6: 1500,
        7: 2200,
        8: 3000,
        9: 4000,
        10: 5500,  # 专家
        15: 12000,
        20: 20000, # 大师
    }

    LEVEL_REWARDS = {
        2: {"feature": "persona_archive", "description": "人格存档功能"},
        3: {"feature": "behavior_insights", "description": "行为洞察"},
        5: {"feature": "deep_analysis", "description": "深度分析技能"},
        8: {"feature": "memory_timeline", "description": "记忆时间线"},
        10: {"feature": "avatar_snapshot", "description": "分身快照"},
        15: {"feature": "cross_session", "description": "跨会话记忆"},
        20: {"feature": "avatar_inheritance", "description": "分身继承"},
        50: {"feature": "avatar_network", "description": "分身网络"},
    }

    def __init__(self, db: AvatarDatabase):
        self.db = db
        self._callbacks: List[Callable[[str, int, int, List[str]], None]] = []

    def add_experience(self, user_id: str, event_type: str, description: str = "") -> tuple:
        """添加经验值，返回 (是否升级, 新等级, 解锁功能)"""
        exp_gain = self.EXPERIENCE_MAP.get(event_type, 5)
        
        avatar = self.db.get_avatar(user_id)
        if not avatar:
            return False, 1, []

        old_level = avatar.level
        avatar.experience += exp_gain

        # 检查升级
        new_level = self._calculate_level(avatar.experience)
        unlocked = []

        if new_level > old_level:
            avatar.level = new_level
            
            # 检查解锁
            for lvl, reward in self.LEVEL_REWARDS.items():
                if old_level < lvl <= new_level:
                    if reward["feature"] not in avatar.unlocked_features:
                        avatar.unlocked_features.append(reward["feature"])
                        unlocked.append(reward["description"])

        avatar.updated_at = time.time()
        self.db.save_avatar(avatar)

        # 记录成长事件
        event = GrowthEvent(
            type=event_type, description=description,
            exp_gained=exp_gain
        )
        self.db.add_growth_event(event)

        # 通知
        for callback in self._callbacks:
            try:
                callback(user_id, new_level, exp_gain, unlocked)
            except Exception:
                pass

        return new_level > old_level, new_level, unlocked

    def _calculate_level(self, experience: int) -> int:
        """根据经验值计算等级"""
        level = 1
        for lvl, threshold in sorted(self.LEVEL_THRESHOLDS.items(), key=lambda x: x[1]):
            if experience >= threshold:
                level = lvl
        return level

    def get_level_progress(self, avatar: DigitalAvatar) -> Dict[str, Any]:
        """获取等级进度"""
        current_threshold = self.LEVEL_THRESHOLDS.get(avatar.level, 0)
        next_threshold = self.LEVEL_THRESHOLDS.get(avatar.level + 1, current_threshold + 1000)
        
        progress = (avatar.experience - current_threshold) / (next_threshold - current_threshold)
        progress = max(0, min(1, progress))

        return {
            "level": avatar.level,
            "experience": avatar.experience,
            "current_threshold": current_threshold,
            "next_threshold": next_threshold,
            "progress": progress,
            "exp_to_next": next_threshold - avatar.experience,
            "unlocked_features": avatar.unlocked_features,
            "next_reward": self.LEVEL_REWARDS.get(avatar.level + 1, {}).get("description", "")
        }

    def on_level_up(self, callback: Callable[[str, int, int, List[str]], None]):
        """注册升级回调"""
        self._callbacks.append(callback)


class AvatarLearningSystem:
    """分身学习系统"""

    def __init__(self, db: AvatarDatabase):
        self.db = db

    def update_from_conversation(
        self, user_id: str, messages: List[Dict[str, str]],
        user_profile: Dict[str, Any] = None
    ):
        """从对话中学习"""
        avatar = self.db.get_avatar(user_id)
        if not avatar:
            return

        # 分析对话模式
        self._analyze_patterns(avatar, messages)

        # 推断角色
        if user_profile:
            self._infer_roles(avatar, user_profile)

        # 学习概念
        self._learn_concepts(avatar, messages)

        # 更新知识盲区
        self._update_knowledge_gaps(avatar, messages)

        self.db.save_avatar(avatar)

    def _analyze_patterns(self, avatar: DigitalAvatar, messages: List[Dict[str, str]]):
        """分析对话模式"""
        # 分析消息长度
        user_messages = [m for m in messages if m.get("role") == "user"]
        if user_messages:
            avg_length = sum(len(m.get("content", "")) for m in user_messages) / len(user_messages)
            avatar.behavioral_patterns["avg_message_length"] = avg_length

        # 分析语言风格
        if user_messages:
            content = " ".join(m.get("content", "") for m in user_messages)
            
            # 简单关键词分析
            if any(w in content for w in ["我觉得", "我认为", "我的看法"]):
                avatar.decision_biases["style"] = "assertive"
            elif any(w in content for w in ["可能", "也许", "大概"]):
                avatar.decision_biases["style"] = "cautious"
            
            # 技术深度
            if any(w in content for w in ["代码", "API", "函数", "算法"]):
                avatar.inferred_roles["coder"] = avatar.inferred_roles.get("coder", 0) + 0.2
            
            if any(w in content for w in ["项目", "产品", "需求"]):
                avatar.inferred_roles["product"] = avatar.inferred_roles.get("product", 0) + 0.2

    def _infer_roles(self, avatar: DigitalAvatar, profile: Dict[str, Any]):
        """推断社会角色"""
        # 基于配置文件的角色推断
        if profile.get("profession"):
            avatar.core_identity["profession"] = profile["profession"]

        if profile.get("interests"):
            for interest in profile["interests"]:
                if interest not in avatar.declared_interests:
                    avatar.declared_interests.append(interest)

    def _learn_concepts(self, avatar: DigitalAvatar, messages: List[Dict[str, str]]):
        """学习新概念"""
        # 简单概念提取 (实际应该用 NLP)
        concept_keywords = ["AI", "模型", "系统", "架构", "算法"]
        
        for msg in messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                for keyword in concept_keywords:
                    if keyword in content and keyword not in avatar.learned_concepts:
                        avatar.learned_concepts[keyword] = {
                            "first_seen": time.time(),
                            "mentions": 1
                        }
                    elif keyword in content:
                        if "mentions" in avatar.learned_concepts[keyword]:
                            avatar.learned_concepts[keyword]["mentions"] += 1

    def _update_knowledge_gaps(self, avatar: DigitalAvatar, messages: List[Dict[str, str]]):
        """更新知识盲区"""
        # 检测"不知道"的回复
        unknown_patterns = ["我不确定", "不清楚", "不知道"]
        
        for msg in messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                for pattern in unknown_patterns:
                    if pattern in content:
                        # 尝试提取相关话题 (简化处理)
                        gap = content[max(0, content.find(pattern) - 20):content.find(pattern) + 20]
                        if gap and gap not in avatar.knowledge_gaps:
                            avatar.knowledge_gaps.append(gap)


class ProactiveAvatarSystem:
    """分身主动交互系统"""

    TRIGGERS = {
        "news_alert": {
            "condition": "has_industry_news",
            "priority": 2
        },
        "contradiction_check": {
            "condition": "has_contradiction",
            "priority": 3
        },
        "knowledge_update": {
            "condition": "has_knowledge_update",
            "priority": 1
        },
        "reengagement": {
            "condition": "is_long_inactive",
            "priority": 1,
            "threshold_days": 3
        }
    }

    def __init__(self, db: AvatarDatabase):
        self.db = db
        self._engagement_handlers: List[Callable[[str], Optional[str]]] = []

    def check_engagement(self, user_id: str) -> Optional[str]:
        """检查是否需要主动发起交互"""
        avatar = self.db.get_avatar(user_id)
        if not avatar:
            return None

        triggers = []

        # 检查知识更新
        if avatar.declared_interests:
            triggers.append(("knowledge_update", "你关注的领域有新动态，需要我为你解读吗？"))

        # 检查矛盾
        if len(avatar.learned_concepts) > 1:
            # 简单矛盾检测
            triggers.append(("contradiction_check", "我注意到你之前提到的观点和最近讨论有些不同，需要理清一下吗？"))

        # 检查不活跃
        if time.time() - avatar.updated_at > 3 * 24 * 3600:
            triggers.append(("reengagement", "好久不见！需要我帮你回顾一下之前的项目进展吗？"))

        # 按优先级排序
        triggers.sort(key=lambda x: self.TRIGGERS.get(x[0], {}).get("priority", 0), reverse=True)

        if triggers:
            return triggers[0][1]

        return None

    def get_context_prompt(self, user_id: str) -> str:
        """获取分身上下文提示"""
        avatar = self.db.get_avatar(user_id)
        if not avatar:
            return ""

        parts = []

        # 核心身份
        if avatar.core_identity.get("name"):
            parts.append(f"用户名称: {avatar.core_identity['name']}")

        if avatar.core_identity.get("profession"):
            parts.append(f"职业: {avatar.core_identity['profession']}")

        # 兴趣
        if avatar.declared_interests:
            parts.append(f"声明的兴趣: {', '.join(avatar.declared_interests[:5])}")

        # 推断的角色
        if avatar.inferred_roles:
            top_roles = sorted(avatar.inferred_roles.items(), key=lambda x: x[1], reverse=True)[:3]
            roles_str = ", ".join([f"{r[0]}({r[1]:.0%})" for r in top_roles])
            parts.append(f"推断的角色: {roles_str}")

        # 最近学的概念
        if avatar.learned_concepts:
            concepts = list(avatar.learned_concepts.keys())[:5]
            parts.append(f"近期关注的概念: {', '.join(concepts)}")

        # 决策风格
        if avatar.decision_biases.get("style"):
            parts.append(f"决策风格: {avatar.decision_biases['style']}")

        # 等级
        parts.append(f"分身等级: Lv{avatar.level}")

        return "\n".join(parts)


class DigitalAvatarSystem:
    """
    数字分身系统
    
    功能：
    - 三层分身模型 (核心/行为/记忆)
    - 成长系统 (经验值/等级/解锁)
    - 主动交互
    """

    def __init__(self, db_path: str | Path = None):
        from client.src.business.config import get_config_dir
        
        if db_path is None:
            db_path = get_config_dir() / "avatars.db"
        
        self.db = AvatarDatabase(db_path)
        self.growth = AvatarGrowthSystem(self.db)
        self.learning = AvatarLearningSystem(self.db)
        self.proactive = ProactiveAvatarSystem(self.db)

    def get_or_create_avatar(self, user_id: str, name: str = "") -> DigitalAvatar:
        """获取或创建分身"""
        avatar = self.db.get_avatar(user_id)
        if not avatar:
            avatar = self.db.create_avatar(user_id, name)
        return avatar

    def update_identity(self, user_id: str, core_identity: Dict[str, Any]):
        """更新核心身份"""
        avatar = self.get_or_create_avatar(user_id)
        avatar.core_identity.update(core_identity)
        avatar.updated_at = time.time()
        self.db.save_avatar(avatar)

    def add_interest(self, user_id: str, interest: str):
        """添加兴趣"""
        avatar = self.get_or_create_avatar(user_id)
        if interest not in avatar.declared_interests:
            avatar.declared_interests.append(interest)
            self.db.save_avatar(avatar)

    def learn_from_conversation(self, user_id: str, messages: List[Dict[str, str]]):
        """从对话中学习"""
        self.learning.update_from_conversation(user_id, messages)

    def add_exp(self, user_id: str, event_type: str, description: str = "") -> tuple:
        """添加经验"""
        return self.growth.add_experience(user_id, event_type, description)

    def get_level_progress(self, user_id: str) -> Dict[str, Any]:
        """获取等级进度"""
        avatar = self.get_or_create_avatar(user_id)
        return self.growth.get_level_progress(avatar)

    def check_proactive(self, user_id: str) -> Optional[str]:
        """检查主动交互"""
        return self.proactive.check_engagement(user_id)

    def get_context(self, user_id: str) -> str:
        """获取上下文"""
        return self.proactive.get_context_prompt(user_id)

    def save_snapshot(self, user_id: str, name: str):
        """保存快照"""
        avatar = self.get_or_create_avatar(user_id)
        self.db.save_snapshot(user_id, name, avatar)

    def get_snapshots(self, user_id: str) -> List[Dict[str, Any]]:
        """获取快照"""
        return self.db.get_snapshots(user_id)

    def get_growth_log(self, user_id: str, limit: int = 50) -> List[GrowthEvent]:
        """获取成长日志"""
        return self.db.get_growth_events(user_id, limit)


# 单例
_avatar_system: Optional[DigitalAvatarSystem] = None


def get_avatar_system() -> DigitalAvatarSystem:
    """获取数字分身系统单例"""
    global _avatar_system
    if _avatar_system is None:
        _avatar_system = DigitalAvatarSystem()
    return _avatar_system
