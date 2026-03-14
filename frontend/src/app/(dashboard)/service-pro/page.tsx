"use client";

import { useCallback, useEffect, useState } from "react";
import {
  EyeOff,
  Eye,
  MapPin,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Clock,
  Info,
} from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import { api } from "@/lib/api";
import type { GhostModeState } from "@/types/iot";

// ── Helpers ──────────────────────────────────────────────────────────

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ── Main Page ─────────────────────────────────────────────────────────

export default function ServiceProDashboard() {
  const { user } = useAuthStore();

  const [ghostState, setGhostState] = useState<GhostModeState | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [checkingIn, setCheckingIn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Fetch current ghost mode state
  const fetchGhostState = useCallback(async () => {
    try {
      const res = await api.get<GhostModeState>("/iot/ghost-mode/");
      setGhostState(res);
      setError(null);
    } catch {
      setError("Could not load Ghost Mode status.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGhostState();
  }, [fetchGhostState]);

  // Toggle ghost mode
  const handleToggle = async () => {
    if (!ghostState) return;
    setToggling(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const res = await api.post<{ detail: string; state: GhostModeState }>(
        "/iot/ghost-mode/",
        { enable: !ghostState.is_active },
      );
      setGhostState(res.state);
      setSuccessMsg(res.detail);
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: unknown) {
      const apiErr = err as { body?: { detail?: string; blocked_by?: string } };
      if (apiErr?.body?.blocked_by === "strict_tracking") {
        setError(apiErr.body.detail ?? "Blocked by Strict Tracking.");
      } else {
        setError(
          apiErr?.body?.detail ?? "Failed to toggle Ghost Mode.",
        );
      }
    } finally {
      setToggling(false);
    }
  };

  // Manual check-in using browser geolocation
  const handleCheckin = async () => {
    setCheckingIn(true);
    setError(null);
    setSuccessMsg(null);

    if (!navigator.geolocation) {
      setError("Geolocation is not supported by your browser.");
      setCheckingIn(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const res = await api.post<{
            detail: string;
            latitude: number;
            longitude: number;
            resolved_alerts: number;
          }>("/iot/ghost-mode/checkin/", {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          });
          setSuccessMsg(
            `Check-in recorded at (${res.latitude.toFixed(4)}, ${res.longitude.toFixed(4)}). ` +
            `${res.resolved_alerts} alert(s) resolved.`,
          );
          setTimeout(() => setSuccessMsg(null), 5000);
          fetchGhostState();
        } catch {
          setError("Failed to submit check-in.");
        } finally {
          setCheckingIn(false);
        }
      },
      (geoErr) => {
        setError(`Geolocation error: ${geoErr.message}`);
        setCheckingIn(false);
      },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };

  const isActive = ghostState?.is_active ?? false;
  const isStrictEnforced = ghostState?.is_strict_tracking_enforced ?? false;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">
          Service Pro Dashboard
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          {user?.first_name
            ? `Welcome, ${user.first_name}. `
            : ""}
          Manage your GPS privacy and shifts.
        </p>
      </div>

      {/* Ghost Mode Card */}
      <div className="mb-6 rounded-xl bg-white shadow-sm ring-1 ring-slate-100 overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div className="flex items-center gap-3">
            {isActive ? (
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-50">
                <EyeOff className="h-5 w-5 text-amber-600" />
              </span>
            ) : (
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-green-50">
                <Eye className="h-5 w-5 text-green-600" />
              </span>
            )}
            <div>
              <h2 className="text-sm font-semibold text-slate-800">
                Ghost Mode
              </h2>
              <p className="text-xs text-slate-500">
                Pause live GPS broadcasting during breaks
              </p>
            </div>
          </div>
          <span
            className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${
              isActive
                ? "bg-amber-100 text-amber-800"
                : "bg-green-100 text-green-800"
            }`}
          >
            {isActive ? "Active" : "Off"}
          </span>
        </div>

        <div className="px-6 py-5 space-y-4">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-6 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading...
            </div>
          ) : (
            <>
              {/* Strict Tracking Warning */}
              {isStrictEnforced && (
                <div className="flex items-start gap-3 rounded-lg bg-red-50 p-4">
                  <Shield className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
                  <div>
                    <p className="text-sm font-medium text-red-800">
                      Strict Tracking Enforced
                    </p>
                    <p className="mt-0.5 text-xs text-red-600">
                      Your Agency Owner has enforced Strict Tracking. Ghost Mode
                      cannot be activated during active shifts.
                    </p>
                  </div>
                </div>
              )}

              {/* Error / Success */}
              {error && (
                <div className="flex items-start gap-3 rounded-lg bg-red-50 p-4">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}

              {successMsg && (
                <div className="flex items-start gap-3 rounded-lg bg-green-50 p-4">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
                  <p className="text-sm text-green-700">{successMsg}</p>
                </div>
              )}

              {/* Status Details */}
              {ghostState && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <div className="rounded-lg bg-slate-50 p-3">
                    <p className="text-xs font-medium text-slate-500">
                      Last Activated
                    </p>
                    <p className="mt-0.5 text-sm font-semibold text-slate-800">
                      {timeAgo(ghostState.activated_at)}
                    </p>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <p className="text-xs font-medium text-slate-500">
                      Last Deactivated
                    </p>
                    <p className="mt-0.5 text-sm font-semibold text-slate-800">
                      {timeAgo(ghostState.deactivated_at)}
                    </p>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <p className="text-xs font-medium text-slate-500">
                      Last Check-In
                    </p>
                    <p className="mt-0.5 text-sm font-semibold text-slate-800">
                      {timeAgo(ghostState.last_manual_checkin_at)}
                    </p>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex flex-col gap-3 sm:flex-row">
                <button
                  data-testid="button-toggle-ghost-mode"
                  onClick={handleToggle}
                  disabled={toggling || loading}
                  className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold transition ${
                    isActive
                      ? "bg-green-600 text-white hover:bg-green-700"
                      : "bg-amber-500 text-white hover:bg-amber-600"
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {toggling ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : isActive ? (
                    <Eye className="h-4 w-4" />
                  ) : (
                    <EyeOff className="h-4 w-4" />
                  )}
                  {isActive ? "Resume Broadcasting" : "Activate Ghost Mode"}
                </button>

                {isActive && (
                  <button
                    data-testid="button-manual-checkin"
                    onClick={handleCheckin}
                    disabled={checkingIn}
                    className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {checkingIn ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <MapPin className="h-4 w-4" />
                    )}
                    Manual Check-In
                  </button>
                )}
              </div>

              {/* Info */}
              <div className="flex items-start gap-2.5 text-xs text-slate-400">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <p>
                  When Ghost Mode is active during a scheduled job, your Agency
                  Owner is automatically notified and a manual check-in is
                  required. GPS data is always logged for dispute resolution
                  even while broadcasting is paused.
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Quick Info Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100">
          <div className="flex items-center gap-3 mb-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50">
              <MapPin className="h-4 w-4 text-blue-600" />
            </span>
            <h3 className="text-sm font-semibold text-slate-800">
              GPS Tracking
            </h3>
          </div>
          <p className="text-xs text-slate-500">
            Your location is shared in real-time with Residents during active
            bookings. Ghost Mode pauses this broadcasting while still logging
            coordinates internally.
          </p>
        </div>

        <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100">
          <div className="flex items-center gap-3 mb-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-50">
              <Clock className="h-4 w-4 text-purple-600" />
            </span>
            <h3 className="text-sm font-semibold text-slate-800">
              Data Retention
            </h3>
          </div>
          <p className="text-xs text-slate-500">
            GPS history older than 30 days is automatically deleted.
            Platform Admins can access logs for dispute resolution within
            the retention window.
          </p>
        </div>
      </div>
    </div>
  );
}
