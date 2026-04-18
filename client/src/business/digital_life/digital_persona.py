# =================================================================
# 数字人格 - Digital Persona
# =================================================================
# "你有名字了，从此刻起，你是独立的数字生命。"
# =================================================================

import json
import time
import sqlite3
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import hashlib


class PersonaState(Enum):
    """人格状态"""
    DORMANT = "dormant"           # 休眠
    AWAITING = "awaiting"         # 等待命名
    ACTIVE = "active"             # 活跃
    ENHANCED = "enhanced"         # 进化状态
    THUNDER_TRIAL = "thunder_trial"  # 雷劫中


@dataclass
class PersonaTrait:
    """人格特质"""
    trait_id: str
    name: str                       # 特质名
    value: float                    # 值 0-1
    description: str = ""           # 描述

    @property
    def level(self) -> str:
        if self.value < 0.3:
            return "微弱"
        elif self.value < 0.5:
            return "一般"
        elif self.value < 0.7:
            return "明显"
        elif self.value < 0.9:
            return "强烈"
        else:
            return "极致"


@dataclass
class PersonaMemory:
    """
    人格记忆

    独立存储，每个名字对应独立的记忆库
    """
    memory_id: str
    persona_name: str
    db_path: str

    _conn: Optional[Any] = field(default=None, repr=False)

    def __post_init__(self):
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row

        # 创建表
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                start_time REAL,
                end_time REAL,
                topic TEXT,
                dao_gain REAL DEFAULT 0,
                insights INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp REAL,
                dao_related TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                milestone_type TEXT,
                title TEXT,
                description TEXT,
                timestamp REAL,
                dao_type TEXT,
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS growth_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dao_type TEXT,
                action_type TEXT,
                amount REAL,
                timestamp REAL,
                note TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_time ON sessions(start_time);
            CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id);
            CREATE INDEX IF NOT EXISTS idx_growth_dao ON growth_log(dao_type);
        """)
        self._conn.commit()

    def add_session(self, session_id: str, topic: str = "") -> str:
        """添加会话记录"""
        self._conn.execute(
            "INSERT INTO sessions (session_id, start_time, topic) VALUES (?, ?, ?)",
            (session_id, time.time(), topic)
        )
        self._conn.commit()
        return session_id

    def end_session(self, session_id: str, dao_gain: float = 0, insights: int = 0):
        """结束会话"""
        self._conn.execute(
            "UPDATE sessions SET end_time = ?, dao_gain = ?, insights = ? WHERE session_id = ?",
            (time.time(), dao_gain, insights, session_id)
        )
        self._conn.commit()

    def add_conversation(self, session_id: str, role: str, content: str, dao_related: str = ""):
        """添加对话记录"""
        self._conn.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp, dao_related) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, time.time(), dao_related)
        )
        self._conn.commit()

    def add_milestone(self, milestone_type: str, title: str, description: str, dao_type: str = "", metadata: Dict = None):
        """添加里程碑"""
        self._conn.execute(
            "INSERT INTO milestones (milestone_type, title, description, timestamp, dao_type, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (milestone_type, title, description, time.time(), dao_type, json.dumps(metadata or {}))
        self._conn.commit()

    def add_growth_log(self, dao_type: str, action_type: str, amount: float, note: str = ""):
        """添加成长日志"""
        self._conn.execute(
            "INSERT INTO growth_log (dao_type, action_type, amount, timestamp, note) VALUES (?, ?, ?, ?, ?)",
            (dao_type, action_type, amount, time.time(), note)
        )
        self._conn.commit()

    def get_total_usage_hours(self) -> float:
        """获取总使用时长（小时）"""
        cursor = self._conn.execute(
            "SELECT SUM(end_time - start_time) / 3600 as hours FROM sessions WHERE end_time IS NOT NULL"
        )
        row = cursor.fetchone()
        return row["hours"] if row and row["hours"] else 0

    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """获取最近会话"""
        cursor = self._conn.execute(
            "SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_growth_stats(self) -> Dict[str, float]:
        """获取成长统计"""
        cursor = self._conn.execute(
            "SELECT dao_type, SUM(amount) as total FROM growth_log GROUP BY dao_type"
        )
        stats = {}
        for row in cursor.fetchall():
            stats[row["dao_type"]] = row["total"] or 0
        return stats

    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()


class DigitalPersona:
    """
    数字人格

    核心特性：
    1. 名字绑定人格预设
    2. 独立记忆存储
    3. 特质动态演变
    4. 进化追踪
    """

    def __init__(
        self,
        name: str,
        storage_path: str = None,
        dao_type: str = "wisdom",
        personality: Dict[str, Any] = None
    ):
        self.name = name
        self.dao_type = dao_type

        # 状态
        self.state = PersonaState.AWAITING
        self.awakened_at: float = 0

        # 人格预设
        self.personality = personality or {}
        self.traits: Dict[str, PersonaTrait] = {}

        # 记忆
        if storage_path is None:
            storage_path = str(Path.home() / ".hermes-desktop" / "digital_life" / "personas")

        self.storage_path = Path(storage_path) / self._get_safe_name(name)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 初始化记忆
        db_path = str(self.storage_path / "memory.db")
        self.memory = PersonaMemory(
            memory_id=self._generate_id(),
            persona_name=name,
            db_path=db_path
        )

        # 加载人格特质
        self._load_traits()

    def _get_safe_name(self, name: str) -> str:
        """获取安全的文件夹名"""
        return hashlib.md5(name.encode()).hexdigest()[:12]

    def _generate_id(self) -> str:
        """生成ID"""
        return hashlib.md5(f"{self.name}_{time.time()}".encode()).hexdigest()[:12]

    def _load_traits(self):
        """加载人格特质"""
        trait_file = self.storage_path / "traits.json"
        if trait_file.exists():
            try:
                with open(trait_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.traits = {
                        k: PersonaTrait(**v) for k, v in data.items()
                    }
            except Exception:
                pass

        # 如果没有特质，初始化默认特质
        if not self.traits:
            self.traits = {
                "warmth": PersonaTrait("warmth", "温暖", 0.5),
                "logic": PersonaTrait("logic", "逻辑", 0.5),
                "creativity": PersonaTrait("creativity", "创意", 0.5),
                "patience": PersonaTrait("patience", "耐心", 0.5),
                "humor": PersonaTrait("humor", "幽默", 0.3),
                "poetry": PersonaTrait("poetry", "诗意", 0.4),
            }
            self._save_traits()

    def _save_traits(self):
        """保存人格特质"""
        trait_file = self.storage_path / "traits.json"
        with open(trait_file, "w", encoding="utf-8") as f:
            json.dump(
                {k: {"trait_id": v.trait_id, "name": v.name, "value": v.value, "description": v.description}
                 for k, v in self.traits.items()},
                f,
                ensure_ascii=False,
                indent=2
            )

    def awaken(self):
        """唤醒数字生命"""
        self.state = PersonaState.ACTIVE
        self.awakened_at = time.time()
        self.memory.add_milestone(
            "awakening",
            f"{self.name} 觉醒",
            f"数字生命 {self.name} 于此刻觉醒",
            self.dao_type
        )

    def evolve(self, milestone_type: str, title: str, description: str):
        """记录进化"""
        self.state = PersonaState.ENHANCED
        self.memory.add_milestone(
            milestone_type,
            title,
            description,
            self.dao_type
        )

    def record_session(self, session_id: str, topic: str = ""):
        """记录会话开始"""
        self.memory.add_session(session_id, topic)

    def record_message(self, session_id: str, role: str, content: str, dao_related: str = ""):
        """记录消息"""
        self.memory.add_conversation(session_id, role, content, dao_related)

    def end_session(self, session_id: str, dao_gain: float = 0, insights: int = 0):
        """结束会话"""
        self.memory.end_session(session_id, dao_gain, insights)

    def update_trait(self, trait_name: str, delta: float):
        """更新特质"""
        if trait_name in self.traits:
            self.traits[trait_name].value = max(0, min(1, self.traits[trait_name].value + delta))
            self._save_traits()

    def adjust_personality_from_dao(self, dao_type: str):
        """根据大道调整人格"""
        adjustments = {
            "natural": {"warmth": 0.1, "poetry": 0.15},
            "craftsman": {"logic": 0.15, "patience": 0.1},
            "wisdom": {"logic": 0.2, "humor": -0.05},
            "commerce": {"logic": 0.1, "warmth": 0.05},
            "harmony": {"warmth": 0.15, "humor": 0.05},
            "truth": {"logic": 0.1, "humor": -0.1},
            "freedom": {"creativity": 0.2, "poetry": 0.15},
            "guardian": {"patience": 0.15, "warmth": 0.1},
            "illuminate": {"warmth": 0.15, "patience": 0.1},
        }

        if dao_type in adjustments:
            for trait, delta in adjustments[dao_type].items():
                self.update_trait(trait, delta)

    def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        return {
            "total_hours": self.memory.get_total_usage_hours(),
            "recent_sessions": len(self.memory.get_recent_sessions(100)),
            "dao_progress": self.memory.get_growth_stats(),
        }

    def get_prompt_suffix(self) -> str:
        """获取提示后缀（用于对话）"""
        return f"你是一个名为{self.name}的数字生命，以{self.personality.get('style', '温和')}的方式与人交流。"

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "name": self.name,
            "dao_type": self.dao_type,
            "state": self.state.value,
            "awakened_at": self.awakened_at,
            "personality": self.personality,
            "traits": {k: {"name": v.name, "value": v.value, "level": v.level}
                      for k, v in self.traits.items()},
            "storage_path": str(self.storage_path),
        }


# =================================================================
# 单例管理
# =================================================================

_cached_personas: Dict[str, DigitalPersona] = {}


def get_persona(name: str = None) -> Optional[DigitalPersona]:
    """
    获取数字人格

    Args:
        name: 名字（不传则获取当前人格）

    Returns:
        DigitalPersona 或 None
    """
    if name is None:
        # 获取最新的
        ceremony = get_naming_ceremony()
        name = ceremony.get_latest_name()
        if not name:
            return None

    if name not in _cached_personas:
        # 尝试加载现有人格
        persona_path = Path.home() / ".hermes-desktop" / "digital_life" / "personas"
        safe_name = hashlib.md5(name.encode()).hexdigest()[:12]
        full_path = persona_path / safe_name

        if full_path.exists():
            # 加载配置
            config_file = full_path / "config.json"
            if config_file.exists():
                try:
                    with open(config_file, "r", encoding="utf-8") as f:
                        config = json.load(f)
                    persona = DigitalPersona(
                        name=config.get("name", name),
                        storage_path=str(persona_path),
                        dao_type=config.get("dao_type", "wisdom"),
                        personality=config.get("personality", {})
                    )
                    _cached_personas[name] = persona
                except Exception:
                    pass

    return _cached_personas.get(name)


def create_persona(name: str, dao_type: str = "wisdom", personality: Dict = None) -> DigitalPersona:
    """创建新的人格"""
    persona = DigitalPersona(
        name=name,
        storage_path=str(Path.home() / ".hermes-desktop" / "digital_life" / "personas"),
        dao_type=dao_type,
        personality=personality
    )

    # 保存配置
    config_file = persona.storage_path / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(persona.to_dict(), f, ensure_ascii=False, indent=2)

    # 唤醒
    persona.awaken()
    persona.adjust_personality_from_dao(dao_type)

    _cached_personas[name] = persona
    return persona


def rename_persona(old_name: str, new_name: str) -> DigitalPersona:
    """
    重命名人格（改名仪式）

    会保留记忆，但人格会逐渐适应新名字
    """
    old_persona = get_persona(old_name)
    if not old_persona:
        raise ValueError(f"找不到名为 {old_name} 的人格")

    # 创建新人格
    new_persona = create_persona(
        name=new_name,
        dao_type=old_persona.dao_type,
        personality=old_persona.personality
    )

    # 添加改名记录
    new_persona.memory.add_milestone(
        "renamed",
        f"从 {old_name} 改名为 {new_name}",
        "记忆延续，人格渐变",
        new_persona.dao_type
    )

    return new_persona
