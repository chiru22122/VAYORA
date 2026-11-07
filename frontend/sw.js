// VAYORA Service Worker for Progressive Web App (PWA)
const CACHE_NAME = 'vayora-shell-v12';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/dashboard.html',
  '/send.html',
  '/receive.html',
  '/wallet.html',
  '/convert.html',
  '/card.html',
  '/transactions.html',
  '/css/global.css',
  '/css/dashboard.css',
  '/css/card.css',
  '/js/api.js',
  '/js/card.js',
  '/js/payments.js',
  '/js/jsqr.min.js',
  '/js/qrcode.min.js',
  '/manifest.json',
  '/assets/icon-192.png',
  '/assets/icon-512.png',
  '/assets/favicon.ico'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // Use no-cache reload to guarantee pristine asset cache
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('VAYORA SW: non-fatal caching warning:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Network-only for API requests to ensure fresh ledger balances
  if (url.pathname.startsWith('/api/') || event.request.method !== 'GET') {
    return;
  }

  // Network-first with cache fallback for HTML, JS, and CSS files to guarantee immediate updates
  const isCodeAsset = url.pathname.endsWith('.js') || url.pathname.endsWith('.css') || url.pathname.endsWith('.html') || (event.request.headers.get('accept') && event.request.headers.get('accept').includes('text/html'));
  if (isCodeAsset) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response && response.status === 200) {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
          }
          return response;
        })
        .catch(() => caches.match(event.request).then((res) => res || (url.pathname.endsWith('.html') ? caches.match('/dashboard.html') : null)))
    );
    return;
  }

  // Cache-first / stale-while-revalidate for static assets
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        // Fetch fresh copy in background to revalidate
        fetch(event.request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, networkResponse));
          }
        }).catch(() => { });
        return cachedResponse;
      }
      return fetch(event.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
        }
        return networkResponse;
      });
    })
  );
});
