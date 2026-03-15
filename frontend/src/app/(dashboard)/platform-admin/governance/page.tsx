"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type {
  SystemFeatureToggle,
  FeatureCategory,
  GovernanceAuditLog,
  BreakGlassSession,
} from "@/types/governance";
import { CATEGORY_META, SEVERITY_META } from "@/types/governance";
import PurgeMedia from "@/components/privacy/PurgeMedia";

// ── Helpers ──────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return "Never";
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function classNames(...classes: (string | false | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

// ── Feature Toggle Card ──────────────────────────────────────────────

function ToggleCard({
  toggle,
  onToggle,
  isLoading,
}: {
  toggle: SystemFeatureToggle;
  onToggle: (slug: string) => void;
  isLoading: boolean;
}) {
  const severity = SEVERITY_META[toggle.severity];

  return (
    <div
      className={classNames(
        "rounded-lg border p-5 transition-all duration-200",
        toggle.is_enabled
          ? "border-brand-500/30 bg-brand-500/5"
          : "border-[hsl(var(--border))] bg-[hsl(var(--card))]",
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-[hsl(var(--foreground))]">
              {toggle.name}
            </h3>
            <span
              className={classNames(
                "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
                severity.bgColor,
              )}
            >
              <span className={classNames("inline-block h-1.5 w-1.5 rounded-full", severity.dotColor)} />
              {severity.label}
            </span>
          </div>
          <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
            {toggle.description}
          </p>
          <p className="mt-2 text-[10px] text-[hsl(var(--muted-foreground))]">
            {toggle.toggled_at
              ? `Last toggled ${formatDate(toggle.toggled_at)}${toggle.toggled_by_email ? ` by ${toggle.toggled_by_email}` : ""}`
              : "Never toggled"}
          </p>
        </div>

        {/* Toggle Switch */}
        <button
          onClick={() => onToggle(toggle.slug)}
          disabled={isLoading}
          className={classNames(
            "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
            toggle.is_enabled ? "bg-brand-500" : "bg-[hsl(var(--muted))]",
          )}
          role="switch"
          aria-checked={toggle.is_enabled}
          aria-label={`Toggle ${toggle.name}`}
        >
          <span
            className={classNames(
              "pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform duration-200",
              toggle.is_enabled ? "translate-x-5" : "translate-x-0",
            )}
          />
        </button>
      </div>
    </div>
  );
}

// ── Audit Log Row ────────────────────────────────────────────────────

function AuditRow({ log }: { log: GovernanceAuditLog }) {
  const severityColor =
    log.severity === "critical"
      ? "text-red-600 dark:text-red-400"
      : log.severity === "warning"
        ? "text-amber-600 dark:text-amber-400"
        : "text-[hsl(var(--muted-foreground))]";

  return (
    <tr className="border-b border-[hsl(var(--border))] last:border-0">
      <td className="px-3 py-3 text-xs">
        <span className={classNames("font-medium", severityColor)}>
          {log.severity.toUpperCase()}
        </span>
      </td>
      <td className="px-3 py-3 text-xs text-[hsl(var(--foreground))]">
        {log.action.replace(/_/g, " ")}
      </td>
      <td className="px-3 py-3 text-xs text-[hsl(var(--muted-foreground))]">
        {log.actor_email || "System"}
      </td>
      <td className="hidden px-3 py-3 text-xs text-[hsl(var(--muted-foreground))] md:table-cell">
        {log.description.length > 80
          ? log.description.slice(0, 80) + "..."
          : log.description}
      </td>
      <td className="px-3 py-3 text-xs text-[hsl(var(--muted-foreground))]">
        {formatDate(log.timestamp)}
      </td>
    </tr>
  );
}

// ── Break-Glass Row ──────────────────────────────────────────────────

function BreakGlassRow({ session }: { session: BreakGlassSession }) {
  const statusColors: Record<string, string> = {
    pending: "bg-yellow-50 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400",
    active: "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400",
    expired: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
    revoked: "bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400",
  };

  return (
    <tr className="border-b border-[hsl(var(--border))] last:border-0">
      <td className="px-3 py-3 text-xs">
        <span
          className={classNames(
            "inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium",
            statusColors[session.status] || "",
          )}
        >
          {session.status.toUpperCase()}
        </span>
      </td>
      <td className="px-3 py-3 text-xs text-[hsl(var(--foreground))]">
        {session.initiated_by_email}
      </td>
      <td className="px-3 py-3 text-xs text-[hsl(var(--muted-foreground))]">
        {session.target_user_email}
      </td>
      <td className="hidden px-3 py-3 text-xs text-[hsl(var(--muted-foreground))] md:table-cell">
        {session.reason.length > 60
          ? session.reason.slice(0, 60) + "..."
          : session.reason}
      </td>
      <td className="px-3 py-3 text-xs text-[hsl(var(--muted-foreground))]">
        {formatDate(session.created_at)}
      </td>
    </tr>
  );
}

// ── Main Dashboard ───────────────────────────────────────────────────

type Tab = "toggles" | "audit" | "break-glass" | "gdpr";

export default function GovernanceDashboard() {
  const [activeTab, setActiveTab] = useState<Tab>("toggles");
  const [toggles, setToggles] = useState<SystemFeatureToggle[]>([]);
  const [auditLogs, setAuditLogs] = useState<GovernanceAuditLog[]>([]);
  const [bgSessions, setBgSessions] = useState<BreakGlassSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [togglingSlug, setTogglingSlug] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<FeatureCategory | "all">("all");
  const [error, setError] = useState<string | null>(null);

  // ── Data fetching ────────────────────────────────────────────────

  const fetchToggles = useCallback(async () => {
    try {
      const data = await api.get<{ results?: SystemFeatureToggle[]; } | SystemFeatureToggle[]>(
        "/governance/features/",
      );
      const items = Array.isArray(data) ? data : data.results || [];
      setToggles(items);
    } catch {
      setError("Failed to load feature toggles.");
    }
  }, []);

  const fetchAuditLogs = useCallback(async () => {
    try {
      const data = await api.get<{ results?: GovernanceAuditLog[] } | GovernanceAuditLog[]>(
        "/governance/audit-logs/",
      );
      const items = Array.isArray(data) ? data : data.results || [];
      setAuditLogs(items);
    } catch {
      setError("Failed to load audit logs.");
    }
  }, []);

  const fetchBreakGlass = useCallback(async () => {
    try {
      const data = await api.get<{ results?: BreakGlassSession[] } | BreakGlassSession[]>(
        "/governance/break-glass/",
      );
      const items = Array.isArray(data) ? data : data.results || [];
      setBgSessions(items);
    } catch {
      setError("Failed to load break-glass sessions.");
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchToggles(), fetchAuditLogs(), fetchBreakGlass()]).finally(
      () => setLoading(false),
    );
  }, [fetchToggles, fetchAuditLogs, fetchBreakGlass]);

  // ── Toggle handler ───────────────────────────────────────────────

  const handleToggle = async (slug: string) => {
    setTogglingSlug(slug);
    try {
      const updated = await api.post<SystemFeatureToggle>(
        `/governance/features/${slug}/toggle/`,
      );
      setToggles((prev) =>
        prev.map((t) => (t.slug === slug ? { ...t, ...updated } : t)),
      );
      // Refresh audit logs to show the new entry
      fetchAuditLogs();
    } catch {
      setError("Failed to toggle feature.");
    } finally {
      setTogglingSlug(null);
    }
  };

  // ── Derived data ─────────────────────────────────────────────────

  const filteredToggles =
    categoryFilter === "all"
      ? toggles
      : toggles.filter((t) => t.category === categoryFilter);

  const categories = Array.from(new Set(toggles.map((t) => t.category)));
  const enabledCount = toggles.filter((t) => t.is_enabled).length;
  const criticalEnabled = toggles.filter(
    (t) => t.is_enabled && (t.severity === "high" || t.severity === "critical"),
  ).length;
  const activeBGCount = bgSessions.filter((s) => s.status === "active").length;

  // ── Tabs ─────────────────────────────────────────────────────────

  const tabs: { key: Tab; label: string; badge?: number }[] = [
    { key: "toggles", label: "Kill Switches" },
    { key: "audit", label: "Audit Log", badge: auditLogs.length },
    { key: "break-glass", label: "Break-Glass", badge: activeBGCount || undefined },
    { key: "gdpr", label: "GDPR Purge" },
  ];

  // ── Render ───────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-[hsl(var(--foreground))]">
          Platform Governance
        </h1>
        <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
          Global feature controls, privacy audit trail, and escalation management.
        </p>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          <p className="text-[10px] font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Total Features
          </p>
          <p className="mt-1 text-2xl font-bold text-[hsl(var(--foreground))]">
            {toggles.length}
          </p>
        </div>
        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          <p className="text-[10px] font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Enabled
          </p>
          <p className="mt-1 text-2xl font-bold text-brand-500">
            {enabledCount}
          </p>
        </div>
        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          <p className="text-[10px] font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            High-Risk Active
          </p>
          <p className={classNames(
            "mt-1 text-2xl font-bold",
            criticalEnabled > 0 ? "text-red-600 dark:text-red-400" : "text-[hsl(var(--foreground))]",
          )}>
            {criticalEnabled}
          </p>
        </div>
        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          <p className="text-[10px] font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Active Break-Glass
          </p>
          <p className={classNames(
            "mt-1 text-2xl font-bold",
            activeBGCount > 0 ? "text-red-600 dark:text-red-400" : "text-[hsl(var(--foreground))]",
          )}>
            {activeBGCount}
          </p>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-[hsl(var(--border))]">
        <nav className="-mb-px flex gap-6" aria-label="Tabs">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={classNames(
                "inline-flex items-center gap-1.5 border-b-2 pb-3 text-sm font-medium transition-colors",
                activeTab === tab.key
                  ? "border-brand-500 text-brand-500"
                  : "border-transparent text-[hsl(var(--muted-foreground))] hover:border-[hsl(var(--border))] hover:text-[hsl(var(--foreground))]",
              )}
            >
              {tab.label}
              {tab.badge !== undefined && tab.badge > 0 && (
                <span className="inline-flex min-w-[18px] items-center justify-center rounded-full bg-brand-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-brand-500">
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === "toggles" && (
        <div className="space-y-4">
          {/* Category Filter */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setCategoryFilter("all")}
              className={classNames(
                "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                categoryFilter === "all"
                  ? "bg-brand-500 text-white"
                  : "bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))]",
              )}
            >
              All
            </button>
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat)}
                className={classNames(
                  "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                  categoryFilter === cat
                    ? "bg-brand-500 text-white"
                    : "bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))]",
                )}
              >
                {CATEGORY_META[cat]?.label || cat}
              </button>
            ))}
          </div>

          {/* Toggle Grid */}
          <div className="grid gap-3 sm:grid-cols-2">
            {filteredToggles.map((toggle) => (
              <ToggleCard
                key={toggle.slug}
                toggle={toggle}
                onToggle={handleToggle}
                isLoading={togglingSlug === toggle.slug}
              />
            ))}
          </div>

          {filteredToggles.length === 0 && (
            <p className="py-8 text-center text-sm text-[hsl(var(--muted-foreground))]">
              No feature toggles found{categoryFilter !== "all" ? ` in "${CATEGORY_META[categoryFilter]?.label}"` : ""}.
            </p>
          )}
        </div>
      )}

      {activeTab === "audit" && (
        <div className="overflow-hidden rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))]">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                  <th className="px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                    Severity
                  </th>
                  <th className="px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                    Action
                  </th>
                  <th className="px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                    Actor
                  </th>
                  <th className="hidden px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))] md:table-cell">
                    Description
                  </th>
                  <th className="px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                    Timestamp
                  </th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((log) => (
                  <AuditRow key={log.id} log={log} />
                ))}
              </tbody>
            </table>
          </div>
          {auditLogs.length === 0 && (
            <p className="py-8 text-center text-sm text-[hsl(var(--muted-foreground))]">
              No audit log entries yet.
            </p>
          )}
        </div>
      )}

      {activeTab === "break-glass" && (
        <div className="overflow-hidden rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))]">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                  <th className="px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                    Status
                  </th>
                  <th className="px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                    Initiated By
                  </th>
                  <th className="px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                    Target User
                  </th>
                  <th className="hidden px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))] md:table-cell">
                    Reason
                  </th>
                  <th className="px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                    Requested
                  </th>
                </tr>
              </thead>
              <tbody>
                {bgSessions.map((session) => (
                  <BreakGlassRow key={session.id} session={session} />
                ))}
              </tbody>
            </table>
          </div>
          {bgSessions.length === 0 && (
            <p className="py-8 text-center text-sm text-[hsl(var(--muted-foreground))]">
              No break-glass sessions recorded.
            </p>
          )}
        </div>
      )}

      {activeTab === "gdpr" && (
        <div className="mx-auto max-w-xl">
          <PurgeMedia />
        </div>
      )}
    </div>
  );
}
