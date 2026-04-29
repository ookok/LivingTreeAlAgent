"""
IMAP 监听引擎
==============

使用 IMAPClient 实现 IDLE 模式监听新邮件。

核心功能：
1. IMAP IDLE 模式实时监听
2. 多账户支持
3. 断线重连
4. 新邮件回调
"""

import threading
import time
import traceback
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# IMAPClient 是更友好的 IMAP 封装库
# 如果不可用，使用标准库 imaplib
try:
    from imapclient import IMAPClient
    HAS_IMAPCLIENT = True
except ImportError:
    HAS_IMAPCLIENT = False
    logger.warning("IMAPClient not installed. Using imaplib fallback.")


class ConnectionState(Enum):
    """连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    IDLE = "idle"
    ERROR = "error"


@dataclass
class ListenerStats:
    """监听器统计"""
    total_emails: int = 0                  # 总处理邮件数
    new_emails: int = 0                   # 新邮件数
    errors: int = 0                       # 错误次数
    last_email_time: float = 0            # 上封邮件时间
    uptime_seconds: float = 0             # 运行时间
    reconnect_count: int = 0              # 重连次数


class IMAPListener:
    """
    IMAP 监听器

    使用 IDLE 模式监听邮箱新邮件。
    """

    def __init__(
        self,
        account,
        on_new_email: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_status_change: Optional[Callable] = None,
    ):
        """
        初始化监听器

        Args:
            account: EmailAccount 实例
            on_new_email: 新邮件回调 (email_message) -> None
            on_error: 错误回调 (error) -> None
            on_status_change: 状态变更回调 (state) -> None
        """
        self.account = account
        self.on_new_email = on_new_email or (lambda x: None)
        self.on_error = on_error or (lambda x: None)
        self.on_status_change = on_status_change or (lambda x: None)

        self._state = ConnectionState.DISCONNECTED
        self._client: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._stats = ListenerStats()
        self._start_time = 0

        # 已知的邮件ID（用于去重）
        self._seen_ids: set = set()

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def stats(self) -> ListenerStats:
        return self._stats

    def _set_state(self, new_state: ConnectionState):
        """设置状态并通知"""
        if self._state != new_state:
            self._state = new_state
            self.on_status_change(new_state)

    def start(self):
        """启动监听"""
        if self._thread and self._thread.is_alive():
            logger.warning(f"Listener for {self.account.email} is already running")
            return

        self._stop_event.clear()
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"IMAP-{self.account.email}")
        self._thread.start()
        logger.info(f"Started listener for {self.account.email}")

    def stop(self):
        """停止监听"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._cleanup()
        logger.info(f"Stopped listener for {self.account.email}")

    def _cleanup(self):
        """清理连接"""
        try:
            if self._client:
                try:
                    self._client.idle_done()
                except:
                    pass
                try:
                    self._client.logout()
                except:
                    pass
        except Exception as e:
            logger.debug(f"Cleanup error: {e}")
        finally:
            self._client = None
            self._set_state(ConnectionState.DISCONNECTED)

    def _run(self):
        """主循环"""
        while not self._stop_event.is_set():
            try:
                self._connect_and_idle()
            except Exception as e:
                logger.error(f"Listener error for {self.account.email}: {e}")
                self._stats.errors += 1
                self.on_error(str(e))
                self._set_state(ConnectionState.ERROR)

            # 重连前等待
            if not self._stop_event.is_set():
                self._stats.reconnect_count += 1
                time.sleep(min(self.account.poll_interval, 60))

        self._stats.uptime_seconds = time.time() - self._start_time

    def _connect_and_idle(self):
        """连接并进入IDLE模式"""
        self._set_state(ConnectionState.CONNECTING)

        # 建立连接
        if HAS_IMAPCLIENT:
            self._client = IMAPClient(self.account.imap_host, port=self.account.imap_port, ssl=self.account.use_ssl)
            self._client.login(self.account.username, self.account.auth_code)
        else:
            # 使用 imaplib 回退
            if self.account.use_ssl:
                self._client = imaplib.IMAP4_SSL(self.account.imap_host, self.account.imap_port)
            else:
                self._client = imaplib.IMAP4(self.account.imap_host, self.account.imap_port)
            self._client.login(self.account.username, self.account.auth_code)

        self._client.select_folder(self.account.folder)
        self._set_state(ConnectionState.CONNECTED)

        # 首次同步：获取已知邮件
        self._sync_seen_ids()

        # 进入 IDLE 循环
        self._set_state(ConnectionState.IDLE)

        while not self._stop_event.is_set():
            try:
                # 使用 IDLE 检查
                if HAS_IMAPCLIENT:
                    responses = self._client.idle_check(timeout=self.account.idle_timeout)
                else:
                    # imaplib 的 IDLE 实现
                    self._client.send(b"IDLE\r\n")
                    # 简化的 idle 实现
                    import socket
                    sock = self._client.sock
                    sock.settimeout(self.account.idle_timeout)
                    try:
                        data = sock.recv(4096)
                        responses = []
                        if b'EXISTS' in data:
                            responses = [b'EXISTS']
                    except socket.timeout:
                        responses = []

                # 处理响应
                self._process_idle_responses(responses)

            except Exception as e:
                if "IDLE" in str(e) or "timed out" in str(e).lower():
                    # IDLE 超时，重新进入 IDLE
                    if HAS_IMAPCLIENT:
                        try:
                            self._client.idle_done()
                            self._client.idle()
                        except:
                            pass
                    continue
                raise

    def _sync_seen_ids(self):
        """同步已知邮件ID"""
        try:
            if HAS_IMAPCLIENT:
                messages = self._client.search()
            else:
                status, messages = self._client.search(None, 'ALL')
                messages = messages[0].split()

            self._seen_ids = set(str(m) for m in messages)
            logger.debug(f"Synced {len(self._seen_ids)} seen IDs for {self.account.email}")
        except Exception as e:
            logger.error(f"Failed to sync seen IDs: {e}")

    def _process_idle_responses(self, responses):
        """处理 IDLE 响应"""
        if not responses:
            return

        needs_resync = False

        for response in responses:
            if isinstance(response, tuple):
                # (folder_name, data)
                continue

            response_str = str(response).upper()

            if b'EXISTS' in response or response_str.isdigit():
                # 新邮件或邮件数量变化
                needs_resync = True

            if b'RECENT' in response:
                # 有新邮件
                needs_resync = True

        if needs_resync:
            self._check_new_emails()

    def _check_new_emails(self):
        """检查新邮件"""
        try:
            if HAS_IMAPCLIENT:
                messages = self._client.search()
            else:
                status, messages = self._client.search(None, 'UNREAD')
                messages = messages[0].split()

            current_ids = set(str(m) for m in messages)
            new_ids = current_ids - self._seen_ids

            if new_ids:
                logger.info(f"Found {len(new_ids)} new emails for {self.account.email}")
                self._fetch_and_notify_new_emails(new_ids)
                self._seen_ids.update(new_ids)

        except Exception as e:
            logger.error(f"Failed to check new emails: {e}")

    def _fetch_and_notify_new_emails(self, message_ids):
        """获取新邮件并发送通知"""
        for msg_id in message_ids:
            try:
                email = self._fetch_email(msg_id)
                if email and email.should_notify(self.account):
                    self._stats.new_emails += 1
                    self._stats.last_email_time = time.time()
                    self.on_new_email(email)
            except Exception as e:
                logger.error(f"Failed to fetch email {msg_id}: {e}")

    def _fetch_email(self, msg_id: str):
        """获取单封邮件"""
        from .email_account import EmailMessage

        try:
            if HAS_IMAPCLIENT:
                msg_data = self._client.fetch([msg_id], ['FLAGS', 'ENVELOPE', 'BODY[TEXT]'])
            else:
                status, msg_data = self._client.fetch(msg_id, '(FLAGS ENVELOPE BODY[TEXT])')
                msg_data = {msg_id: msg_data}

            if not msg_data:
                return None

            data = msg_data.get(msg_id)
            if not data:
                return None

            # 解析邮件
            email = EmailMessage(
                message_id=str(msg_id),
                account_id=self.account.account_id,
            )

            # 解析 ENVELOPE 获取发件人、主题等
            if 'ENVELOPE' in str(data):
                # 简化解析
                pass

            # 检查 UNREAD 标志
            if HAS_IMAPCLIENT:
                flags = data.get(b'FLAGS', [])
                email.flags = [f.decode() if isinstance(f, bytes) else str(f) for f in flags]
            else:
                # imaplib 格式
                pass

            self._stats.total_emails += 1
            return email

        except Exception as e:
            logger.error(f"Error fetching email {msg_id}: {e}")
            return None

    def test_connection(self) -> tuple:
        """
        测试连接

        Returns:
            (success: bool, message: str)
        """
        try:
            if HAS_IMAPCLIENT:
                client = IMAPClient(self.account.imap_host, port=self.account.imap_port, ssl=self.account.use_ssl)
                client.login(self.account.username, self.account.auth_code)
                client.select_folder(self.account.folder)
                client.logout()
                return True, "连接成功"
            else:
                if self.account.use_ssl:
                    client = imaplib.IMAP4_SSL(self.account.imap_host, self.account.imap_port)
                else:
                    client = imaplib.IMAP4(self.account.imap_host, self.account.imap_port)
                client.login(self.account.username, self.account.auth_code)
                client.select(self.account.folder)
                client.logout()
                return True, "连接成功"
        except Exception as e:
            return False, f"连接失败: {str(e)}"


