/* ═══════════════════════════════════
   LivingTree — Service Worker
   Cache-first strategy: instant reloads, offline-ready
   ═══════════════════════════════════ */

const CACHE = 'lt-v2';
const ASSETS = [
  '/', '/index.html', '/login.html', '/search.html', '/map.html', '/card.html',
  '/auto-fill.html', '/diagram.html', '/app.js',
  '/css/tokens.css', '/css/layout.css', '/css/app.css',
  '/core/framework.js', '/services/store.js', '/services/api.js',
  '/services/renderer.js', '/services/share.js', '/services/x6-graph.js',
  '/services/x6-diagram.js', '/services/cards.js', '/services/onlyoffice.js',
  '/services/page-agent-bridge.js', '/services/login.js',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

// Cache-first for static assets, network-first for API
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/api/')) return; // Bypass API
  if (url.pathname.includes('monaco')) return;   // Bypass CDN

  e.respondWith(
    caches.match(e.request).then(cached =>
      cached || fetch(e.request).then(resp => {
        if (resp.ok && resp.type === 'basic') {
          const clone = resp.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return resp;
      })
    )
  );
});
