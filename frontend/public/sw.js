/**
 * Cleanable — Service Worker
 * ============================
 *
 * Production service worker for the Cleanable platform.
 *
 * Strategies:
 *   • App shell (HTML/JS/CSS)   → Cache-first with network fallback
 *   • API responses             → Network-first with cache fallback (stale-while-revalidate)
 *   • Static assets (images)    → Cache-first, long TTL
 *   • GPS location data         → Background Sync queue for offline resilience
 *   • WebSocket reconnect       → Exponential backoff on connection loss
 *
 * Cache Versioning:
 *   Bump CACHE_VERSION on deploy to invalidate stale caches.
 */

const CACHE_VERSION = "v1";
const APP_SHELL_CACHE = `cleanable-shell-${CACHE_VERSION}`;
const API_CACHE = `cleanable-api-${CACHE_VERSION}`;
const STATIC_CACHE = `cleanable-static-${CACHE_VERSION}`;
const GPS_SYNC_TAG = "gps-background-sync";
const GPS_QUEUE_KEY = "cleanable-gps-queue";

// ── App Shell — precached on install ────────────────────────────────

const APP_SHELL_URLS = [
  "/",
  "/login",
  "/register",
  "/offline",
  "/manifest.json",
];

// ── Cache Strategies ────────────────────────────────────────────────

/**
 * Network patterns to match for each strategy.
 */
const API_PATTERNS = [
  /\/api\/v1\//,
];

const STATIC_PATTERNS = [
  /\/_next\/static\//,
  /\/_next\/image\//,
  /\.(?:png|jpg|jpeg|gif|webp|avif|svg|ico)$/,
  /\.(?:woff2?|ttf|eot)$/,
];

const SKIP_PATTERNS = [
  /\/api\/v1\/auth\/token\/refresh/,
  /\/api\/v1\/iot\/gps\/report/,
  /\/ws\//,
  /chrome-extension/,
];

// ── Install ─────────────────────────────────────────────────────────

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(APP_SHELL_CACHE).then((cache) => {
      return cache.addAll(APP_SHELL_URLS).catch((err) => {
        // Non-fatal — pages may not exist yet in dev
        console.warn("[SW] Precache partial failure:", err.message);
      });
    })
  );
  // Activate immediately without waiting for old tabs to close
  self.skipWaiting();
});

// ── Activate — purge old caches ─────────────────────────────────────

self.addEventListener("activate", (event) => {
  const CURRENT_CACHES = new Set([APP_SHELL_CACHE, API_CACHE, STATIC_CACHE]);

  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => !CURRENT_CACHES.has(key))
          .map((key) => {
            console.log("[SW] Purging old cache:", key);
            return caches.delete(key);
          })
      )
    )
  );
  // Take control of all open clients immediately
  self.clients.claim();
});

// ── Fetch — routing by strategy ─────────────────────────────────────

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET, non-HTTP, and excluded patterns
  if (request.method !== "GET") return;
  if (!url.protocol.startsWith("http")) return;
  if (SKIP_PATTERNS.some((p) => p.test(url.pathname))) return;

  // Strategy 1: Static assets → Cache-first
  if (STATIC_PATTERNS.some((p) => p.test(url.pathname))) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  // Strategy 2: API → Network-first (stale-while-revalidate)
  if (API_PATTERNS.some((p) => p.test(url.pathname))) {
    event.respondWith(networkFirst(request, API_CACHE));
    return;
  }

  // Strategy 3: Navigation / App Shell → Cache-first with network fallback
  if (request.mode === "navigate" || request.destination === "document") {
    event.respondWith(appShellFetch(request));
    return;
  }

  // Strategy 4: Everything else → Cache-first
  event.respondWith(cacheFirst(request, STATIC_CACHE));
});

// ── Cache-First ─────────────────────────────────────────────────────

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response("Offline", { status: 503, statusText: "Service Unavailable" });
  }
}

// ── Network-First (Stale-While-Revalidate for API) ──────────────────

async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response(
      JSON.stringify({ error: "offline", message: "You are offline. Cached data may be stale." }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }
}

// ── App Shell Fetch (navigation) ────────────────────────────────────

