# -*- coding: utf-8 -*-
"""
播放列表管理模块
支持本地视频和网络视频的播放队列管理
"""

import os
import logging
from typing import List, Optional, Callable, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse
import hashlib

logger = logging.getLogger(__name__)


class ItemType(Enum):
    """列表项类型"""
    VIDEO = "video"
    AUDIO = "audio"
    UNKNOWN = "unknown"


@dataclass
class PlaylistItem:
    """
    播放列表项

    Attributes:
        id: 唯一标识符
        url: 媒体 URL 或文件路径
        title: 显示标题
        duration: 时长（秒）
        thumbnail: 缩略图路径
        item_type: 媒体类型
        metadata: 其他元数据
        local: 是否为本地文件
    """
    url: str
    title: str = ""
    duration: float = 0.0
    thumbnail: str = ""
    item_type: ItemType = ItemType.VIDEO
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = ""
    local: bool = False

    def __post_init__(self):
        if not self.id:
            # 生成唯一 ID
            self.id = hashlib.md5(self.url.encode()).hexdigest()[:12]

        if not self.title:
            # 从 URL 或文件名提取标题
            self.title = self._extract_title()

        # 判断是否为本地文件
        if not self.local:
            self.local = self._is_local()

        # 判断媒体类型
        if self.item_type == ItemType.UNKNOWN:
            self.item_type = self._guess_type()

    def _extract_title(self) -> str:
        """从 URL 或路径提取标题"""
        if self._is_local():
            return os.path.splitext(os.path.basename(self.url))[0]
        else:
            parsed = urlparse(self.url)
            path = parsed.path
            filename = os.path.basename(path)
            if filename:
                return os.path.splitext(filename)[0]
            # 尝试使用域名
            return parsed.netloc or "网络媒体"

    def _is_local(self) -> bool:
        """判断是否为本地文件"""
        if not self.url:
            return False
        # 检查是否为 URL
        parsed = urlparse(self.url)
        if parsed.scheme in ("http", "https", "rtmp", "rtmps", "mms"):
            return False
        # 检查是否为文件路径
        return os.path.exists(self.url) if self.url.startswith("/") or ":" in self.url else False

    def _guess_type(self) -> ItemType:
        """根据扩展名猜测媒体类型"""
        if self._is_local():
            ext = os.path.splitext(self.url)[1].lower()
        else:
            parsed = urlparse(self.url)
            ext = os.path.splitext(parsed.path)[1].lower()

        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
                     ".webm", ".m4v", ".mpg", ".mpeg", ".3gp", ".ogv",
                     ".ts", ".mts", ".m2ts", ".vob", ".rm", ".rmvb"}
        audio_exts = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma",
                      ".m4a", ".opus", ".ape", ".alac", ".ac3"}

        if ext in video_exts:
            return ItemType.VIDEO
        elif ext in audio_exts:
            return ItemType.AUDIO
        return ItemType.UNKNOWN


