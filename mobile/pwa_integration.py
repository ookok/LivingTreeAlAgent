"""
PWA 集成模块
=============

移动端 PWA 支持，提供离线能力和原生体验

功能:
- Service Worker 注册
- 离线存储
- 推送通知
- 背景同步
"""

import json
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PWAConfig:
    """PWA 配置"""
    name: str = "Hermes Desktop"
    short_name: str = "Hermes"
    description: str = "智能 AI 助手"
    start_url: str = "/"
    display: str = "standalone"  # standalone/minimal-ui/fullscreen
    background_color: str = "#1e1e1e"
    theme_color: str = "#007acc"
    orientation: str = "any"  # any/portrait/landscape
    icons: List[Dict] = field(default_factory=list)
    categories: List[str] = field(default_factory=lambda: ["productivity", "utilities"])


@dataclass
class CacheConfig:
    """缓存配置"""
    name: str = "hermes-cache-v1"
    strategy: str = "cache-first"  # cache-first/network-first/stale-while-revalidate
    max_size: int = 100  # 最大缓存条目数
    max_age: int = 86400 * 7  # 7天


class PWAManager:
    """
    PWA 管理器

    提供:
    - Service Worker 注册
    - 缓存管理
    - 推送通知
    - 背景同步
    """

    def __init__(self, config: PWAConfig = None):
        self.config = config or PWAConfig()
        self._registered = False
        self._sw_registration: Optional[Any] = None

    def get_manifest(self) -> Dict[str, Any]:
        """获取 PWA Manifest"""
        return {
            "name": self.config.name,
            "short_name": self.config.short_name,
            "description": self.config.description,
            "start_url": self.config.start_url,
            "display": self.config.display,
            "background_color": self.config.background_color,
            "theme_color": self.config.theme_color,
            "orientation": self.config.orientation,
            "icons": self.config.icons or [
                {
                    "src": "/icons/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png"
                },
                {
                    "src": "/icons/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png"
                },
                {
                    "src": "/icons/icon-maskable.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable"
                }
            ],
            "categories": self.config.categories,
            "lang": "zh-CN",
            "dir": "ltr",
            "scope": "/",
            "prefer_related_applications": False
        }

    def generate_service_worker_js(self, cache_config: CacheConfig = None) -> str:
        """
        生成 Service Worker JavaScript 代码

        Args:
            cache_config: 缓存配置

        Returns:
            Service Worker JavaScript 代码
        """
        cache_name = cache_config.name if cache_config else CacheConfig().name
        strategy = cache_config.strategy if cache_config else CacheConfig().strategy

        return f"""
// Hermes Desktop Service Worker
// =============================

const CACHE_NAME = '{cache_name}';
const OFFLINE_URL = '/offline.html';

// 核心资源
const CORE_ASSETS = [
    '/',
    '/index.html',
    '/manifest.json',
    '/icons/icon-192.png',
    '/icons/icon-512.png',
];

// 安装事件
self.addEventListener('install', (event) => {{
    console.log('[SW] Installing...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {{
                console.log('[SW] Precaching core assets');
                return cache.addAll(CORE_ASSETS);
            }})
            .then(() => self.skipWaiting())
    );
}});

// 激活事件
self.addEventListener('activate', (event) => {{
    console.log('[SW] Activating...');
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {{
                return Promise.all(
                    cacheNames
                        .filter((name) => name !== CACHE_NAME)
                        .map((name) => caches.delete(name))
                );
            }})
            .then(() => self.clients.claim())
    );
}});

// 请求拦截
self.addEventListener('fetch', (event) => {{
    const {{ request }} = event;
    const url = new URL(request.url);

    // 只处理同源请求
    if (url.origin !== location.origin) {{
        return;
    }}

    // {strategy} 策略
    event.respondWith(
        {self._get_strategy_code(strategy)}
    );
}});

// 背景同步
self.addEventListener('sync', (event) => {{
    console.log('[SW] Background sync:', event.tag);
    if (event.tag === 'sync-messages') {{
        event.waitUntil(syncMessages());
    }}
}});

// 推送通知
self.addEventListener('push', (event) => {{
    console.log('[SW] Push received');
    if (!event.data) return;

    const data = event.data.json();
    const options = {{
        body: data.body || 'You have a new message',
        icon: '/icons/icon-192.png',
        badge: '/icons/badge.png',
        vibrate: [100, 50, 100],
        data: {{
            url: data.url || '/'
        }},
        actions: [
            {{ action: 'open', title: 'Open' }},
            {{ action: 'close', title: 'Close' }}
        ]
    }};

    event.waitUntil(
        self.registration.showNotification(data.title || 'Hermes', options)
    );
}});

// 通知点击
self.addEventListener('notificationclick', (event) => {{
    event.notification.close();
    if (event.action === 'close') return;

    event.waitUntil(
        clients.openWindow(event.notification.data.url || '/')
    );
}});

// 辅助函数
async function syncMessages() {{
    // 从 IndexedDB 获取待同步消息
    const db = await openDB();
    const messages = await db.getAll('pending_messages');

    for (const msg of messages) {{
        try {{
            await fetch('/api/v1/messages/sync', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(msg)
            }});
            await db.delete('pending_messages', msg.id);
        }} catch (e) {{
            console.error('[SW] Sync failed:', e);
        }}
    }}
}}

function openDB() {{
    return new Promise((resolve, reject) => {{
        const request = indexedDB.open('hermes-pwa', 1);
        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result);
        request.onupgradeneeded = (event) => {{
            const db = event.target.result;
            if (!db.objectStoreNames.contains('pending_messages')) {{
                db.createObjectStore('pending_messages', {{ keyPath: 'id' }});
            }}
        }};
    }});
}}
"""

    def _get_strategy_code(self, strategy: str) -> str:
        """获取策略代码"""
        strategies = {
            "cache-first": """
        caches.match(request)
            .then((response) => {
                if (response) return response;
                return fetch(request)
                    .then((networkResponse) => {
                        if (!networkResponse || networkResponse.status !== 200) {
                            return networkResponse;
                        }
                        const responseClone = networkResponse.clone();
                        caches.open(CACHE_NAME)
                            .then((cache) => cache.put(request, responseClone));
                        return networkResponse;
                    });
            })
            """,
            "network-first": """
        fetch(request)
            .then((response) => {
                if (!response || response.status !== 200) {
                    return caches.match(request);
                }
                const responseClone = response.clone();
                caches.open(CACHE_NAME)
                    .then((cache) => cache.put(request, responseClone));
                return response;
            })
            .catch(() => caches.match(request))
            """,
            "stale-while-revalidate": """
        const cachedResponse = await caches.match(request);
        const fetchPromise = fetch(request)
            .then((networkResponse) => {
                if (!networkResponse || networkResponse.status !== 200) {
                    return networkResponse;
                }
                const responseClone = networkResponse.clone();
                caches.open(CACHE_NAME)
                    .then((cache) => cache.put(request, responseClone));
                return networkResponse;
            });
        return cachedResponse || fetchPromise;
            """
        }
        return strategies.get(strategy, strategies["cache-first"])

    async def register_service_worker(self) -> bool:
        """
        注册 Service Worker

        Returns:
            是否注册成功
        """
        if not (hasattr(self, '_is_browser') and self._is_browser()):
            return False

        try:
            # 动态导入
            import js
            sw_js = self.generate_service_worker_js()

            # 创建 Blob
            blob = js.Blob.new([sw_js], {"type": "application/javascript"})
            sw_url = js.URL.createObjectURL(blob)

            # 注册
            registration = await js.navigator.serviceWorker.register(sw_url)
            self._sw_registration = registration
            self._registered = True
            print(f"[PWA] Service Worker registered: {registration.active}")
            return True

        except Exception as e:
            print(f"[PWA] Registration failed: {e}")
            return False

    async def request_notification_permission(self) -> bool:
        """请求通知权限"""
        if not (hasattr(self, '_is_browser') and self._is_browser()):
            return False

        try:
            import js
            result = await js.Notification.requestPermission()
            return result == "granted"
        except Exception as e:
            print(f"[PWA] Notification permission failed: {e}")
            return False

    async def show_notification(
        self,
        title: str,
        body: str,
        icon: str = None,
        url: str = None
    ):
        """显示通知"""
        try:
            import js
            if hasattr(js, 'Notification') and js.Notification.permission == "granted":
                options = {
                    "body": body,
                    "icon": icon or "/icons/icon-192.png",
                    "badge": "/icons/badge.png",
                    "requireInteraction": False
                }
                if url:
                    notification = js.Notification.new(title, options)
                    notification.onclick = js.Function.new(
                        "(event) => { window.open(arguments[0]); }",
                        url
                    )
                else:
                    js.Notification.new(title, options)
        except Exception as e:
            print(f"[PWA] Show notification failed: {e}")

    def _is_browser(self) -> bool:
        """检测是否在浏览器环境"""
        try:
            import js
            return hasattr(js, 'navigator') and hasattr(js, 'window')
        except ImportError:
            return False


