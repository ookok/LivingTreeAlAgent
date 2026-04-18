"""
Service Worker - PWA离线支持
"""

// Service Worker版本
const CACHE_NAME = 'hermes-web-v1';
const API_CACHE_NAME = 'hermes-api-v1';

// 需要缓存的核心文件
const CORE_FILES = [
    '/',
    '/index.html',
    '/manifest.json',
];

// API缓存策略
const API_CACHE_STRATEGY = {
    '/api/status': 'network-first',  // 状态API优先网络
    '/api/route/test': 'network-only',  // 测试API只用网络
    '/api/route/list': 'cache-first',  // 路由列表优先缓存
};

// 安装事件
self.addEventListener('install', (event) => {
    console.log('[SW] Installing...');

    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[SW] Caching core files');
                return cache.addAll(CORE_FILES);
            })
            .then(() => {
                console.log('[SW] Skip waiting');
                return self.skipWaiting();
            })
    );
});

// 激活事件
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating...');

    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((name) => name !== CACHE_NAME && name !== API_CACHE_NAME)
                        .map((name) => {
                            console.log('[SW] Deleting old cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => {
                console.log('[SW] Claiming clients');
                return self.clients.claim();
            })
    );
});

// 请求拦截
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // API请求处理
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(handleAPIRequest(event.request));
        return;
    }

    // 静态资源处理
    event.respondWith(handleStaticRequest(event.request));
});

// 处理API请求
async function handleAPIRequest(request) {
    const url = new URL(request.url);
    const strategy = API_CACHE_STRATEGY[url.pathname] || 'network-first';

    if (strategy === 'network-only') {
        // 纯网络策略
        try {
            const response = await fetch(request);
            return response;
        } catch (error) {
            return new Response(
                JSON.stringify({ error: 'Network unavailable' }),
                { status: 503, headers: { 'Content-Type': 'application/json' } }
            );
        }
    }

    if (strategy === 'network-first') {
        // 网络优先
        try {
            const response = await fetch(request);
            // 缓存成功的响应
            if (response.ok) {
                const cache = await caches.open(API_CACHE_NAME);
                cache.put(request, response.clone());
            }
            return response;
        } catch (error) {
            // 网络失败，尝试缓存
            const cached = await caches.match(request);
            if (cached) {
                return cached;
            }
            return new Response(
                JSON.stringify({ error: 'Offline' }),
                { status: 503, headers: { 'Content-Type': 'application/json' } }
            );
        }
    }

    if (strategy === 'cache-first') {
        // 缓存优先
        const cached = await caches.match(request);
        if (cached) {
            // 后台更新缓存
            fetch(request)
                .then((response) => {
                    if (response.ok) {
                        caches.open(API_CACHE_NAME)
                            .then((cache) => cache.put(request, response));
                    }
                })
                .catch(() => {});

            return cached;
        }

        try {
            const response = await fetch(request);
            if (response.ok) {
                const cache = await caches.open(API_CACHE_NAME);
                cache.put(request, response.clone());
            }
            return response;
        } catch (error) {
            return new Response(
                JSON.stringify({ error: 'Offline and no cache' }),
                { status: 503, headers: { 'Content-Type': 'application/json' } }
            );
        }
    }
}

// 处理静态请求
async function handleStaticRequest(request) {
    const cached = await caches.match(request);

    if (cached) {
        // 后台更新
        fetch(request)
            .then((response) => {
                if (response.ok) {
                    caches.open(CACHE_NAME)
                        .then((cache) => cache.put(request, response));
                }
            })
            .catch(() => {});

        return cached;
    }

    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        // 离线且没有缓存
        if (request.mode === 'navigate') {
            return caches.match('/index.html');
        }
        return new Response('Offline', { status: 503 });
    }
}

// 推送通知
self.addEventListener('push', (event) => {
    if (!event.data) return;

    const data = event.data.json();

    const options = {
        body: data.body || '您有新的更新',
        icon: '/icons/icon-192.png',
        badge: '/icons/badge.png',
        vibrate: [100, 50, 100],
        data: {
            url: data.url || '/',
        },
        actions: [
            { action: 'open', title: '查看' },
            { action: 'dismiss', title: '忽略' },
        ],
    };

    event.waitUntil(
        self.registration.showNotification(data.title || 'Hermes Desktop', options)
    );
});

// 通知点击
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    if (event.action === 'dismiss') {
        return;
    }

    const url = event.notification.data?.url || '/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                // 聚焦已有窗口或打开新窗口
                for (const client of clientList) {
                    if (client.url === url && 'focus' in client) {
                        return client.focus();
                    }
                }
                return clients.openWindow(url);
            })
    );
});

// 后台同步
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-status') {
        event.waitUntil(syncStatus());
    }
});

async function syncStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        // 通知所有客户端
        const clients = await self.clients.matchAll();
        clients.forEach((client) => {
            client.postMessage({
                type: 'status_update',
                data: data,
            });
        });
    } catch (error) {
        console.error('[SW] Sync failed:', error);
    }
}