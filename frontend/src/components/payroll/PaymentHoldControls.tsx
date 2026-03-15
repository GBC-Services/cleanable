/**
 * PaymentHoldControls — Fiscal Auditor Override Panel
 * ====================================================
 *
 * Allows the Fiscal Auditor to place a hold on a payroll cycle when
 * anomalies are detected, and release holds to resume payout processing.
 */

"use client";

import { useState } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  Loader2,
  AlertTriangle,
  Lock,
  Unlock,
} from "lucide-react";
import { api } from "@/lib/api";
import type { PaymentHold, PayrollCycleStatus } from "@/types/payroll";
import { HOLD_STATUS_INFO } from "@/types/payroll";

interface Props {
  cycleUuid: string;
  cycleStatus: PayrollCycleStatus;
  holds: PaymentHold[];
  onUpdate: () => void;
}

export default function PaymentHoldControls({
  cycleUuid,
  cycleStatus,
  holds,
  onUpdate,
}: Props) {
  const [showPlaceHold, setShowPlaceHold] = useState(false);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [releaseLoading, setReleaseLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [releaseNotes, setReleaseNotes] = useState<Record<string, string>>({});

  const canPlaceHold =
    cycleStatus === "open" || cycleStatus === "processing";

  // ── Place hold ────────────────────────────────────────────────────

  const placeHold = async () => {
    if (reason.length < 10) {
      setError("Reason must be at least 10 characters.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await api.post(`/payroll/cycles/${cycleUuid}/hold/`, { reason });
      setShowPlaceHold(false);
      setReason("");
      onUpdate();
    } catch (err: any) {
      setError(err?.message || "Failed to place hold");
    } finally {
      setLoading(false);
    }
  };

  // ── Release hold ──────────────────────────────────────────────────

  const releaseHold = async (holdUuid: string) => {
    setReleaseLoading(holdUuid);
    setError(null);
    try {
      await api.post(`/payroll/holds/${holdUuid}/release/`, {
        release_notes: releaseNotes[holdUuid] || "",
      });
      onUpdate();
    } catch (err: any) {
      setError(err?.message || "Failed to release hold");
    } finally {
      setReleaseLoading(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
          <ShieldAlert className="h-4 w-4 text-red-500" />
          Payment Holds
        </h4>
        {canPlaceHold && (
          <button
            onClick={() => setShowPlaceHold(!showPlaceHold)}
            className="flex items-center gap-1 rounded-lg border border-red-200
                       bg-white px-3 py-1.5 text-sm font-medium text-red-600
                       hover:bg-red-50"
          >
            <Lock className="h-3.5 w-3.5" />
            Place Hold
          </button>
        )}
      </div>

      {/* ── Place hold form ──────────────────────────────────────── */}
      {showPlaceHold && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 space-y-3">
          <p className="text-sm text-red-700 font-medium">
            Placing a hold will pause all payouts for this cycle.
          </p>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Describe the anomaly or concern (min 10 characters)..."
            rows={3}
            className="w-full rounded-md border border-red-300 px-3 py-2 text-sm
                       focus:border-red-400 focus:outline-none"
          />
          <div className="flex gap-2">
            <button
              onClick={placeHold}
              disabled={loading}
              className="flex items-center gap-1 rounded-lg bg-red-500 px-4 py-1.5
                         text-sm font-medium text-white hover:bg-red-600 disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Lock className="h-3.5 w-3.5" />
              )}
              Confirm Hold
            </button>
            <button
              onClick={() => {
                setShowPlaceHold(false);
                setReason("");
              }}
              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5
                         text-sm text-gray-600 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* ── Error ────────────────────────────────────────────────── */}
      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* ── Holds list ───────────────────────────────────────────── */}
      {holds.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-200 p-4 text-center">
          <ShieldCheck className="mx-auto h-6 w-6 text-green-400" />
          <p className="mt-1 text-xs text-gray-500">No holds on this cycle.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {holds.map((hold) => {
            const info = HOLD_STATUS_INFO[hold.status];
            return (
              <div
                key={hold.uuid}
                className="rounded-lg border border-gray-200 bg-white p-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${info.color} ${info.bgColor}`}
                      >
                        {info.label}
                      </span>
                      <span className="text-xs text-gray-400">
                        by {hold.placed_by_name} on{" "}
                        {new Date(hold.created).toLocaleDateString()}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-gray-700">{hold.reason}</p>
                    {hold.release_notes && (
                      <p className="mt-1 text-xs text-green-600">
                        Released: {hold.release_notes}
                      </p>
                    )}
                  </div>

                  {hold.status === "active" && (
                    <div className="flex flex-col gap-1 items-end">
                      <input
                        type="text"
                        value={releaseNotes[hold.uuid] || ""}
                        onChange={(e) =>
                          setReleaseNotes((prev) => ({
                            ...prev,
                            [hold.uuid]: e.target.value,
                          }))
                        }
                        placeholder="Release notes..."
                        className="rounded-md border border-gray-300 px-2 py-1 text-xs w-48
                                   focus:border-green-400 focus:outline-none"
                      />
                      <button
                        onClick={() => releaseHold(hold.uuid)}
                        disabled={releaseLoading === hold.uuid}
                        className="flex items-center gap-1 rounded bg-green-500 px-2 py-1
                                   text-xs font-medium text-white hover:bg-green-600
                                   disabled:opacity-50"
                      >
                        {releaseLoading === hold.uuid ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Unlock className="h-3 w-3" />
                        )}
                        Release
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
