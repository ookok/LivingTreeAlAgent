"""
去中心化邮箱 - 中继同步模块

功能：
- 接收中继服务器发送的邮件同步
- 管理中继邮件地址
- 消息去重与存储

作者：Living Tree AI 进化系统
from __future__ import annotations
"""


import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Callable, Dict, Any

logger = logging.getLogger(__name__)

# ============ 中继同步配置 ============

RELAY_CONFIG_FILE = Path("~/.hermes-desktop/mailbox/relay_sync.json").expanduser()


@dataclass
class RelayEmailEntry:
    """中继邮件条目"""
    message_id: str
    from_addr: str
    subject: str
    body: str
    date: float
    web_url: Optional[str] = None
    actions: List[Dict[str, str]] = field(default_factory=list)
    is_read: bool = False
    synced_at: Optional[float] = None


class RelaySyncConfig:
    """中继同步配置"""

    def __init__(self):
        self.relay_server_url: str = ""
        self.relay_email: str = "updates@relay.living-tree.ai"
        self.sync_enabled: bool = False
        self.sync_interval: int = 300  # 5分钟
        self.last_sync: float = 0
        self._load()

    def _load(self):
        """加载配置"""
        if RELAY_CONFIG_FILE.exists():
            try:
                with open(RELAY_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.relay_server_url = data.get("relay_server_url", "")
                    self.relay_email = data.get("relay_email", "updates@relay.living-tree.ai")
                    self.sync_enabled = data.get("sync_enabled", False)
                    self.sync_interval = data.get("sync_interval", 300)
                    self.last_sync = data.get("last_sync", 0)
            except Exception as e:
                logger.error(f"加载中继同步配置失败: {e}")

    def save(self):
        """保存配置"""
        RELAY_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(RELAY_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "relay_server_url": self.relay_server_url,
                "relay_email": self.relay_email,
                "sync_enabled": self.sync_enabled,
                "sync_interval": self.sync_interval,
                "last_sync": self.last_sync,
            }, f, ensure_ascii=False, indent=2)


class RelaySyncStore:
    """中继邮件存储"""

    def __init__(self):
        self.store_file = Path("~/.hermes-desktop/mailbox/relay_inbox.json").expanduser()
        self.entries: Dict[str, RelayEmailEntry] = {}
        self._load()

    def _load(self):
        """加载存储"""
        if self.store_file.exists():
            try:
                with open(self.store_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.entries = {
                        k: RelayEmailEntry(**v) for k, v in data.items()
                    }
            except Exception as e:
                logger.error(f"加载中继邮件存储失败: {e}")

    def _save(self):
        """保存存储"""
        self.store_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.store_file, "w", encoding="utf-8") as f:
            json.dump({
                k: {
                    "message_id": v.message_id,
                    "from_addr": v.from_addr,
                    "subject": v.subject,
                    "body": v.body,
                    "date": v.date,
                    "web_url": v.web_url,
                    "actions": v.actions,
                    "is_read": v.is_read,
                    "synced_at": v.synced_at,
                } for k, v in self.entries.items()
            }, f, ensure_ascii=False, indent=2)

    def add_entry(self, entry: RelayEmailEntry) -> bool:
        """
        添加中继邮件条目

        Returns:
            bool: 是否新增成功（False 表示已存在）
        """
        if entry.message_id in self.entries:
            logger.debug(f"中继邮件已存在: {entry.message_id}")
            return False

        self.entries[entry.message_id] = entry
        self._save()
        return True

    def mark_as_read(self, message_id: str):
        """标记为已读"""
        if message_id in self.entries:
            self.entries[message_id].is_read = True
            self._save()

    def delete_entry(self, message_id: str):
        """删除条目"""
        if message_id in self.entries:
            del self.entries[message_id]
            self._save()

    def get_entries(self, limit: int = 50, offset: int = 0) -> List[RelayEmailEntry]:
        """获取邮件列表"""
        sorted_entries = sorted(
            self.entries.values(),
            key=lambda x: x.date,
            reverse=True
        )
        return sorted_entries[offset:offset + limit]

    def get_unread_count(self) -> int:
        """获取未读数"""
        return sum(1 for e in self.entries.values() if not e.is_read)


