/** LivingTree Service Worker — offline-first PWA */

const CACHE = 'livingtree-v1';
const ASSETS = [
  '/tree/living',
  '/tree/awakening',
  '/js/living-canvas.js',
  '/manifest.json',
];

// Install: pre-cache static assets
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

// Fetch: cache-first for assets, network-first for API
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // API calls: network-first, fallback to offline queue
  if(url.pathname.startsWith('/api/')) {
    e.respondWith(
      fetch(e.request).catch(() =>
        new Response(JSON.stringify({error:'offline',queued:true}), {
          status: 503,
          headers: {'Content-Type': 'application/json'},
        })
      )
    );
    return;
  }

  // Static assets: cache-first
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request).then(res => {
      if(res.ok) {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
      }
      return res;
    }))
  );
});

// Background sync: queue failed requests
self.addEventListener('sync', e => {
  if(e.tag === 'send-messages') {
    e.waitUntil(replayQueuedMessages());
  }
});

async function replayQueuedMessages() {
  // Replay messages stored in IndexedDB when online
  const clients = await self.clients.matchAll();
  clients.forEach(c => c.postMessage({type:'sync-complete'}));
}
