"""
离线镜像 (Offline Mirror)
========================

自动将重要网页抓取并以 CID 形式存储，实现"时间旅行"访问

功能：
- 定时抓取指定网页
- 内容哈希生成 CID
- 本地存储网页快照
- 永不失效的永恒链接
"""

import asyncio
import hashlib
import json
import sqlite3
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import aiohttp


class MirrorStatus(Enum):
    """镜像状态"""
    PENDING = "pending"       # 待抓取
    FETCHING = "fetching"     # 抓取中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"        # 失败


@dataclass
class MirrorSnapshot:
    """镜像快照"""
    cid: str                           # 内容标识符 (Content ID)
    original_url: str                  # 原始 URL
    content: str                       # HTML 内容
    text_content: str                  # 纯文本内容
    title: str = ""
    fetch_time: datetime = field(default_factory=datetime.now)
    status: MirrorStatus = MirrorStatus.COMPLETED
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class OfflineMirror:
    """
    离线镜像管理器

    功能：
    1. 抓取网页并生成 CID
    2. 存储快照到本地
    3. 支持通过 CID 永恒访问
    4. 定时更新已镜像的网页
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "offline_mirror"
        self.content_dir = self.data_dir / "content"
        self.db_path = self.data_dir / "mirrors.db"

        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.content_dir.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_database()

        # 抓取会话
        self._session: Optional[aiohttp.ClientSession] = None

    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 镜像表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mirrors (
                cid TEXT PRIMARY KEY,
                original_url TEXT NOT NULL,
                title TEXT,
                fetch_time TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                content_size INTEGER,
                text_size INTEGER
            )
        """)

        # 抓取任务表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_tasks (
                task_id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                interval_hours INTEGER DEFAULT 24,
                last_fetch TEXT,
                next_fetch TEXT,
                enabled INTEGER DEFAULT 1
            )
        """)

        # 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_url ON mirrors(original_url)")

        conn.commit()
        conn.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def generate_cid(self, content: str) -> str:
        """
        生成内容标识符 (CID)

        使用 SHA-256 哈希作为 CID
        简化实现（完整实现应使用 IPFS 的 CIDv1）
        """
        # 预处理：规范化内容
        normalized = self._normalize_content(content)
        hash_bytes = hashlib.sha256(normalized.encode("utf-8")).digest()

        # 转换为 base58 字符（类似 IPFS）
        return self._bytes_to_base58(hash_bytes)

    def _normalize_content(self, content: str) -> str:
        """规范化内容（用于生成一致 CID）"""
        # 移除空白、规范化编码
        content = re.sub(r'\s+', ' ', content)
        content = content.strip()
        return content

    def _bytes_to_base58(self, data: bytes) -> str:
        """字节转 Base58"""
        alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        num = int.from_bytes(data, "big")
        result = []
        while num > 0:
            num, rem = divmod(num, 58)
            result.append(alphabet[rem])
        return "Qm" + "".join(reversed(result))[:44]  # IPFS CID 格式

    async def mirror_url(
        self,
        url: str,
        force: bool = False
    ) -> Optional[MirrorSnapshot]:
        """
        镜像 URL

        Args:
            url: 目标 URL
            force: 是否强制重新抓取

        Returns:
            镜像快照
        """
        # 检查是否已存在
        if not force:
            existing = await self.get_snapshot_by_url(url)
            if existing:
                return existing

        # 开始抓取
        cid = None
        try:
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    return MirrorSnapshot(
                        cid="",
                        original_url=url,
                        content="",
                        text_content="",
                        status=MirrorStatus.FAILED,
                        error_message=f"HTTP {response.status}"
                    )

                content = await response.text()
                html = content

                # 提取标题和纯文本
                title = self._extract_title(html)
                text = self._extract_text(html)

                # 生成 CID
                cid = self.generate_cid(html)

                # 保存快照
                await self._save_snapshot(cid, url, html, title)

                return MirrorSnapshot(
                    cid=cid,
                    original_url=url,
                    content=html,
                    text_content=text,
                    title=title,
                    status=MirrorStatus.COMPLETED
                )

        except asyncio.TimeoutError:
            return MirrorSnapshot(
                cid=cid or "",
                original_url=url,
                content="",
                text_content="",
                status=MirrorStatus.FAILED,
                error_message="Timeout"
            )
        except Exception as e:
            return MirrorSnapshot(
                cid=cid or "",
                original_url=url,
                content="",
                text_content="",
                status=MirrorStatus.FAILED,
                error_message=str(e)
            )

    def _extract_title(self, html: str) -> str:
        """提取标题"""
        match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_text(self, html: str) -> str:
        """提取纯文本"""
        # 移除脚本和样式
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # 移除标签
        text = re.sub(r'<[^>]+>', '', text)
        # 规范化空白
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    async def _save_snapshot(
        self,
        cid: str,
        url: str,
        content: str,
        title: str
    ):
        """保存快照"""
        # 保存 HTML 文件
        content_path = self.content_dir / f"{cid}.html"
        with open(content_path, "w", encoding="utf-8") as f:
            f.write(content)

        # 更新数据库
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO mirrors
            (cid, original_url, title, fetch_time, status, content_size, text_size)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            cid,
            url,
            title,
            datetime.now().isoformat(),
            MirrorStatus.COMPLETED.value,
            len(content),
            len(self._extract_text(content))
        ))

        conn.commit()
        conn.close()

    async def get_snapshot(self, cid: str) -> Optional[MirrorSnapshot]:
        """通过 CID 获取快照"""
        content_path = self.content_dir / f"{cid}.html"
        if not content_path.exists():
            return None

        with open(content_path, "r", encoding="utf-8") as f:
            content = f.read()

        return MirrorSnapshot(
            cid=cid,
            original_url="",  # 需要从数据库获取
            content=content,
            text_content=self._extract_text(content),
            title=self._extract_title(content),
            status=MirrorStatus.COMPLETED
        )

    async def get_snapshot_by_url(self, url: str) -> Optional[MirrorSnapshot]:
        """通过原始 URL 获取快照"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT cid, original_url, title, fetch_time, status, error_message
            FROM mirrors WHERE original_url = ?
            ORDER BY fetch_time DESC LIMIT 1
        """, (url,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        cid = row[0]

        # 加载内容
        content_path = self.content_dir / f"{cid}.html"
        if not content_path.exists():
            return None

        with open(content_path, "r", encoding="utf-8") as f:
            content = f.read()

        return MirrorSnapshot(
            cid=cid,
            original_url=row[1],
            content=content,
            text_content=self._extract_text(content),
            title=row[2] or "",
            fetch_time=datetime.fromisoformat(row[3]),
            status=MirrorStatus(row[4]),
            error_message=row[5]
        )

    async def add_crawl_task(
        self,
        url: str,
        interval_hours: int = 24
    ) -> str:
        """添加定时抓取任务"""
        import uuid
        task_id = uuid.uuid4().hex[:12]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO crawl_tasks
            (task_id, url, interval_hours, next_fetch, enabled)
            VALUES (?, ?, ?, ?, 1)
        """, (
            task_id,
            url,
            interval_hours,
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

        return task_id

    async def get_mirror_stats(self) -> dict[str, Any]:
        """获取镜像统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # 总镜像数
        cursor.execute("SELECT COUNT(*) FROM mirrors")
        stats["total_mirrors"] = cursor.fetchone()[0]

        # 总大小
        cursor.execute("SELECT SUM(content_size) FROM mirrors")
        stats["total_size_bytes"] = cursor.fetchone()[0] or 0

        # 抓取任务数
        cursor.execute("SELECT COUNT(*) FROM crawl_tasks WHERE enabled = 1")
        stats["active_tasks"] = cursor.fetchone()[0]

        conn.close()

        stats["total_size_mb"] = stats["total_size_bytes"] / (1024 * 1024)
        return stats


def create_offline_mirror(data_dir: Path) -> OfflineMirror:
    """创建离线镜像"""
    return OfflineMirror(data_dir=data_dir)