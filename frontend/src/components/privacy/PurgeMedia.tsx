"use client";

import { useState } from "react";
import {
  Trash2,
  ShieldAlert,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Search,
} from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import type { PurgeMediaResponse } from "@/types/support";

// ── Component ──────────────────────────────────────────────────────────

/**
 * GDPR Purge Media — Superuser Function
 *
 * Platform Admins and Support Architects can instantly delete all
 * spatial verification media tied to a specific Resident account.
 *
 * Implements GDPR Article 17 — Right to Erasure.
 */
export default function PurgeMedia() {
  const { tokens } = useAuthStore();

  const [residentId, setResidentId] = useState("");
  const [reason, setReason] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [result, setResult] = useState<PurgeMediaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

  const handleSubmit = async () => {
    if (!tokens?.access || !residentId.trim()) return;

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/support/purge-media/`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${tokens.access}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          resident_id: parseInt(residentId, 10),
          reason: reason.trim() || "GDPR Right to be Forgotten",
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Purge failed.");
      }

      setResult(data as PurgeMediaResponse);
      setShowConfirm(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Purge failed.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setResidentId("");
    setReason("");
    setResult(null);
    setError(null);
    setShowConfirm(false);
  };

  return (
    <div className="rounded-xl bg-white shadow-sm ring-1 ring-slate-100 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-slate-100 px-6 py-4">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-red-50">
          <Trash2 className="h-5 w-5 text-red-600" />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-slate-800">
            Purge Verification Media
          </h2>
          <p className="text-xs text-slate-500">
            GDPR Right to be Forgotten — delete all media for a Resident
          </p>
        </div>
      </div>

      <div className="px-6 py-5 space-y-4">
        {/* Warning banner */}
        <div className="flex items-start gap-3 rounded-lg bg-amber-50 p-4 ring-1 ring-amber-100">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          <div className="text-xs text-amber-700">
            <p className="font-semibold mb-1">Irreversible Action</p>
            <p>
              This will permanently delete all spatial verification photos,
              videos, and AI analysis data associated with the Resident.
              This action is logged to the governance audit trail.
            </p>
          </div>
        </div>

        {/* Result */}
        {result && (
          <div className="rounded-lg bg-green-50 p-4 ring-1 ring-green-100">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <span className="text-sm font-semibold text-green-800">
                Purge Complete
              </span>
            </div>
            <div className="text-xs text-green-700 space-y-1">
              <p>{result.detail}</p>
              <p>
                Resident: {result.resident_email} (ID: {result.resident_id})
              </p>
              <p>
                Records purged: {result.purged_count}
              </p>
              {result.purged_verification_ids.length > 0 && (
                <p className="font-mono text-[11px]">
                  IDs: {result.purged_verification_ids.join(", ")}
                </p>
              )}
            </div>
            <button
              data-testid="button-purge-reset"
              onClick={handleReset}
              className="mt-3 text-xs font-medium text-green-700 underline hover:text-green-900"
            >
              Process another request
            </button>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-start gap-2 rounded-lg bg-red-50 p-3 ring-1 ring-red-100">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
            <span className="text-xs text-red-700">{error}</span>
          </div>
        )}

        {/* Form */}
        {!result && (
          <>
            <div className="space-y-3">
              <div>
                <label
                  htmlFor="resident-id"
                  className="block text-xs font-medium text-slate-700 mb-1"
                >
                  Resident User ID
                </label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input
                    id="resident-id"
                    data-testid="input-resident-id"
                    type="number"
                    value={residentId}
                    onChange={(e) => setResidentId(e.target.value)}
                    placeholder="Enter the Resident's user ID"
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-4 text-sm text-slate-800 placeholder:text-slate-400 focus:border-red-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-red-100 transition"
                  />
                </div>
              </div>

              <div>
                <label
                  htmlFor="purge-reason"
                  className="block text-xs font-medium text-slate-700 mb-1"
                >
                  Reason for Purge
                </label>
                <textarea
                  id="purge-reason"
                  data-testid="input-purge-reason"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="GDPR erasure request, reference number..."
                  rows={2}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-800 placeholder:text-slate-400 focus:border-red-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-red-100 transition resize-none"
                />
              </div>
            </div>

            {/* Confirmation step */}
            {!showConfirm ? (
              <button
                data-testid="button-purge-initiate"
                onClick={() => setShowConfirm(true)}
                disabled={!residentId.trim()}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Trash2 className="h-4 w-4" />
                Purge All Media
              </button>
            ) : (
              <div className="space-y-3">
                <p className="text-xs font-medium text-red-700 text-center">
                  Are you sure? This action cannot be undone.
                </p>
                <div className="flex gap-3">
                  <button
                    data-testid="button-purge-confirm"
                    onClick={handleSubmit}
                    disabled={isLoading}
                    className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-60"
                  >
                    {isLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                    {isLoading ? "Purging..." : "Confirm Purge"}
                  </button>
                  <button
                    data-testid="button-purge-cancel"
                    onClick={() => setShowConfirm(false)}
                    disabled={isLoading}
                    className="rounded-lg bg-slate-100 px-4 py-3 text-sm font-medium text-slate-600 transition hover:bg-slate-200 disabled:opacity-60"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
