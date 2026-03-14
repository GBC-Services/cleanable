"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Users,
  Shield,
  ShieldOff,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  EyeOff,
  Eye,
  MapPin,
  Clock,
  Loader2,
  ChevronDown,
  ChevronUp,
  Bell,
  RefreshCw,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  FleetServicePro,
  GhostModeAlert,
  StrictTrackingRule,
} from "@/types/iot";

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

function formatDateTime(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

// ── Sub-Components ───────────────────────────────────────────────────

function GhostBadge({ active }: { active: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
        active
          ? "bg-amber-100 text-amber-800"
          : "bg-green-100 text-green-800"
      }`}
    >
      {active ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
      {active ? "Ghost" : "Live"}
    </span>
  );
}

function StrictBadge({ enforced }: { enforced: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
        enforced
          ? "bg-red-100 text-red-800"
          : "bg-slate-100 text-slate-600"
      }`}
    >
      {enforced ? (
        <Shield className="h-3 w-3" />
      ) : (
        <ShieldOff className="h-3 w-3" />
      )}
      {enforced ? "Strict" : "Standard"}
    </span>
  );
}

function ResolutionBadge({ resolution }: { resolution: string }) {
  const map: Record<string, string> = {
    pending: "bg-amber-100 text-amber-800",
    checked_in: "bg-green-100 text-green-800",
    dismissed: "bg-slate-100 text-slate-600",
    escalated: "bg-red-100 text-red-800",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        map[resolution] ?? "bg-slate-100 text-slate-600"
      }`}
    >
      {resolution.replace("_", " ")}
    </span>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────

export default function FleetManagementPage() {
  const [pros, setPros] = useState<FleetServicePro[]>([]);
  const [alerts, setAlerts] = useState<GhostModeAlert[]>([]);
  const [loadingPros, setLoadingPros] = useState(true);
  const [loadingAlerts, setLoadingAlerts] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [expandedPro, setExpandedPro] = useState<number | null>(null);
  const [togglingPro, setTogglingPro] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<"fleet" | "alerts">("fleet");

  // Fetch fleet data
  const fetchPros = useCallback(async () => {
    try {
      const res = await api.get<{ count: number; results: FleetServicePro[] }>(
        "/iot/fleet/pros/",
      );
      setPros(res.results);
    } catch {
      setError("Could not load fleet data.");
    } finally {
      setLoadingPros(false);
    }
  }, []);

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await api.get<{ count: number; results: GhostModeAlert[] }>(
        "/iot/fleet/alerts/",
      );
      setAlerts(res.results);
    } catch {
      /* ignore */
    } finally {
      setLoadingAlerts(false);
    }
  }, []);

  useEffect(() => {
    fetchPros();
    fetchAlerts();
  }, [fetchPros, fetchAlerts]);

  // Toggle strict tracking
  const handleToggleStrict = async (pro: FleetServicePro) => {
    setTogglingPro(pro.id);
    setError(null);
    setSuccessMsg(null);

    try {
      await api.post<{ detail: string; rule: StrictTrackingRule }>(
        "/iot/fleet/strict-tracking/",
        {
          service_pro_id: pro.id,
          is_enforced: !pro.strict_tracking_enforced,
          reason: !pro.strict_tracking_enforced
            ? "Enforced by Agency Owner"
            : "Relaxed by Agency Owner",
        },
      );
      setSuccessMsg(
        `Strict Tracking ${!pro.strict_tracking_enforced ? "enforced" : "relaxed"} for ${pro.full_name}.`,
      );
      setTimeout(() => setSuccessMsg(null), 4000);
      fetchPros();
    } catch {
      setError("Failed to update strict tracking.");
    } finally {
      setTogglingPro(null);
    }
  };

  // Resolve an alert
  const handleResolveAlert = async (
    alertUuid: string,
    resolution: string,
  ) => {
    try {
      await api.patch<{ detail: string }>("/iot/fleet/alerts/", {
        alert_uuid: alertUuid,
        resolution,
      });
      fetchAlerts();
    } catch {
      setError("Failed to update alert.");
    }
  };

  const pendingAlertCount = alerts.filter(
    (a) => a.resolution === "pending",
  ).length;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Fleet Management
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Monitor Service Pro GPS tracking, enforce strict tracking, and
            manage Ghost Mode alerts.
          </p>
        </div>
        <button
          data-testid="button-refresh-fleet"
          onClick={() => {
            setLoadingPros(true);
            setLoadingAlerts(true);
            fetchPros();
            fetchAlerts();
          }}
          className="flex items-center gap-1.5 rounded-lg bg-white px-3 py-2 text-xs font-medium text-slate-600 shadow-sm ring-1 ring-slate-200 transition hover:bg-slate-50"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </button>
      </div>

      {/* Tab Bar */}
      <div className="mb-5 flex gap-1 rounded-lg bg-white p-1 shadow-sm ring-1 ring-slate-100">
        <button
          data-testid="tab-fleet"
          onClick={() => setActiveTab("fleet")}
          className={`flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${
            activeTab === "fleet"
              ? "bg-slate-900 text-white"
              : "text-slate-500 hover:text-slate-700"
          }`}
        >
          <Users className="h-4 w-4" />
          Service Pros ({pros.length})
        </button>
        <button
          data-testid="tab-alerts"
          onClick={() => setActiveTab("alerts")}
          className={`relative flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${
            activeTab === "alerts"
              ? "bg-slate-900 text-white"
              : "text-slate-500 hover:text-slate-700"
          }`}
        >
          <Bell className="h-4 w-4" />
          Alerts
          {pendingAlertCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
              {pendingAlertCount}
            </span>
          )}
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div className="mb-4 flex items-start gap-3 rounded-lg bg-red-50 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}
      {successMsg && (
        <div className="mb-4 flex items-start gap-3 rounded-lg bg-green-50 p-4">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
          <p className="text-sm text-green-700">{successMsg}</p>
        </div>
      )}

      {/* Fleet Tab */}
      {activeTab === "fleet" && (
        <div className="rounded-xl bg-white shadow-sm ring-1 ring-slate-100 overflow-hidden">
          {loadingPros ? (
            <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading fleet data...
            </div>
          ) : pros.length === 0 ? (
            <div className="px-6 py-10 text-center text-sm text-slate-400">
              No Service Pros found in your agency.
            </div>
          ) : (
            <ul className="divide-y divide-slate-50">
              {pros.map((pro) => (
                <li key={pro.id}>
                  <div
                    className="flex cursor-pointer items-center gap-4 px-6 py-4 transition hover:bg-slate-50"
                    onClick={() =>
                      setExpandedPro(expandedPro === pro.id ? null : pro.id)
                    }
                    data-testid={`row-fleet-pro-${pro.id}`}
                  >
                    {/* Avatar placeholder */}
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-bold text-slate-600">
                      {pro.full_name
                        .split(" ")
                        .map((n) => n[0])
                        .join("")
                        .slice(0, 2)
                        .toUpperCase()}
                    </div>

                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-slate-800">
                        {pro.full_name}
                      </p>
                      <p className="text-xs text-slate-400">{pro.email}</p>
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      <GhostBadge active={pro.ghost_mode_active} />
                      <StrictBadge enforced={pro.strict_tracking_enforced} />
                      {pro.pending_alerts_count > 0 && (
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                          {pro.pending_alerts_count}
                        </span>
                      )}
                      {expandedPro === pro.id ? (
                        <ChevronUp className="h-4 w-4 text-slate-400" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-slate-400" />
                      )}
                    </div>
                  </div>

                  {/* Expanded Detail */}
                  {expandedPro === pro.id && (
                    <div className="border-t border-slate-100 bg-slate-50 px-6 py-4 space-y-4">
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                        <div className="rounded-lg bg-white p-3 shadow-sm">
                          <p className="text-xs font-medium text-slate-500">
                            Ghost Mode
                          </p>
                          <p className="mt-0.5 text-sm font-semibold text-slate-800">
                            {pro.ghost_mode_active ? "Active" : "Off"}
                          </p>
                          {pro.ghost_mode_since && (
                            <p className="text-xs text-slate-400">
                              Since {timeAgo(pro.ghost_mode_since)}
                            </p>
                          )}
                        </div>
                        <div className="rounded-lg bg-white p-3 shadow-sm">
                          <p className="text-xs font-medium text-slate-500">
                            Last GPS
                          </p>
                          {pro.last_gps_lat && pro.last_gps_lng ? (
                            <>
                              <p className="mt-0.5 text-sm font-semibold text-slate-800">
                                {pro.last_gps_lat.toFixed(4)},{" "}
                                {pro.last_gps_lng.toFixed(4)}
                              </p>
                              <p className="text-xs text-slate-400">
                                {timeAgo(pro.last_gps_time)}
                              </p>
                            </>
                          ) : (
                            <p className="mt-0.5 text-sm text-slate-400">
                              No data
                            </p>
                          )}
                        </div>
                        <div className="rounded-lg bg-white p-3 shadow-sm">
                          <p className="text-xs font-medium text-slate-500">
                            Pending Alerts
                          </p>
                          <p className="mt-0.5 text-sm font-semibold text-slate-800">
                            {pro.pending_alerts_count}
                          </p>
                        </div>
                      </div>

                      {/* Strict Tracking Toggle */}
                      <button
                        data-testid={`button-toggle-strict-${pro.id}`}
                        onClick={() => handleToggleStrict(pro)}
                        disabled={togglingPro === pro.id}
                        className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-xs font-semibold transition ${
                          pro.strict_tracking_enforced
                            ? "bg-slate-200 text-slate-700 hover:bg-slate-300"
                            : "bg-red-600 text-white hover:bg-red-700"
                        } disabled:opacity-50`}
                      >
                        {togglingPro === pro.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : pro.strict_tracking_enforced ? (
                          <ShieldOff className="h-3.5 w-3.5" />
                        ) : (
                          <Shield className="h-3.5 w-3.5" />
                        )}
                        {pro.strict_tracking_enforced
                          ? "Relax Strict Tracking"
                          : "Enforce Strict Tracking"}
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Alerts Tab */}
      {activeTab === "alerts" && (
        <div className="rounded-xl bg-white shadow-sm ring-1 ring-slate-100 overflow-hidden">
          {loadingAlerts ? (
            <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading alerts...
            </div>
          ) : alerts.length === 0 ? (
            <div className="px-6 py-10 text-center text-sm text-slate-400">
              No Ghost Mode alerts.
            </div>
          ) : (
            <ul className="divide-y divide-slate-50">
              {alerts.map((alert) => (
                <li
                  key={alert.uuid}
                  className="px-6 py-4"
                  data-testid={`row-alert-${alert.uuid}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" />
                        <p className="truncate text-sm font-semibold text-slate-800">
                          {alert.service_pro_name}
                        </p>
                        <ResolutionBadge resolution={alert.resolution} />
                      </div>
                      <p className="text-xs text-slate-500 line-clamp-2">
                        {alert.message}
                      </p>
                      <p className="mt-1 text-xs text-slate-400">
                        {formatDateTime(alert.created_at)}
                        {alert.booking
                          ? ` · Booking #${alert.booking}`
                          : ""}
                      </p>
                    </div>

                    {alert.resolution === "pending" && (
                      <div className="flex shrink-0 gap-2">
                        <button
                          data-testid={`button-dismiss-alert-${alert.uuid}`}
                          onClick={() =>
                            handleResolveAlert(alert.uuid, "dismissed")
                          }
                          className="rounded-md bg-slate-100 px-2.5 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-200"
                        >
                          Dismiss
                        </button>
                        <button
                          data-testid={`button-escalate-alert-${alert.uuid}`}
                          onClick={() =>
                            handleResolveAlert(alert.uuid, "escalated")
                          }
                          className="rounded-md bg-red-600 px-2.5 py-1.5 text-xs font-medium text-white transition hover:bg-red-700"
                        >
                          Escalate
                        </button>
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
