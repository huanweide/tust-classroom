const CACHE = "tust-v3";
const ASSETS = ["./", "./index.html", "./manifest.json"];

// Install: cache shell assets
self.addEventListener("install", (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
});

// Activate: clean old caches, take over immediately
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  clients.claim();
});

// Fetch: stale-while-revalidate for HTML, cache JSON on fetch
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // Stale-while-revalidate for shell (show cache, update in background)
  if (e.request.destination === "document" || url.pathname.endsWith(".html")) {
    e.respondWith(
      caches.open(CACHE).then((cache) =>
        cache.match(e.request).then((cached) => {
          const fetchPromise = fetch(e.request).then((resp) => {
            cache.put(e.request, resp.clone());
            return resp;
          });
          return cached || fetchPromise;
        })
      )
    );
    return;
  }

  // Cache JSON data on fetch (network-first, fallback to cache)
  if (url.pathname.includes("/data/")) {
    e.respondWith(
      fetch(e.request)
        .then((resp) => {
          const clone = resp.clone();
          caches.open(CACHE).then((c) => c.put(e.request, clone));
          return resp;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Default: cache-first, fallback to network
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
