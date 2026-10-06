// PEPS ALARM service worker.
//
// This app shows LIVE inventory/expiration data -- serving a stale cached
// dashboard would be actively dangerous (you'd think a product is fine
// when it already expired). So this worker is network-first and only
// exists to make the app installable on phones; it is not an offline-data
// cache. We only pre-cache the static shell (icons, manifest).
const CACHE_NAME = "peps-alarm-shell-v1";
const SHELL_ASSETS = [
    "/static/manifest.json",
    "/static/icon-192.png",
    "/static/icon-512.png",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
    event.respondWith(
        fetch(event.request).catch(() => caches.match(event.request))
    );
});

// Notificaciones push: el servidor manda un payload JSON {title, body} y
// aqui lo mostramos como notificacion del sistema operativo.
self.addEventListener("push", (event) => {
    let datos = { title: "PEPS ALARM", body: "Tienes una alerta nueva." };
    if (event.data) {
        try {
            datos = event.data.json();
        } catch (err) {
            datos.body = event.data.text();
        }
    }
    event.waitUntil(
        self.registration.showNotification(datos.title || "PEPS ALARM", {
            body: datos.body || "",
            icon: "/static/icon-192.png",
            badge: "/static/icon-192.png",
        })
    );
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    event.waitUntil(clients.openWindow("/dashboard"));
});
