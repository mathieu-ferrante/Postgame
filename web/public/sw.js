// Service worker minimal : l'interface s'ouvre même sans réseau (coquille en cache) ;
// les données de l'API sont toujours demandées au service, avec repli sur le cache.
const CACHE = "postgame-v2";
const COQUILLE = ["/", "/index.html", "/manifest.webmanifest", "/icone.svg"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(COQUILLE)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((cles) => Promise.all(cles.filter((k) => k !== CACHE).map((k) => caches.delete(k)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/api/")) {
    // Réseau d'abord : les données doivent être fraîches.
    e.respondWith(
      fetch(e.request)
        .then((r) => {
          if (r.ok) caches.open(CACHE).then((c) => c.put(e.request, r.clone()));
          return r;
        })
        .catch(() => caches.match(e.request)),
    );
    return;
  }
  // Pages (navigation) : réseau d'abord, pour toujours charger la dernière version de
  // l'appli ; hors ligne, la coquille en cache.
  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request)
        .then((r) => {
          if (r.ok) caches.open(CACHE).then((c) => c.put("/index.html", r.clone()));
          return r;
        })
        .catch(() => caches.match("/index.html")),
    );
    return;
  }
  // Fichiers de l'appli (noms versionnés par Vite, donc immuables) : cache d'abord.
  e.respondWith(
    caches.match(e.request).then(
      (r) =>
        r ||
        fetch(e.request)
          .then((rep) => {
            if (rep.ok) caches.open(CACHE).then((c) => c.put(e.request, rep.clone()));
            return rep;
          })
          .catch(() => Response.error()),
    ),
  );
});
