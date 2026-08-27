// Orbit CRM service worker — enables "Install App" / Add to Home Screen.
// Leads, quotes and notifications change constantly, so this deliberately does NOT
// cache pages or API responses (no stale data risk). It only caches the static
// app-shell assets (css/js/icons) so the install prompt qualifies and repeat loads
// of those files are instant.

const CACHE_NAME = 'orbit-crm-shell-v1';
const SHELL_ASSETS = [
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/js/charts.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .catch(() => {}) // don't block install if an asset 404s
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return; // never intercept POSTs (form submits, webhooks)

  const url = new URL(req.url);
  const isShellAsset = SHELL_ASSETS.some((path) => url.pathname === path);

  if (isShellAsset) {
    // Cache-first for the static shell — fall back to network if not cached yet.
    event.respondWith(
      caches.match(req).then((cached) => cached || fetch(req))
    );
    return;
  }

  // Everything else (pages, /api/*, leads data) — always go to the network.
  // Live CRM data must never be served stale from cache.
});