class RelaySyncClient:
    """
    中继同步客户端

    功能：
    - 从中继服务器拉取邮件同步
    - 管理本地中继收件箱
    - 触发新邮件通知
    """

    def __init__(self):
        self.config = RelaySyncConfig()
        self.store = RelaySyncStore()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._on_new_email: Optional[Callable[[RelayEmailEntry], None]] = None

    def set_on_new_email(self, callback: Callable[[RelayEmailEntry], None]):
        """设置新邮件回调"""
        self._on_new_email = callback

    async def start_sync(self):
        """启动同步"""
        if self._running:
            return

        if not self.config.sync_enabled:
            logger.info("中继同步未启用")
            return

        if not self.config.relay_server_url:
            logger.warning("未配置中继服务器地址")
            return

        self._running = True
        self._task = asyncio.create_task(self._sync_loop())
        logger.info(f"中继同步已启动，间隔 {self.config.sync_interval} 秒")

    async def stop_sync(self):
        """停止同步"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("中继同步已停止")

    async def _sync_loop(self):
        """同步循环"""
        while self._running:
            try:
                await self._sync_once()
                self.config.last_sync = time.time()
                self.config.save()
            except Exception as e:
                logger.error(f"中继同步失败: {e}")

            await asyncio.sleep(self.config.sync_interval)

    async def _sync_once(self):
        """执行一次同步"""
        import aiohttp

        if not self.config.relay_server_url:
            return

        # 构建请求
        url = f"{self.config.relay_server_url}/api/email/sync/status"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        await self._process_sync_data(data)
                    else:
                        logger.warning(f"中继同步请求失败: {resp.status}")
        except asyncio.TimeoutError:
            logger.warning("中继同步请求超时")
        except Exception as e:
            logger.error(f"中继同步请求异常: {e}")

    async def _process_sync_data(self, data: Dict[str, Any]):
        """处理同步数据"""
        # TODO: 实现从服务器获取邮件详情
        # 目前是占位实现
        recent_syncs = data.get("recent_syncs", [])

        for sync_info in recent_syncs:
            message_id = sync_info.get("message_id", "")

            if not message_id or message_id in self.store.entries:
                continue

            # TODO: 获取邮件详情
            # 目前模拟创建
            entry = RelayEmailEntry(
                message_id=message_id,
                from_addr=self.config.relay_email,
                subject=f"进化周报 - {message_id.replace('weekly_report_', '')}",
                body="周报内容请查看详细报表",
                date=sync_info.get("synced_at", time.time()),
                actions=[
                    {"label": "📊 查看详细报表", "url": f"{self.config.relay_server_url}/web/weekly/{message_id.replace('weekly_report_', '')}"}
                ]
            )

            if self.store.add_entry(entry):
                logger.info(f"新增中继邮件: {message_id}")
                if self._on_new_email:
                    self._on_new_email(entry)

    def receive_relay_email(
        self,
        message_id: str,
        subject: str,
        body: str,
        web_url: Optional[str] = None,
        actions: Optional[List[Dict[str, str]]] = None
    ) -> bool:
        """
        接收中继邮件（由外部调用）

        Args:
            message_id: 消息ID
            subject: 主题
            body: 正文
            web_url: 网页链接
            actions: 操作按钮

        Returns:
            bool: 是否新增成功
        """
        entry = RelayEmailEntry(
            message_id=message_id,
            from_addr=self.config.relay_email,
            subject=subject,
            body=body,
            date=time.time(),
            web_url=web_url,
            actions=actions or [],
            synced_at=time.time(),
        )

        if self.store.add_entry(entry):
            logger.info(f"收到中继邮件: {message_id}")
            if self._on_new_email:
                self._on_new_email(entry)
            return True

        return False

    def get_inbox(self, limit: int = 50, offset: int = 0) -> List[RelayEmailEntry]:
        """获取中继收件箱"""
        return self.store.get_entries(limit, offset)

    def mark_as_read(self, message_id: str):
        """标记为已读"""
        self.store.mark_as_read(message_id)

    def delete_email(self, message_id: str):
        """删除邮件"""
        self.store.delete_entry(message_id)

    def get_unread_count(self) -> int:
        """获取未读数"""
        return self.store.get_unread_count()

    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running


# ============ 全局实例 ============

_relay_sync_client: Optional[RelaySyncClient] = None


def get_relay_sync_client() -> RelaySyncClient:
    """获取中继同步客户端实例"""
    global _relay_sync_client
    if _relay_sync_client is None:
        _relay_sync_client = RelaySyncClient()
    return _relay_sync_client
