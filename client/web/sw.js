// LivingTree Service Worker v2 — offline cache + push notifications + badge
const CACHE = 'livingtree-v5';
const ASSETS = ['/tree/living','/tree/chat','/tree/dashboard','/tree/theme/dark','/tree/theme/kami'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(caches.match(e.request).then(cached => {
    const fetched = fetch(e.request).then(r => { if (r.ok) { const clone = r.clone(); caches.open(CACHE).then(c => c.put(e.request, clone)); } return r; }).catch(() => cached);
    return cached || fetched;
  }));
});

// ═══ Push Notifications ═══
self.addEventListener('push', e => {
  let data = { title: '小树', body: '有新消息', icon: '/assets/icon.svg', badge: '/assets/icon.svg' };
  try { data = e.data.json(); } catch(_) { if (e.data) data.body = e.data.text(); }
  e.waitUntil(self.registration.showNotification(data.title, {
    body: data.body, icon: data.icon, badge: data.badge, tag: data.tag || 'lt-notify',
    data: { url: data.url || '/tree/living' },
    vibrate: [200, 100, 200],
    actions: data.actions || [{ action: 'open', title: '打开' }, { action: 'dismiss', title: '忽略' }],
    requireInteraction: data.requireInteraction || false,
  }));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  if (e.action === 'dismiss') return;
  e.waitUntil(clients.matchAll({ type: 'window' }).then(cs => {
    const url = e.notification.data.url || '/tree/living';
    for (const c of cs) { if (c.url.includes(url.split('/')[2]) && 'focus' in c) { c.focus(); return; } }
    if (clients.openWindow) return clients.openWindow(url);
  }));
});

// ═══ Badge ═══
self.addEventListener('message', e => {
  if (e.data.type === 'SET_BADGE' && 'setAppBadge' in navigator) {
    navigator.setAppBadge(e.data.count).catch(() => {});
  } else if (e.data.type === 'CLEAR_BADGE' && 'clearAppBadge' in navigator) {
    navigator.clearAppBadge().catch(() => {});
  }
});