# ==================== 离线存储 ====================

class OfflineStorage:
    """
    离线存储管理器

    使用 IndexedDB 实现离线数据持久化
    """

    DB_NAME = "hermes-offline"
    DB_VERSION = 1

    def __init__(self):
        self._db = None

    async def init(self):
        """初始化数据库"""
        if self._db:
            return

        try:
            import js
            request = js.indexedDB.open(self.DB_NAME, self.DB_VERSION)

            def on_upgrade_needed(event):
                db = event.target.result
                # 消息存储
                if not db.objectStoreNames.contains("messages"):
                    msg_store = db.createObjectStore("messages", keyPath="id")
                    msg_store.createIndex("session_id", "session_id")
                    msg_store.createIndex("timestamp", "timestamp")

                # 记忆存储
                if not db.objectStoreNames.contains("memories"):
                    mem_store = db.createObjectStore("memories", keyPath="id")
                    mem_store.createIndex("type", "type")
                    mem_store.createIndex("timestamp", "timestamp")

                # 文件缓存
                if not db.objectStoreNames.contains("files"):
                    db.createObjectStore("files", keyPath="id")

            request.onupgradeneeded = on_upgrade_needed

            self._db = await self._wait_for_request(request)

        except ImportError:
            print("[OfflineStorage] Not in browser environment")

    async def _wait_for_request(self, request):
        """等待 IndexedDB 请求完成"""
        import js
        return await js.Promise.new(lambda resolve, reject: None)

    # ==================== 消息操作 ====================

    async def save_message(self, message: Dict):
        """保存消息"""
        if not self._db:
            await self.init()

        try:
            import js
            tx = self._db.transaction("messages", "readwrite")
            store = tx.objectStore("messages")
            await store.put(message)
        except Exception as e:
            print(f"[OfflineStorage] Save message failed: {e}")

    async def get_messages(self, session_id: str, limit: int = 50) -> List[Dict]:
        """获取消息"""
        if not self._db:
            await self.init()

        try:
            import js
            tx = self._db.transaction("messages", "readonly")
            store = tx.objectStore("messages")
            index = store.index("session_id")

            messages = []
            cursor = await index.openCursor(session_id)

            while cursor:
                messages.append(cursor.value)
                if len(messages) >= limit:
                    break
                cursor = await cursor.continue()

            return messages

        except Exception as e:
            print(f"[OfflineStorage] Get messages failed: {e}")
            return []

    # ==================== 记忆操作 ====================

    async def save_memory(self, memory: Dict):
        """保存记忆"""
        if not self._db:
            await self.init()

        try:
            import js
            tx = self._db.transaction("memories", "readwrite")
            store = tx.objectStore("memories")
            await store.put(memory)
        except Exception as e:
            print(f"[OfflineStorage] Save memory failed: {e}")

    async def search_memories(self, query: str) -> List[Dict]:
        """搜索记忆"""
        if not self._db:
            await self.init()

        try:
            import js
            tx = self._db.transaction("memories", "readonly")
            store = tx.objectStore("memories")
            memories = await store.getAll()

            # 简单关键词匹配
            results = [
                m for m in memories
                if query.lower() in m.get("content", "").lower()
            ]
            return results

        except Exception as e:
            print(f"[OfflineStorage] Search memories failed: {e}")
            return []

    # ==================== 文件操作 ====================

    async def cache_file(self, file_id: str, content: bytes, metadata: Dict = None):
        """缓存文件"""
        if not self._db:
            await self.init()

        try:
            import js
            tx = self._db.transaction("files", "readwrite")
            store = tx.objectStore("files")
            await store.put({
                "id": file_id,
                "content": content,
                "metadata": metadata or {},
                "timestamp": time.time()
            })
        except Exception as e:
            print(f"[OfflineStorage] Cache file failed: {e}")

    async def get_cached_file(self, file_id: str) -> Optional[Dict]:
        """获取缓存文件"""
        if not self._db:
            await self.init()

        try:
            import js
            tx = self._db.transaction("files", "readonly")
            store = tx.objectStore("files")
            return await store.get(file_id)
        except Exception as e:
            print(f"[OfflineStorage] Get cached file failed: {e}")
            return None


# 全局实例
_pwa_manager: Optional[PWAManager] = None
_offline_storage: Optional[OfflineStorage] = None


def get_pwa_manager() -> PWAManager:
    """获取 PWA 管理器"""
    global _pwa_manager
    if _pwa_manager is None:
        _pwa_manager = PWAManager()
    return _pwa_manager


def get_offline_storage() -> OfflineStorage:
    """获取离线存储"""
    global _offline_storage
    if _offline_storage is None:
        _offline_storage = OfflineStorage()
    return _offline_storage
