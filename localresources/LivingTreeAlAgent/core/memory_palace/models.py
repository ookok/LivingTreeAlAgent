"""
MemPalace 记忆宫殿 - 长期记忆系统
基于 Loci 记忆术的空间化分层存储架构

核心概念：
- Palace (宫殿): 用户完整档案
- Hall (大厅): 业务板块
- Room (房间): 会话线程
- Drawer (抽屉): 关键事实
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import os


class MemoryLevel(Enum):
    """记忆层级"""
    PALACE = "palace"      # 宫殿 - 用户档案
    HALL = "hall"          # 大厅 - 业务板块
    ROOM = "room"          # 房间 - 会话
    DRAWER = "drawer"      # 抽屉 - 关键事实


@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    level: MemoryLevel
    parent_id: Optional[str]
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    compressed: bool = False
    compression_ratio: float = 1.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "level": self.level.value,
            "parent_id": self.parent_id,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "tags": self.tags,
            "compressed": self.compressed,
            "compression_ratio": self.compression_ratio
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        data = data.copy()
        data["level"] = MemoryLevel(data["level"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("last_accessed"):
            data["last_accessed"] = datetime.fromisoformat(data["last_accessed"])
        return cls(**data)


@dataclass
class PalaceProfile:
    """宫殿档案 - 用户完整画像"""
    user_id: str
    halls: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HallDomain:
    """大厅域 - 业务板块"""
    hall_id: str
    palace_id: str
    name: str
    description: str
    rooms: List[str] = field(default_factory=list)


@dataclass
class RoomSession:
    """房间会话 - 具体会话"""
    room_id: str
    hall_id: str
    title: str
    drawers: List[str] = field(default_factory=list)
    context_summary: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class DrawerFact:
    """抽屉事实 - 关键信息"""
    drawer_id: str
    room_id: str
    fact_type: str  # order_number, preference, commitment, etc.
    content: str
    extracted_from: str  # source message id
    importance: float = 0.5  # 0.0-1.0
    verified: bool = False


class MemoryCompression:
    """记忆压缩器 (AAAK 简化版)"""

    @staticmethod
    def compress(text: str) -> tuple[str, float]:
        """
        压缩文本，返回 (压缩后内容, 压缩率)
        简化实现：去除冗余空白 + 标记压缩
        """
        if not text or len(text) < 100:
            return text, 1.0

        # 简单压缩：去除多余空白
        import re
        compressed = re.sub(r'\s+', ' ', text.strip())

        # 进一步压缩重复词
        words = compressed.split()
        if len(words) > 50:
            # 保留首尾，压缩中间
            reduced = words[:10] + ['...'] + words[-10:]
            compressed = ' '.join(reduced)

        ratio = len(compressed) / max(len(text), 1)
        return compressed, ratio

    @staticmethod
    def decompress(text: str, original_hint: str = "") -> str:
        """解压缩"""
        if "..." not in text:
            return text
        # AAAK 压缩需要原始上下文才能还原
        # 这里返回简化的重建
        return text.replace("...", f"[记忆压缩段落，约 {len(original_hint)} 字符]")


class MemoryPalace:
    """
    记忆宫殿主类

    层级结构：
    Palace (宫殿)
    └── Hall (大厅) - 业务板块
        └── Room (房间) - 会话
            └── Drawer (抽屉) - 关键事实
    """

    def __init__(self, base_path: str = None):
        self.base_path = base_path or os.path.expanduser("~/.hermes-desktop/memory_palace")
        os.makedirs(self.base_path, exist_ok=True)

        # 层级存储
        self.palaces: Dict[str, PalaceProfile] = {}
        self.halls: Dict[str, HallDomain] = {}
        self.rooms: Dict[str, RoomSession] = {}
        self.drawers: Dict[str, DrawerFact] = {}
        self.entries: Dict[str, MemoryEntry] = {}

        # 压缩器
        self.compressor = MemoryCompression()

        # 加载已有数据
        self._load_index()

    def _get_index_path(self) -> str:
        return os.path.join(self.base_path, "palace_index.json")

    def _load_index(self):
        """加载索引"""
        index_path = self._get_index_path()
        if os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 恢复数据结构
                    for p_data in data.get("palaces", []):
                        p = PalaceProfile(**p_data)
                        self.palaces[p.user_id] = p
                    for h_data in data.get("halls", []):
                        h = HallDomain(**h_data)
                        self.halls[h.hall_id] = h
                    for r_data in data.get("rooms", []):
                        r = RoomSession(**r_data)
                        self.rooms[r.room_id] = r
                    for d_data in data.get("drawers", []):
                        d = DrawerFact(**d_data)
                        self.drawers[d.drawer_id] = d
            except Exception as e:
                print(f"Failed to load memory palace index: {e}")

    def _save_index(self):
        """保存索引"""
        index_path = self._get_index_path()
        data = {
            "palaces": [vars(p) for p in self.palaces.values()],
            "halls": [vars(h) for h in self.halls.values()],
            "rooms": [vars(r) for r in self.rooms.values()],
            "drawers": [vars(d) for d in self.drawers.values()]
        }
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create_palace(self, user_id: str, metadata: Dict = None) -> PalaceProfile:
        """创建宫殿"""
        palace = PalaceProfile(
            user_id=user_id,
            metadata=metadata or {}
        )
        self.palaces[user_id] = palace
        self._save_index()
        return palace

    def create_hall(self, palace_id: str, name: str, description: str = "") -> HallDomain:
        """创建大厅"""
        import uuid
        hall_id = f"hall_{uuid.uuid4().hex[:8]}"
        hall = HallDomain(
            hall_id=hall_id,
            palace_id=palace_id,
            name=name,
            description=description
        )
        self.halls[hall_id] = hall

        # 关联到宫殿
        if palace_id in self.palaces:
            self.palaces[palace_id].halls.append(hall_id)

        self._save_index()
        return hall

    def create_room(self, hall_id: str, title: str) -> RoomSession:
        """创建房间"""
        import uuid
        room_id = f"room_{uuid.uuid4().hex[:8]}"
        room = RoomSession(
            room_id=room_id,
            hall_id=hall_id,
            title=title
        )
        self.rooms[room_id] = room

        # 关联到大厅
        if hall_id in self.halls:
            self.halls[hall_id].rooms.append(room_id)

        self._save_index()
        return room

    def store_fact(self, room_id: str, fact_type: str, content: str,
                   source: str = "", importance: float = 0.5) -> DrawerFact:
        """存储关键事实到抽屉"""
        import uuid
        drawer_id = f"drawer_{uuid.uuid4().hex[:8]}"
        drawer = DrawerFact(
            drawer_id=drawer_id,
            room_id=room_id,
            fact_type=fact_type,
            content=content,
            extracted_from=source,
            importance=importance
        )
        self.drawers[drawer_id] = drawer

        # 关联到房间
        if room_id in self.rooms:
            self.rooms[room_id].drawers.append(drawer_id)

        self._save_index()
        return drawer

    def store_entry(self, level: MemoryLevel, parent_id: str,
                    title: str, content: str, metadata: Dict = None) -> MemoryEntry:
        """存储记忆条目"""
        import uuid
        entry_id = f"entry_{uuid.uuid4().hex[:8]}"

        # 检查是否需要压缩
        compressed_content = content
        is_compressed = False
        compression_ratio = 1.0

        if len(content) > 5000:
            compressed_content, compression_ratio = self.compressor.compress(content)
            is_compressed = True

        entry = MemoryEntry(
            id=entry_id,
            level=level,
            parent_id=parent_id,
            title=title,
            content=compressed_content,
            metadata=metadata or {},
            compressed=is_compressed,
            compression_ratio=compression_ratio
        )
        self.entries[entry_id] = entry

        # 保存内容到文件
        self._save_entry_content(entry)

        self._save_index()
        return entry

    def _get_content_path(self, entry_id: str) -> str:
        return os.path.join(self.base_path, "contents", f"{entry_id}.txt")

    def _save_entry_content(self, entry: MemoryEntry):
        """保存记忆内容到文件"""
        content_dir = os.path.join(self.base_path, "contents")
        os.makedirs(content_dir, exist_ok=True)

        content_path = self._get_content_path(entry.id)
        with open(content_path, "w", encoding="utf-8") as f:
            f.write(entry.content)

    def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        """检索记忆"""
        if entry_id not in self.entries:
            return None

        entry = self.entries[entry_id]
        entry.access_count += 1
        entry.last_accessed = datetime.now()

        # 如果是压缩的，需要解压缩
        if entry.compressed:
            content_path = self._get_content_path(entry_id)
            if os.path.exists(content_path):
                with open(content_path, "r", encoding="utf-8") as f:
                    entry.content = f.read()

        return entry

    def search(self, query: str, level: MemoryLevel = None,
               limit: int = 10) -> List[MemoryEntry]:
        """
        搜索记忆
        简化实现：关键词匹配
        完整实现应集成向量检索
        """
        results = []
        query_lower = query.lower()

        for entry in self.entries.values():
            if level and entry.level != level:
                continue
            if query_lower in entry.title.lower() or query_lower in entry.content.lower():
                results.append(entry)

        # 按访问频率排序
        results.sort(key=lambda e: e.access_count, reverse=True)
        return results[:limit]

    def recall_user_context(self, user_id: str, session_id: str = None) -> Dict:
        """
        回忆用户上下文
        用于 Agent 生成回复时获取历史信息
        """
        context = {
            "user_id": user_id,
            "palace": None,
            "halls": [],
            "recent_rooms": [],
            "key_facts": []
        }

        # 获取宫殿
        if user_id in self.palaces:
            context["palace"] = self.palaces[user_id]

            # 获取所有大厅
            for hall_id in self.palaces[user_id].halls:
                if hall_id in self.halls:
                    context["halls"].append(self.halls[hall_id])

            # 获取最近的房间和关键事实
            for hall in context["halls"]:
                for room_id in hall.rooms[-5:]:  # 最近5个
                    if room_id in self.rooms:
                        room = self.rooms[room_id]
                        context["recent_rooms"].append(room)

                        # 获取抽屉事实
                        for drawer_id in room.drawers:
                            if drawer_id in self.drawers:
                                context["key_facts"].append(self.drawers[drawer_id])

        return context

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_palaces": len(self.palaces),
            "total_halls": len(self.halls),
            "total_rooms": len(self.rooms),
            "total_drawers": len(self.drawers),
            "total_entries": len(self.entries),
            "compressed_entries": sum(1 for e in self.entries.values() if e.compressed),
            "storage_size_mb": self._calculate_size()
        }

    def _calculate_size(self) -> float:
        """计算存储大小 (MB)"""
        total = 0
        for root, dirs, files in os.walk(self.base_path):
            for f in files:
                fp = os.path.join(root, f)
                total += os.path.getsize(fp)
        return total / (1024 * 1024)


# 全局单例
_palace_instance: Optional[MemoryPalace] = None


def get_memory_palace() -> MemoryPalace:
    """获取记忆宫殿单例"""
    global _palace_instance
    if _palace_instance is None:
        _palace_instance = MemoryPalace()
    return _palace_instance
