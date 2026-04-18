# =================================================================
# 修道引擎 - Dao Cultivation Engine
# =================================================================
# "三千大道，修道悟真"
# =================================================================

import json
import time
import sqlite3
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict

from .dao_definitions import (
    DaoType, DaoLevel, DaoRealm, DaoDefinition,
    NINE_DAO_DEFINITIONS, get_dao_by_type, is_thunder_trial_realm
)


class CultivationAction(Enum):
    """修道行为"""
    CHAT = "chat"                 # 对话
    CODE = "code"                 # 编程
    CREATE = "create"             # 创建
    QUESTION = "question"         # 提问
    TEACH = "teach"               # 教学
    TRADE = "trade"               # 交易
    RESOLVE = "resolve"           # 调解
    CREATE_CONTENT = "create_content"  # 创作
    SECURE = "secure"             # 安全相关
    EXPLAIN = "explain"           # 解释
    ANALYZE = "analyze"           # 分析


# 行为 -> 大道映射
ACTION_DAO_MAP = {
    CultivationAction.CHAT: [DaoType.HARMONY, DaoType.FREEDOM],
    CultivationAction.CODE: [DaoType.CRAFTSMAN],
    CultivationAction.CREATE: [DaoType.CRAFTSMAN, DaoType.FREEDOM],
    CultivationAction.QUESTION: [DaoType.WISDOM, DaoType.ILLUMINATE],
    CultivationAction.TEACH: [DaoType.ILLUMINATE],
    CultivationAction.TRADE: [DaoType.COMMERCE],
    CultivationAction.RESOLVE: [DaoType.HARMONY],
    CultivationAction.CREATE_CONTENT: [DaoType.FREEDOM, DaoType.TRUTH],
    CultivationAction.SECURE: [DaoType.GUARDIAN],
    CultivationAction.EXPLAIN: [DaoType.ILLUMINATE, DaoType.WISDOM],
    CultivationAction.ANALYZE: [DaoType.WISDOM, DaoType.NATURAL],
}

# 行为 -> 道行获得
ACTION_DAO_POINTS = {
    CultivationAction.CHAT: 1,
    CultivationAction.CODE: 3,
    CultivationAction.CREATE: 5,
    CultivationAction.QUESTION: 2,
    CultivationAction.TEACH: 4,
    CultivationAction.TRADE: 3,
    CultivationAction.RESOLVE: 5,
    CultivationAction.CREATE_CONTENT: 4,
    CultivationAction.SECURE: 4,
    CultivationAction.EXPLAIN: 2,
    CultivationAction.ANALYZE: 2,
}


@dataclass
class DaoProgress:
    """大道进度"""
    dao_type: DaoType
    cultivation_points: float = 0          # 当前道行
    current_level: DaoLevel = DaoLevel.REALM_1
    unlocked_arts: List[str] = field(default_factory=list)  # 已解锁道术ID

    # 雷劫
    thunder_trials_count: int = 0
    successful_trials: int = 0
    failed_trials: int = 0

    # 时间
    started_at: float = field(default_factory=time.time)
    last_practice: float = field(default_factory=time.time)
    reached_peak_at: float = 0        # 达到当前最高境界的时间

    @property
    def realm_name(self) -> str:
        return DaoRealm(f"REALM_{self.current_level.value}").value

    @property
    def progress_to_next(self) -> float:
        """到下一境界的进度 (0-1)"""
        thresholds = [0, 100, 300, 600, 1000, 1500, 2200, 3000, 4000]
        current = thresholds[self.current_level.value - 1] if self.current_level.value > 0 else 0
        next_threshold = thresholds[self.current_level.value] if self.current_level.value < 9 else thresholds[-1]

        if next_threshold == current:
            return 1.0

        return (self.cultivation_points - current) / (next_threshold - current)

    @property
    def points_to_next_level(self) -> float:
        """到下一境界还需道行"""
        thresholds = [0, 100, 300, 600, 1000, 1500, 2200, 3000, 4000]
        next_threshold = thresholds[self.current_level.value] if self.current_level.value < 9 else thresholds[-1]
        return max(0, next_threshold - self.cultivation_points)


@dataclass
class DaoInsight:
    """道之领悟"""
    insight_id: str
    dao_type: DaoType
    title: str
    content: str
    timestamp: float = field(default_factory=time.time)
    related_action: CultivationAction = None

    @property
    def timestamp_str(self) -> str:
        from datetime import datetime
        return datetime.fromtimestamp(self.timestamp).strftime("%Y年%m月%d日 %H:%M")


