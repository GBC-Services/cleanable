/**
 * Service Worker Registration
 * ============================
 *
 * Registers the SW in production, handles updates, and exposes
 * the GPS background sync queue API.
 */

// ── Registration ────────────────────────────────────────────────────

let swRegistration: ServiceWorkerRegistration | null = null;

export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
    return null;
  }

  try {
    const registration = await navigator.serviceWorker.register("/sw.js", {
      scope: "/",
    });

    swRegistration = registration;

    // Listen for updates
    registration.addEventListener("updatefound", () => {
      const newWorker = registration.installing;
      if (!newWorker) return;

      newWorker.addEventListener("statechange", () => {
        if (
          newWorker.state === "installed" &&
          navigator.serviceWorker.controller
        ) {
          // New version available — notify the UI
          window.dispatchEvent(
            new CustomEvent("sw-update-available", { detail: registration })
          );
        }
      });
    });

    // Handle controller change (new SW took over)
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      // Reload only if user has accepted the update
      if (document.visibilityState === "visible") {
        window.location.reload();
      }
    });

    console.log("[App] Service Worker registered");
    return registration;
  } catch (err) {
    console.warn("[App] Service Worker registration failed:", err);
    return null;
  }
}

/**
 * Prompt the user to update and activate the new SW.
 */
export function applyServiceWorkerUpdate(registration: ServiceWorkerRegistration): void {
  const waiting = registration.waiting;
  if (waiting) {
    waiting.postMessage({ type: "SKIP_WAITING" });
  }
}

// ── GPS Background Sync Queue ───────────────────────────────────────

interface GPSPayload {
  booking_id: number;
  latitude: number;
  longitude: number;
  accuracy: number;
  heading: number | null;
  speed: number | null;
  timestamp: string;
}

/**
 * Queue a GPS reading for background sync.
 *
 * If the SW is active, sends the data via postMessage for IndexedDB
 * queueing + Background Sync registration.
 *
 * Falls back to direct fetch if SW is not available.
 */
export async function queueGPSReading(
  payload: GPSPayload,
  accessToken: string
): Promise<void> {
  const controller = navigator.serviceWorker?.controller;

  if (controller) {
    controller.postMessage({
      type: "queue-gps",
      payload: { ...payload, _token: accessToken },
    });
    return;
  }

  // Fallback: direct POST (no offline resilience)
  await fetch("/api/v1/iot/gps/report/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(payload),
  });
}

/**
 * Listen for sync status messages from the SW.
 */
export function onGPSSyncStatus(
  callback: (synced: number, remaining: number) => void
): () => void {
  const handler = (event: MessageEvent) => {
    if (event.data?.type === "gps-sync-status") {
      callback(event.data.synced, event.data.remaining);
    }
  };

  navigator.serviceWorker?.addEventListener("message", handler);
  return () => navigator.serviceWorker?.removeEventListener("message", handler);
}

/**
 * Listen for SW update availability.
 */
export function onSWUpdateAvailable(
  callback: (registration: ServiceWorkerRegistration) => void
): () => void {
  const handler = (event: Event) => {
    callback((event as CustomEvent).detail);
  };

  window.addEventListener("sw-update-available", handler);
  return () => window.removeEventListener("sw-update-available", handler);
}
