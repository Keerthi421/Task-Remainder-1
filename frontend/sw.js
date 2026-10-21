const CACHE = 'task-reminder-v3';
const STATIC_ASSETS = [
  '/static/style.css',
  '/static/script.js',
  '/login',
  '/app',
  '/',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Network-first so new deploys show up immediately; the cache is only an offline fallback.
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    fetch(e.request)
      .then(r => {
        if (r.ok) { const c = r.clone(); caches.open(CACHE).then(cache => cache.put(e.request, c)); }
        return r;
      })
      .catch(() => caches.match(e.request))
  );
});