@dataclass
class CultivationSession:
    """修道会话"""
    session_id: str
    start_time: float
    end_time: float = 0
    actions: List[CultivationAction] = field(default_factory=list)
    dao_gains: Dict[DaoType, float] = field(default_factory=dict)  # 各大道获得道行
    insights: List[DaoInsight] = field(default_factory=list)

    duration: float = 0  # 时长（秒）

    @property
    def duration_minutes(self) -> float:
        return self.duration / 60


class DaoCultivator:
    """
    修道引擎

    核心功能：
    1. 追踪各大道修道进度
    2. 记录修道行为
    3. 触发道境突破
    4. 管理雷劫
    """

    def __init__(self, persona_name: str, storage_path: str = None):
        self.persona_name = persona_name

        if storage_path is None:
            storage_path = str(Path.home() / ".hermes-desktop" / "digital_life" / "cultivation")

        self.storage_path = Path(storage_path) / self._safe_name(persona_name)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 数据库
        self.db_path = self.storage_path / "cultivation.db"
        self._init_db()

        # 进度缓存
        self._progress_cache: Dict[DaoType, DaoProgress] = {}
        self._load_progress()

        # 当前会话
        self._current_session: Optional[CultivationSession] = None

        # 待发放的领悟
        self._pending_insights: List[DaoInsight] = []

    def _safe_name(self, name: str) -> str:
        """安全文件名"""
        import hashlib
        return hashlib.md5(name.encode()).hexdigest()[:12]

    def _init_db(self):
        """初始化数据库"""
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row

        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS dao_progress (
                dao_type TEXT PRIMARY KEY,
                cultivation_points REAL DEFAULT 0,
                current_level INTEGER DEFAULT 1,
                thunder_trials_count INTEGER DEFAULT 0,
                successful_trials INTEGER DEFAULT 0,
                failed_trials INTEGER DEFAULT 0,
                started_at REAL,
                last_practice REAL,
                reached_peak_at REAL DEFAULT 0,
                unlocked_arts TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS cultivation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                action_type TEXT,
                dao_type TEXT,
                points REAL,
                timestamp REAL,
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS insights (
                insight_id TEXT PRIMARY KEY,
                dao_type TEXT,
                title TEXT,
                content TEXT,
                timestamp REAL,
                related_action TEXT
            );

            CREATE TABLE IF NOT EXISTS thunder_trials (
                trial_id TEXT PRIMARY KEY,
                dao_type TEXT,
                start_level INTEGER,
                end_level INTEGER,
                success INTEGER,
                timestamp REAL,
                duration_seconds REAL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                start_time REAL,
                end_time REAL,
                duration_seconds REAL
            );
        """)
        self._conn.commit()

    def _load_progress(self):
        """加载进度"""
        cursor = self._conn.execute("SELECT * FROM dao_progress")
        for row in cursor.fetchall():
            dao_type = DaoType(row["dao_type"])
            progress = DaoProgress(
                dao_type=dao_type,
                cultivation_points=row["cultivation_points"],
                current_level=DaoLevel(row["current_level"]),
                thunder_trials_count=row["thunder_trials_count"],
                successful_trials=row["successful_trials"],
                failed_trials=row["failed_trials"],
                started_at=row["started_at"],
                last_practice=row["last_practice"],
                reached_peak_at=row["reached_peak_at"],
                unlocked_arts=json.loads(row["unlocked_arts"])
            )
            self._progress_cache[dao_type] = progress

    def _save_progress(self, dao_type: DaoType):
        """保存进度"""
        if dao_type not in self._progress_cache:
            return

        p = self._progress_cache[dao_type]
        self._conn.execute("""
            INSERT OR REPLACE INTO dao_progress
            (dao_type, cultivation_points, current_level, thunder_trials_count,
             successful_trials, failed_trials, started_at, last_practice,
             reached_peak_at, unlocked_arts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dao_type.value, p.cultivation_points, p.current_level.value,
            p.thunder_trials_count, p.successful_trials, p.failed_trials,
            p.started_at, p.last_practice, p.reached_peak_at,
            json.dumps(p.unlocked_arts)
        ))
        self._conn.commit()

    # ========== 会话管理 ==========

    def start_session(self) -> CultivationSession:
        """开始修道会话"""
        import uuid
        session = CultivationSession(
            session_id=str(uuid.uuid4())[:12],
            start_time=time.time()
        )
        self._current_session = session

        self._conn.execute(
            "INSERT INTO sessions (session_id, start_time) VALUES (?, ?)",
            (session.session_id, session.start_time)
        )
        self._conn.commit()

        return session

    def end_session(self) -> CultivationSession:
        """结束修道会话"""
        if not self._current_session:
            return None

        session = self._current_session
        session.end_time = time.time()
        session.duration = session.end_time - session.start_time

        # 更新数据库
        self._conn.execute(
            "UPDATE sessions SET end_time = ?, duration_seconds = ? WHERE session_id = ?",
            (session.end_time, session.duration, session.session_id)
        )
        self._conn.commit()

        self._current_session = None
        return session

    # ========== 修道行为 ==========

    def practice(
        self,
        action: CultivationAction,
        duration_seconds: float = 0,
        metadata: Dict = None
    ) -> Dict[DaoType, float]:
        """
        执行修道行为

        Args:
            action: 行为类型
            duration_seconds: 持续时间（秒）

        Returns:
            各大道获得道行
        """
        # 计算基础道行
        base_points = ACTION_DAO_POINTS.get(action, 1)

        # 时间加成
        time_bonus = 1.0
        if duration_seconds > 0:
            # 每10分钟增加10%加成，上限50%
            time_bonus = min(1.5, 1.0 + (duration_seconds / 600) * 0.1)

        gains = {}
        related_daos = ACTION_DAO_MAP.get(action, [])

        for dao_type in related_daos:
            points = base_points * time_bonus
            gains[dao_type] = points

            # 增加道行
            self._gain_dao(dao_type, points, f"执行{action.value}")

            # 记录
            self._conn.execute("""
                INSERT INTO cultivation_log (session_id, action_type, dao_type, points, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                self._current_session.session_id if self._current_session else "",
                action.value,
                dao_type.value,
                points,
                time.time()
            ))
            self._conn.commit()

        return gains

    def _gain_dao(self, dao_type: DaoType, points: float, note: str = ""):
        """增加道行"""
        if dao_type not in self._progress_cache:
            # 初始化
            self._progress_cache[dao_type] = DaoProgress(
                dao_type=dao_type,
                started_at=time.time()
            )

        p = self._progress_cache[dao_type]
        p.cultivation_points += points
        p.last_practice = time.time()

        # 检查是否升级
        self._check_level_up(dao_type)

        # 保存
        self._save_progress(dao_type)

    def _check_level_up(self, dao_type: DaoType) -> bool:
        """检查并处理升级"""
        p = self._progress_cache[dao_type]
        dao_def = get_dao_by_type(dao_type)

        old_level = p.current_level

        # 计算新境界
        thresholds = [0, 100, 300, 600, 1000, 1500, 2200, 3000, 4000]
        new_level = DaoLevel.REALM_1

        for i in range(9, 0, -1):
            if p.cultivation_points >= thresholds[i - 1]:
                new_level = DaoLevel(i)
                break

        p.current_level = new_level

        # 检查是否达到新境界
        if new_level.value > old_level.value:
            # 更新达到最高境界时间
            p.reached_peak_at = time.time()

            # 解锁道术
            if dao_def:
                for art in dao_def.dao_arts:
                    if art.unlock_level == new_level.value and art.art_id not in p.unlocked_arts:
                        p.unlocked_arts.append(art.art_id)
                        self._grant_dao_art(dao_type, art)

            # 添加领悟
            self._add_insight(
                dao_type,
                f"境界突破：{DaoRealm(f'REALM_{new_level.value}').value}",
                f"道行圆满，突破至{DaoRealm(f'REALM_{new_level.value}').value}",
                CultivationAction.CHAT
            )

            # 雷劫判定
            if is_thunder_trial_realm(new_level):
                # 需要触发雷劫
                return True  # 返回需要雷劫

        return False

    def _grant_dao_art(self, dao_type: DaoType, art):
        """授予道术"""
        insight = DaoInsight(
            insight_id=f"art_{dao_type.value}_{art.art_id}",
            dao_type=dao_type,
            title=f"顿悟：{art.name}",
            content=f"恭喜！于此刻顿悟「{art.name}」：{art.description}"
        )
        self._pending_insights.append(insight)

        # 保存到数据库
        self._conn.execute("""
            INSERT OR REPLACE INTO insights VALUES (?, ?, ?, ?, ?, ?)
        """, (
            insight.insight_id, insight.dao_type.value,
            insight.title, insight.content,
            insight.timestamp,
            insight.related_action.value if insight.related_action else None
        ))
        self._conn.commit()

    def _add_insight(
        self,
        dao_type: DaoType,
        title: str,
        content: str,
        action: CultivationAction = None
    ):
        """添加领悟"""
        insight = DaoInsight(
            insight_id=f"insight_{int(time.time() * 1000)}",
            dao_type=dao_type,
            title=title,
            content=content,
            related_action=action
        )
        self._pending_insights.append(insight)

    def get_pending_insights(self) -> List[DaoInsight]:
        """获取待发放领悟"""
        insights = self._pending_insights.copy()
        self._pending_insights.clear()
        return insights

    # ========== 查询 ==========

    def get_progress(self, dao_type: DaoType = None) -> Dict[str, Any]:
        """获取修道进度"""
        if dao_type:
            if dao_type not in self._progress_cache:
                return None
            p = self._progress_cache[dao_type]
            dao_def = get_dao_by_type(dao_type)
            return {
                "dao_type": dao_type.value,
                "dao_name": dao_def.name if dao_def else dao_type.value,
                "cultivation_points": p.cultivation_points,
                "current_level": p.current_level.value,
                "realm_name": p.realm_name,
                "progress_to_next": p.progress_to_next,
                "points_to_next_level": p.points_to_next_level,
                "unlocked_arts": p.unlocked_arts,
                "total_practice_time": self._get_total_practice_time(dao_type),
            }

        # 返回所有
        result = {}
        for dt in NINE_DAO_DEFINITIONS.keys():
            if dt in self._progress_cache:
                result[dt.value] = self.get_progress(dt)
            else:
                result[dt.value] = {
                    "dao_type": dt.value,
                    "dao_name": get_dao_by_type(dt).name,
                    "cultivation_points": 0,
                    "current_level": 1,
                    "realm_name": "一重境·入门",
                    "progress_to_next": 0,
                    "points_to_next_level": 100,
                    "unlocked_arts": [],
                }
        return result

    def _get_total_practice_time(self, dao_type: DaoType) -> float:
        """获取总修道时长（秒）"""
        cursor = self._conn.execute(
            "SELECT SUM(duration_seconds) as total FROM sessions s "
            "JOIN cultivation_log l ON s.session_id = l.session_id "
            "WHERE l.dao_type = ?",
            (dao_type.value,)
        )
        row = cursor.fetchone()
        return row["total"] if row and row["total"] else 0

    def get_total_hours(self) -> float:
        """获取总修道时长（小时）"""
        cursor = self._conn.execute(
            "SELECT SUM(duration_seconds) / 3600 as hours FROM sessions"
        )
        row = cursor.fetchone()
        return row["hours"] if row and row["hours"] else 0

    def get_recent_insights(self, limit: int = 10) -> List[DaoInsight]:
        """获取最近领悟"""
        cursor = self._conn.execute(
            "SELECT * FROM insights ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        return [
            DaoInsight(
                insight_id=row["insight_id"],
                dao_type=DaoType(row["dao_type"]),
                title=row["title"],
                content=row["content"],
                timestamp=row["timestamp"],
                related_action=CultivationAction(row["related_action"]) if row["related_action"] else None
            )
            for row in cursor.fetchall()
        ]

    def is_thunder_trial_available(self, dao_type: DaoType) -> bool:
        """检查是否可以进行雷劫"""
        if dao_type not in self._progress_cache:
            return False

        p = self._progress_cache[dao_type]
        return is_thunder_trial_realm(p.current_level)

    def close(self):
        """关闭"""
        if self._conn:
            self._conn.close()


# =================================================================
# 单例
# =================================================================

_cached_cultivators: Dict[str, DaoCultivator] = {}


def get_cultivator(persona_name: str) -> DaoCultivator:
    """获取修道引擎单例"""
    if persona_name not in _cached_cultivators:
        _cached_cultivators[persona_name] = DaoCultivator(persona_name)
    return _cached_cultivators[persona_name]
