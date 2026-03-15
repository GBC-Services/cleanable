/**
 * Offline Fallback Page
 * ======================
 *
 * Displayed when the user is offline and the requested page
 * is not available in the Service Worker cache.
 */

"use client";

import { useEffect, useState } from "react";
import { WifiOff, RefreshCw } from "lucide-react";

export default function OfflinePage() {
  const [isOnline, setIsOnline] = useState(false);
  const [queuedCount, setQueuedCount] = useState(0);

  useEffect(() => {
    setIsOnline(navigator.onLine);

    const onOnline = () => setIsOnline(true);
    const onOffline = () => setIsOnline(false);

    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);

    // Listen for GPS sync status from SW
    const handler = (event: MessageEvent) => {
      if (event.data?.type === "gps-sync-status") {
        setQueuedCount(event.data.remaining);
      }
    };
    navigator.serviceWorker?.addEventListener("message", handler);

    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
      navigator.serviceWorker?.removeEventListener("message", handler);
    };
  }, []);

  // Auto-redirect when back online
  useEffect(() => {
    if (isOnline) {
      const timer = setTimeout(() => window.location.replace("/"), 1500);
      return () => clearTimeout(timer);
    }
  }, [isOnline]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface p-8">
      <div className="text-center">
        <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-brand-50">
          <WifiOff className="h-10 w-10 text-brand-500" />
        </div>

        <h1 className="mb-2 text-2xl font-semibold text-brand-800">
          {isOnline ? "Back Online" : "You're Offline"}
        </h1>

        <p className="mb-6 text-sm text-gray-500">
          {isOnline
            ? "Reconnected. Redirecting..."
            : "No internet connection detected. Your GPS data and pending actions are safely queued and will sync automatically."}
        </p>

        {queuedCount > 0 && (
          <p className="mb-4 text-xs text-gray-400">
            {queuedCount} GPS reading{queuedCount !== 1 ? "s" : ""} queued for sync
          </p>
        )}

        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-6 py-3
                     text-sm font-medium text-white transition hover:bg-brand-600"
        >
          <RefreshCw className="h-4 w-4" />
          Try Again
        </button>
      </div>
    </div>
  );
}