class IMAPListenerManager:
    """
    IMAP 监听管理器

    管理多个邮箱账户的监听器。
    """

    def __init__(self):
        self._listeners: Dict[str, IMAPListener] = {}
        self._lock = threading.Lock()

    def add_account(
        self,
        account,
        on_new_email: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ) -> IMAPListener:
        """
        添加账户监听

        Args:
            account: EmailAccount 实例
            on_new_email: 新邮件回调
            on_error: 错误回调

        Returns:
            IMAPListener 实例
        """
        with self._lock:
            # 停止已有的
            if account.account_id in self._listeners:
                self.remove_account(account.account_id)

            listener = IMAPListener(
                account=account,
                on_new_email=on_new_email or self._default_on_new_email,
                on_error=on_error or self._default_on_error,
            )
            self._listeners[account.account_id] = listener
            return listener

    def remove_account(self, account_id: str):
        """移除账户监听"""
        with self._lock:
            if account_id in self._listeners:
                self._listeners[account_id].stop()
                del self._listeners[account_id]

    def start_account(self, account_id: str):
        """启动账户监听"""
        with self._lock:
            if account_id in self._listeners:
                self._listeners[account_id].start()

    def stop_account(self, account_id: str):
        """停止账户监听"""
        with self._lock:
            if account_id in self._listeners:
                self._listeners[account_id].stop()

    def start_all(self):
        """启动所有监听"""
        with self._lock:
            for listener in self._listeners.values():
                listener.start()

    def stop_all(self):
        """停止所有监听"""
        with self._lock:
            for listener in self._listeners.values():
                listener.stop()

    def get_listener(self, account_id: str) -> Optional[IMAPListener]:
        """获取监听器"""
        return self._listeners.get(account_id)

    def get_all_stats(self) -> Dict[str, ListenerStats]:
        """获取所有统计"""
        return {aid: l.stats for aid, l in self._listeners.items()}

    def _default_on_new_email(self, email):
        """默认新邮件处理"""
        logger.info(f"New email: {email.subject} from {email.sender}")

    def _default_on_error(self, error):
        """默认错误处理"""
        logger.error(f"Listener error: {error}")