class Playlist:
    """
    播放列表管理器

    支持:
    - 添加/移除媒体
    - 排序和随机
    - 播放模式（列表循环/单曲循环/随机）
    - 列表持久化
    """

    class Mode(Enum):
        """播放模式"""
        NORMAL = "normal"           # 顺序播放，播完停止
        LOOP = "loop"               # 列表循环
        SINGLE = "single"           # 单曲循环
        SHUFFLE = "shuffle"         # 随机播放
        SHUFFLE_LOOP = "shuffle_loop"  # 随机循环

    def __init__(self):
        self._items: List[PlaylistItem] = []
        self._current_index: int = -1
        self._mode: Playlist.Mode = Playlist.Mode.LOOP
        self._history: List[int] = []  # 播放历史
        self._event_callbacks: Dict[str, Callable] = {}

    # 列表操作

    def add(self, url: str, title: str = "", **metadata) -> PlaylistItem:
        """
        添加媒体到播放列表

        Args:
            url: 媒体 URL 或文件路径
            title: 自定义标题
            **metadata: 其他元数据

        Returns:
            添加的 PlaylistItem
        """
        item = PlaylistItem(url=url, title=title, metadata=metadata)
        self._items.append(item)
        self._emit("item_added", item)
        logger.debug(f"添加媒体: {item.title}")
        return item

    def add_multiple(self, urls: List[str]) -> List[PlaylistItem]:
        """
        批量添加媒体

        Args:
            urls: URL 列表

        Returns:
            添加的 PlaylistItem 列表
        """
        items = []
        for url in urls:
            item = self.add(url)
            items.append(item)
        return items

    def remove(self, index: int) -> bool:
        """
        从播放列表移除项

        Args:
            index: 索引

        Returns:
            是否成功
        """
        if 0 <= index < len(self._items):
            item = self._items.pop(index)
            # 调整当前索引
            if index < self._current_index:
                self._current_index -= 1
            elif index == self._current_index:
                self._current_index = min(self._current_index, len(self._items) - 1)
            self._emit("item_removed", item, index)
            return True
        return False

    def remove_by_id(self, item_id: str) -> bool:
        """通过 ID 移除项"""
        for i, item in enumerate(self._items):
            if item.id == item_id:
                return self.remove(i)
        return False

    def clear(self):
        """清空播放列表"""
        self._items.clear()
        self._current_index = -1
        self._history.clear()
        self._emit("cleared")

    def move(self, from_index: int, to_index: int) -> bool:
        """
        移动播放列表项

        Args:
            from_index: 源索引
            to_index: 目标索引

        Returns:
            是否成功
        """
        if (0 <= from_index < len(self._items) and
            0 <= to_index < len(self._items)):
            item = self._items.pop(from_index)
            self._items.insert(to_index, item)

            # 调整当前索引
            if self._current_index == from_index:
                self._current_index = to_index
            elif from_index < self._current_index <= to_index:
                self._current_index -= 1
            elif to_index <= self._current_index < from_index:
                self._current_index += 1

            self._emit("reordered")
            return True
        return False

    # 播放控制

    def play(self, index: int) -> Optional[PlaylistItem]:
        """
        播放指定索引的媒体

        Args:
            index: 索引

        Returns:
            PlaylistItem 或 None
        """
        if 0 <= index < len(self._items):
            # 记录历史
            if self._current_index >= 0:
                self._history.append(self._current_index)

            self._current_index = index
            item = self._items[index]
            self._emit("play", item, index)
            logger.debug(f"播放: {item.title}")
            return item
        return None

    def play_next(self) -> Optional[PlaylistItem]:
        """
        播放下一个

        Returns:
            PlaylistItem 或 None
        """
        if not self._items:
            return None

        if self._mode == Playlist.Mode.SHUFFLE:
            import random
            next_index = random.randint(0, len(self._items) - 1)
        else:
            next_index = self._current_index + 1

            if next_index >= len(self._items):
                if self._mode in (Playlist.Mode.LOOP, Playlist.Mode.SHUFFLE_LOOP):
                    next_index = 0
                else:
                    return None

        return self.play(next_index)

    def play_previous(self) -> Optional[PlaylistItem]:
        """
        播放上一个

        Returns:
            PlaylistItem 或 None
        """
        if not self._items:
            return None

        # 从历史记录返回
        if self._history:
            prev_index = self._history.pop()
            return self.play(prev_index)

        # 否则后退
        if self._mode in (Playlist.Mode.LOOP, Playlist.Mode.SHUFFLE_LOOP):
            prev_index = (self._current_index - 1) % len(self._items)
        else:
            prev_index = max(0, self._current_index - 1)

        return self.play(prev_index)

    def get_current(self) -> Optional[PlaylistItem]:
        """获取当前播放项"""
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index]
        return None

    def get_current_index(self) -> int:
        """获取当前播放索引"""
        return self._current_index

    # 排序

    def sort_by_title(self, reverse: bool = False):
        """按标题排序"""
        current_item = self.get_current()
        self._items.sort(key=lambda x: x.title, reverse=reverse)
        self._restore_current_index(current_item)

    def sort_by_duration(self, reverse: bool = False):
        """按时长排序"""
        current_item = self.get_current()
        self._items.sort(key=lambda x: x.duration, reverse=reverse)
        self._restore_current_index(current_item)

    def shuffle(self):
        """随机排序"""
        current_item = self.get_current()
        import random
        random.shuffle(self._items)
        self._restore_current_index(current_item)

    def reverse(self):
        """反转列表"""
        current_item = self.get_current()
        self._items.reverse()
        self._restore_current_index(current_item)

    def _restore_current_index(self, current_item: Optional[PlaylistItem]):
        """恢复当前播放项的位置"""
        if current_item:
            for i, item in enumerate(self._items):
                if item.id == current_item.id:
                    self._current_index = i
                    break

    # 模式

    def set_mode(self, mode: Mode):
        """设置播放模式"""
        self._mode = mode
        self._emit("mode_changed", mode)

    def get_mode(self) -> Mode:
        """获取播放模式"""
        return self._mode

    # 查询

    def get_items(self) -> List[PlaylistItem]:
        """获取所有播放列表项"""
        return self._items.copy()

    def get_count(self) -> int:
        """获取列表项数量"""
        return len(self._items)

    def is_empty(self) -> bool:
        """列表是否为空"""
        return len(self._items) == 0

    def find_by_url(self, url: str) -> Optional[PlaylistItem]:
        """通过 URL 查找项"""
        for item in self._items:
            if item.url == url:
                return item
        return None

    def get_videos(self) -> List[PlaylistItem]:
        """获取所有视频项"""
        return [item for item in self._items if item.item_type == ItemType.VIDEO]

    def get_audios(self) -> List[PlaylistItem]:
        """获取所有音频项"""
        return [item for item in self._items if item.item_type == ItemType.AUDIO]

    # 持久化

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "mode": self._mode.value,
            "current_index": self._current_index,
            "items": [
                {
                    "url": item.url,
                    "title": item.title,
                    "duration": item.duration,
                    "thumbnail": item.thumbnail,
                    "type": item.item_type.value,
                    "metadata": item.metadata
                }
                for item in self._items
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Playlist":
        """从字典反序列化"""
        playlist = cls()

        # 恢复模式
        if "mode" in data:
            playlist._mode = Playlist.Mode(data["mode"])

        # 恢复项
        for item_data in data.get("items", []):
            item = PlaylistItem(
                url=item_data["url"],
                title=item_data.get("title", ""),
                duration=item_data.get("duration", 0.0),
                thumbnail=item_data.get("thumbnail", ""),
                metadata=item_data.get("metadata", {})
            )
            playlist._items.append(item)

        # 恢复当前索引
        if "current_index" in data and 0 <= data["current_index"] < len(playlist._items):
            playlist._current_index = data["current_index"]

        return playlist

    def save_to_file(self, path: str) -> bool:
        """
        保存播放列表到文件

        Args:
            path: 文件路径

        Returns:
            是否成功
        """
        import json
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"播放列表已保存: {path}")
            return True
        except Exception as e:
            logger.error(f"保存播放列表失败: {e}")
            return False

    @classmethod
    def load_from_file(cls, path: str) -> Optional["Playlist"]:
        """
        从文件加载播放列表

        Args:
            path: 文件路径

        Returns:
            Playlist 或 None
        """
        import json
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            playlist = cls.from_dict(data)
            logger.info(f"播放列表已加载: {path}")
            return playlist
        except Exception as e:
            logger.error(f"加载播放列表失败: {e}")
            return None

    # 事件

    def on(self, event: str, callback: Callable):
        """注册事件回调"""
        self._event_callbacks[event] = callback

    def off(self, event: str):
        """注销事件回调"""
        self._event_callbacks.pop(event, None)

    def _emit(self, event: str, *args):
        """触发事件"""
        if event in self._event_callbacks:
            try:
                self._event_callbacks[event](*args)
            except Exception as e:
                logger.error(f"播放列表事件回调错误: {e}")
