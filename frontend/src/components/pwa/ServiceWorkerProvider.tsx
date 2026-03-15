/**
 * ServiceWorkerProvider
 * ======================
 *
 * Client component that registers the Service Worker on mount
 * and provides an update banner when a new version is available.
 */

"use client";

import { useEffect, useState } from "react";
import {
  registerServiceWorker,
  applyServiceWorkerUpdate,
  onSWUpdateAvailable,
} from "@/lib/sw-register";

export function ServiceWorkerProvider() {
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const [registration, setRegistration] = useState<ServiceWorkerRegistration | null>(null);

  useEffect(() => {
    // Only register in production
    if (process.env.NODE_ENV !== "production") return;

    registerServiceWorker();

    const cleanup = onSWUpdateAvailable((reg) => {
      setRegistration(reg);
      setUpdateAvailable(true);
    });

    return cleanup;
  }, []);

  if (!updateAvailable || !registration) return null;

  return (
    <div
      role="alert"
      className="fixed bottom-4 left-4 right-4 z-50 mx-auto max-w-md rounded-lg
                 bg-brand-800 p-4 text-white shadow-lg sm:left-auto sm:right-4"
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium">
          A new version of Cleanable is available.
        </p>
        <button
          onClick={() => applyServiceWorkerUpdate(registration)}
          className="shrink-0 rounded-md bg-white px-3 py-1.5 text-sm
                     font-semibold text-brand-800 transition hover:bg-brand-50"
        >
          Update
        </button>
      </div>
    </div>
  );
}