async function appShellFetch(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(APP_SHELL_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // Try cached version of requested page
    const cached = await caches.match(request);
    if (cached) return cached;

    // Fall back to offline page
    const offlinePage = await caches.match("/offline");
    if (offlinePage) return offlinePage;

    return new Response(
      "<html><body><h1>Cleanable</h1><p>You are offline. Please check your connection.</p></body></html>",
      { status: 503, headers: { "Content-Type": "text/html" } }
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
//  BACKGROUND SYNC — GPS Location Queue
// ═══════════════════════════════════════════════════════════════════
//
//  When the Service Pro app is offline or has poor connectivity,
//  GPS readings are queued in IndexedDB and synced when the device
//  regains connectivity via the Background Sync API.
//
//  Flow:
//    1. Main thread calls navigator.serviceWorker.controller.postMessage
//       with type "queue-gps" and GPS payload
//    2. SW writes to IndexedDB queue
//    3. SW registers a sync event
//    4. Browser fires "sync" when connectivity returns
//    5. SW drains the queue, POSTing each reading to the Django API
// ═══════════════════════════════════════════════════════════════════

// ── IndexedDB Helpers ───────────────────────────────────────────────

function openGPSDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("cleanable-gps", 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("queue")) {
        db.createObjectStore("queue", { autoIncrement: true });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function enqueueGPS(data) {
  const db = await openGPSDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("queue", "readwrite");
    tx.objectStore("queue").add(data);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function drainGPSQueue() {
  const db = await openGPSDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("queue", "readwrite");
    const store = tx.objectStore("queue");
    const items = [];

    const cursor = store.openCursor();
    cursor.onsuccess = () => {
      const c = cursor.result;
      if (c) {
        items.push({ key: c.key, value: c.value });
        c.continue();
      } else {
        resolve(items);
      }
    };
    cursor.onerror = () => reject(cursor.error);
  });
}

async function deleteGPSEntry(key) {
  const db = await openGPSDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("queue", "readwrite");
    tx.objectStore("queue").delete(key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

// ── Message Handler — receive GPS data from main thread ─────────────

self.addEventListener("message", (event) => {
  const { type, payload } = event.data || {};

  if (type === "queue-gps") {
    event.waitUntil(
      enqueueGPS(payload).then(() => {
        // Register background sync
        return self.registration.sync.register(GPS_SYNC_TAG).catch(() => {
          // Sync API not supported — try immediate flush
          return flushGPSQueue(payload.token);
        });
      })
    );
  }

  if (type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

// ── Background Sync Handler ────────────────────────────────────────

self.addEventListener("sync", (event) => {
  if (event.tag === GPS_SYNC_TAG) {
    event.waitUntil(flushGPSQueue());
  }
});

/**
 * Drain the IndexedDB GPS queue and POST each entry to the API.
 * Entries that succeed are deleted; failures remain for the next sync.
 */
async function flushGPSQueue(tokenOverride) {
  const items = await drainGPSQueue();
  if (items.length === 0) return;

  console.log(`[SW] Flushing ${items.length} queued GPS readings`);

  for (const { key, value } of items) {
    try {
      const token = tokenOverride || value._token;
      const { _token, ...body } = value;

      const response = await fetch("/api/v1/iot/gps/report/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
      });

      if (response.ok || response.status === 409) {
        // 409 = duplicate/already-reported — safe to remove
        await deleteGPSEntry(key);
        console.log(`[SW] GPS entry ${key} synced`);
      } else if (response.status === 401) {
        // Token expired — can't sync, leave in queue for next attempt
        console.warn("[SW] GPS sync 401 — token expired, keeping in queue");
        break;
      } else {
        console.warn(`[SW] GPS sync failed (${response.status}), will retry`);
      }
    } catch (err) {
      console.warn("[SW] GPS sync network error:", err.message);
      // Leave in queue — will retry on next sync event
    }
  }

  // Notify connected clients
  const clients = await self.clients.matchAll();
  const remaining = await drainGPSQueue();
  clients.forEach((client) => {
    client.postMessage({
      type: "gps-sync-status",
      synced: items.length - remaining.length,
      remaining: remaining.length,
    });
  });
}

// ── Periodic Sync (if browser supports it) ──────────────────────────

self.addEventListener("periodicsync", (event) => {
  if (event.tag === "gps-periodic-flush") {
    event.waitUntil(flushGPSQueue());
  }
});

// ── Push Notifications (future) ─────────────────────────────────────

self.addEventListener("push", (event) => {
  if (!event.data) return;

  const data = event.data.json();
  const title = data.title || "Cleanable";
  const options = {
    body: data.body || "",
    icon: "/icons/icon-192x192.png",
    badge: "/icons/icon-72x72.png",
    tag: data.tag || "cleanable-notification",
    data: { url: data.url || "/" },
    actions: data.actions || [],
    vibrate: [100, 50, 100],
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clients) => {
      // Focus existing tab if open
      for (const client of clients) {
        if (client.url.includes(url) && "focus" in client) {
          return client.focus();
        }
      }
      // Otherwise open new tab
      return self.clients.openWindow(url);
    })
  );
});
