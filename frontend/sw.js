const CACHE = 'task-reminder-v2';
const STATIC_ASSETS = [
  '/static/style.css',
  '/static/script.js',
  '/login',
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

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  // Network-first for API calls
  if (['/tasks', '/users', '/templates', '/token', '/register'].some(p => url.pathname.startsWith(p))) {
    e.respondWith(
      fetch(e.request)
        .then(r => { const c = r.clone(); caches.open(CACHE).then(cache => cache.put(e.request, c)); return r; })
        .catch(() => caches.match(e.request))
    );
    return;
  }
  // Cache-first for static
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request).then(resp => {
      const c = resp.clone();
      caches.open(CACHE).then(cache => cache.put(e.request, c));
      return resp;
    }))
  );
});
