"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { api } from "@/lib/api";
import type {
  PlatformIntegration,
  NotificationPreference,
  IntegrationCategory,
  BulkUpdateResponse,
} from "@/types/command-center";
import {
  INTEGRATION_CATEGORY_META,
  EVENT_CATEGORY_META,
} from "@/types/command-center";

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

function cn(...classes: (string | false | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

// ── Integration Card ─────────────────────────────────────────────────

function IntegrationCard({
  integration,
  onToggle,
  onExpand,
  isLoading,
  isExpanded,
}: {
  integration: PlatformIntegration;
  onToggle: (slug: string) => void;
  onExpand: (slug: string) => void;
  isLoading: boolean;
  isExpanded: boolean;
}) {
  const catMeta = INTEGRATION_CATEGORY_META[integration.category];

  return (
    <div
      className={cn(
        "rounded-lg border transition-all duration-200",
        integration.is_enabled
          ? "border-brand-500/30 bg-brand-500/5"
          : "border-[hsl(var(--border))] bg-[hsl(var(--card))]",
      )}
    >
      <div className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-lg">
                {integration.icon === "brain" && "🧠"}
                {integration.icon === "mic" && "🎤"}
                {integration.icon === "speaker" && "🔊"}
                {integration.icon === "lock" && "🔐"}
              </span>
              <h3 className="text-sm font-semibold text-[hsl(var(--foreground))]">
                {integration.name}
              </h3>
              <span className="inline-flex items-center rounded-full bg-[hsl(var(--muted))] px-2 py-0.5 text-[10px] font-medium text-[hsl(var(--muted-foreground))]">
                {catMeta?.label || integration.category}
              </span>
            </div>
            <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
              {integration.description}
            </p>
            {integration.toggled_at && (
              <p className="mt-2 text-[10px] text-[hsl(var(--muted-foreground))]">
                Last toggled {formatDate(integration.toggled_at)}
                {integration.toggled_by_email
                  ? ` by ${integration.toggled_by_email}`
                  : ""}
              </p>
            )}
          </div>

          {/* Toggle Switch */}
          <button
            onClick={() => onToggle(integration.slug)}
            disabled={isLoading}
            className={cn(
              "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
              integration.is_enabled
                ? "bg-brand-500"
                : "bg-[hsl(var(--muted))]",
            )}
            role="switch"
            aria-checked={integration.is_enabled}
            aria-label={`Toggle ${integration.name}`}
          >
            <span
              className={cn(
                "pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform duration-200",
                integration.is_enabled ? "translate-x-5" : "translate-x-0",
              )}
            />
          </button>
        </div>
      </div>

      {/* Config Section (expandable) */}
      {integration.is_enabled && (
        <div className="border-t border-[hsl(var(--border))]">
          <button
            onClick={() => onExpand(integration.slug)}
            className="flex w-full items-center justify-between px-5 py-2.5 text-[10px] font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))] transition-colors hover:text-[hsl(var(--foreground))]"
          >
            <span>Configuration</span>
            <span className="text-xs">
              {isExpanded ? "▲" : "▼"}
            </span>
          </button>
          {isExpanded && (
            <div className="px-5 pb-4">
              <div className="rounded-md bg-[hsl(var(--muted))] p-3">
                <pre className="overflow-x-auto text-[11px] text-[hsl(var(--foreground))]">
                  {JSON.stringify(integration.config, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Notification Matrix Checkbox ─────────────────────────────────────

function MatrixCheckbox({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: () => void;
  disabled: boolean;
  label: string;
}) {
  return (
    <button
      onClick={onChange}
      disabled={disabled}
      className="flex items-center justify-center"
      aria-label={label}
    >
      <div
        className={cn(
          "flex h-5 w-5 items-center justify-center rounded border transition-all duration-150",
          checked
            ? "border-brand-500 bg-brand-500"
            : "border-[hsl(var(--border))] bg-[hsl(var(--card))]",
          disabled && "cursor-not-allowed opacity-50",
          !disabled && "cursor-pointer hover:border-brand-500/60",
        )}
      >
        {checked && (
          <svg
            className="h-3 w-3 text-white"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={3}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M5 13l4 4L19 7"
            />
          </svg>
        )}
      </div>
    </button>
  );
}

// ── Main Command Center ──────────────────────────────────────────────

type Tab = "integrations" | "notifications";

export default function CyberneticCommandCenter() {
  const [activeTab, setActiveTab] = useState<Tab>("integrations");

  // Integration state
  const [integrations, setIntegrations] = useState<PlatformIntegration[]>([]);
  const [togglingSlug, setTogglingSlug] = useState<string | null>(null);
  const [expandedSlugs, setExpandedSlugs] = useState<Set<string>>(new Set());

  // Notification state
  const [preferences, setPreferences] = useState<NotificationPreference[]>([]);
  const [savingMatrix, setSavingMatrix] = useState(false);
  const [pendingChanges, setPendingChanges] = useState<
    Map<string, Partial<Pick<NotificationPreference, "in_app" | "sms" | "email">>>
  >(new Map());

  // Shared
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // ── Data fetching ──────────────────────────────────────────────────

  const fetchIntegrations = useCallback(async () => {
    try {
      const data = await api.get<
        { results?: PlatformIntegration[] } | PlatformIntegration[]
      >("/governance/integrations/");
      const items = Array.isArray(data) ? data : data.results || [];
      setIntegrations(items);
    } catch {
      setError("Failed to load integrations.");
    }
  }, []);

  const fetchPreferences = useCallback(async () => {
    try {
      const data = await api.get<NotificationPreference[]>(
        "/governance/notifications/me/",
      );
      const items = Array.isArray(data) ? data : [];
      setPreferences(items);
    } catch {
      setError("Failed to load notification preferences.");
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchIntegrations(), fetchPreferences()]).finally(() =>
      setLoading(false),
    );
  }, [fetchIntegrations, fetchPreferences]);

  // ── Integration toggle handler ─────────────────────────────────────

  const handleToggleIntegration = async (slug: string) => {
    setTogglingSlug(slug);
    try {
      const updated = await api.post<PlatformIntegration>(
        `/governance/integrations/${slug}/toggle/`,
      );
      setIntegrations((prev) =>
        prev.map((i) => (i.slug === slug ? { ...i, ...updated } : i)),
      );
    } catch {
      setError("Failed to toggle integration.");
    } finally {
      setTogglingSlug(null);
    }
  };

  const handleExpandToggle = (slug: string) => {
    setExpandedSlugs((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) {
        next.delete(slug);
      } else {
        next.add(slug);
      }
      return next;
    });
  };

  // ── Notification matrix handlers ───────────────────────────────────

  const handleMatrixToggle = (
    eventSlug: string,
    channel: "in_app" | "sms" | "email",
  ) => {
    const current = preferences.find((p) => p.event_slug === eventSlug);
    if (!current) return;

    const pending = pendingChanges.get(eventSlug) || {};
    const currentValue =
      pending[channel] !== undefined ? pending[channel] : current[channel];

    setPendingChanges((prev) => {
      const next = new Map(prev);
      next.set(eventSlug, { ...pending, [channel]: !currentValue });
      return next;
    });
  };

  const getEffectiveValue = (
    pref: NotificationPreference,
    channel: "in_app" | "sms" | "email",
  ): boolean => {
    const pending = pendingChanges.get(pref.event_slug);
    if (pending && pending[channel] !== undefined) {
      return pending[channel]!;
    }
    return pref[channel];
  };

  const hasPendingChanges = pendingChanges.size > 0;

  const handleSaveMatrix = async () => {
    if (!hasPendingChanges) return;

    setSavingMatrix(true);
    setError(null);

    const updates = Array.from(pendingChanges.entries()).map(
      ([event_slug, channels]) => ({
        event_slug,
        ...channels,
      }),
    );

    try {
      const result = await api.put<BulkUpdateResponse>(
        "/governance/notifications/me/",
        { preferences: updates },
      );
      setPreferences(result.preferences);
      setPendingChanges(new Map());
      setSuccessMsg(
        `Updated ${result.updated_count} notification preference${result.updated_count !== 1 ? "s" : ""}.`,
      );
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch {
      setError("Failed to save notification preferences.");
    } finally {
      setSavingMatrix(false);
    }
  };

  const handleDiscardChanges = () => {
    setPendingChanges(new Map());
  };

  // ── Group integrations by category ─────────────────────────────────

  const groupedIntegrations = useMemo(() => {
    const groups: Record<IntegrationCategory, PlatformIntegration[]> = {
      proactive: [],
      voice: [],
      device: [],
    };
    integrations.forEach((i) => {
      if (groups[i.category]) {
        groups[i.category].push(i);
      }
    });
    return groups;
  }, [integrations]);

  // ── Group notifications by event category ──────────────────────────

  const groupedPreferences = useMemo(() => {
    const groups: Record<string, NotificationPreference[]> = {};
    preferences.forEach((p) => {
      const cat = p.event_category || "Other";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(p);
    });
    return groups;
  }, [preferences]);

  // ── Stats ──────────────────────────────────────────────────────────

  const enabledIntegrations = integrations.filter((i) => i.is_enabled).length;
  const totalChannelsActive = preferences.reduce(
    (sum, p) => sum + (p.in_app ? 1 : 0) + (p.sms ? 1 : 0) + (p.email ? 1 : 0),
    0,
  );

  // ── Tabs ───────────────────────────────────────────────────────────

  const tabs: { key: Tab; label: string; badge?: number }[] = [
    {
      key: "integrations",
      label: "Integration Toggles",
      badge: enabledIntegrations || undefined,
    },
    {
      key: "notifications",
      label: "Notification Matrix",
    },
  ];

  // ── Render ─────────────────────────────────────────────────────────

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
          Cybernetic Command Center
        </h1>
        <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
          Platform integrations, proactive intelligence, and notification
          routing for all lifecycle events.
        </p>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          <p className="text-[10px] font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Total Integrations
          </p>
          <p className="mt-1 text-2xl font-bold text-[hsl(var(--foreground))]">
            {integrations.length}
          </p>
        </div>
        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          <p className="text-[10px] font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Active Integrations
          </p>
          <p className="mt-1 text-2xl font-bold text-brand-500">
            {enabledIntegrations}
          </p>
        </div>
        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          <p className="text-[10px] font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Lifecycle Events
          </p>
          <p className="mt-1 text-2xl font-bold text-[hsl(var(--foreground))]">
            {preferences.length}
          </p>
        </div>
        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          <p className="text-[10px] font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Active Channels
          </p>
          <p className="mt-1 text-2xl font-bold text-brand-500">
            {totalChannelsActive}
          </p>
        </div>
      </div>

      {/* Error / Success Banner */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">
            Dismiss
          </button>
        </div>
      )}
      {successMsg && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700 dark:border-green-800 dark:bg-green-900/20 dark:text-green-400">
          {successMsg}
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-[hsl(var(--border))]">
        <nav className="-mb-px flex gap-6" aria-label="Tabs">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
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

      {/* ── Integration Toggles Tab ─────────────────────────────────── */}
      {activeTab === "integrations" && (
        <div className="space-y-8">
          {(
            Object.entries(groupedIntegrations) as [
              IntegrationCategory,
              PlatformIntegration[],
            ][]
          ).map(([category, items]) => {
            if (items.length === 0) return null;
            const catMeta = INTEGRATION_CATEGORY_META[category];
            return (
              <div key={category} className="space-y-3">
                <div>
                  <h2 className="text-sm font-semibold text-[hsl(var(--foreground))]">
                    {catMeta?.label || category}
                  </h2>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">
                    {catMeta?.description || ""}
                  </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {items.map((integration) => (
                    <IntegrationCard
                      key={integration.slug}
                      integration={integration}
                      onToggle={handleToggleIntegration}
                      onExpand={handleExpandToggle}
                      isLoading={togglingSlug === integration.slug}
                      isExpanded={expandedSlugs.has(integration.slug)}
                    />
                  ))}
                </div>
              </div>
            );
          })}

          {integrations.length === 0 && (
            <p className="py-8 text-center text-sm text-[hsl(var(--muted-foreground))]">
              No platform integrations configured.
            </p>
          )}
        </div>
      )}

      {/* ── Notification Matrix Tab ─────────────────────────────────── */}
      {activeTab === "notifications" && (
        <div className="space-y-4">
          {/* Save/Discard bar */}
          {hasPendingChanges && (
            <div className="flex items-center justify-between rounded-lg border border-brand-500/30 bg-brand-500/5 p-3">
              <p className="text-xs font-medium text-brand-500">
                {pendingChanges.size} unsaved change
                {pendingChanges.size !== 1 ? "s" : ""}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={handleDiscardChanges}
                  className="rounded-md border border-[hsl(var(--border))] px-3 py-1.5 text-xs font-medium text-[hsl(var(--muted-foreground))] transition-colors hover:bg-[hsl(var(--muted))]"
                >
                  Discard
                </button>
                <button
                  onClick={handleSaveMatrix}
                  disabled={savingMatrix}
                  className="rounded-md bg-brand-500 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {savingMatrix ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </div>
          )}

          {/* Grouped Matrix Tables */}
          {Object.entries(groupedPreferences).map(
            ([category, categoryPrefs]) => {
              const catMeta = EVENT_CATEGORY_META[category];
              return (
                <div
                  key={category}
                  className="overflow-hidden rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))]"
                >
                  {/* Category Header */}
                  <div className="flex items-center gap-2 border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-4 py-2.5">
                    <span
                      className={cn(
                        "text-xs font-semibold",
                        catMeta?.color ||
                          "text-[hsl(var(--muted-foreground))]",
                      )}
                    >
                      {category}
                    </span>
                    <span className="text-[10px] text-[hsl(var(--muted-foreground))]">
                      ({categoryPrefs.length} event
                      {categoryPrefs.length !== 1 ? "s" : ""})
                    </span>
                  </div>

                  {/* Matrix Grid */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-left">
                      <thead>
                        <tr className="border-b border-[hsl(var(--border))]">
                          <th className="px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                            Event
                          </th>
                          <th className="px-4 py-2.5 text-center text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                            In-App
                          </th>
                          <th className="px-4 py-2.5 text-center text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                            SMS
                          </th>
                          <th className="px-4 py-2.5 text-center text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                            Email
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {categoryPrefs.map((pref) => {
                          const hasChange = pendingChanges.has(
                            pref.event_slug,
                          );
                          return (
                            <tr
                              key={pref.id}
                              className={cn(
                                "border-b border-[hsl(var(--border))] last:border-0 transition-colors",
                                hasChange && "bg-brand-500/5",
                              )}
                            >
                              <td className="px-4 py-3 text-xs text-[hsl(var(--foreground))]">
                                {pref.event_label}
                              </td>
                              <td className="px-4 py-3 text-center">
                                <MatrixCheckbox
                                  checked={getEffectiveValue(pref, "in_app")}
                                  onChange={() =>
                                    handleMatrixToggle(
                                      pref.event_slug,
                                      "in_app",
                                    )
                                  }
                                  disabled={savingMatrix}
                                  label={`${pref.event_label} in-app notification`}
                                />
                              </td>
                              <td className="px-4 py-3 text-center">
                                <MatrixCheckbox
                                  checked={getEffectiveValue(pref, "sms")}
                                  onChange={() =>
                                    handleMatrixToggle(
                                      pref.event_slug,
                                      "sms",
                                    )
                                  }
                                  disabled={savingMatrix}
                                  label={`${pref.event_label} SMS notification`}
                                />
                              </td>
                              <td className="px-4 py-3 text-center">
                                <MatrixCheckbox
                                  checked={getEffectiveValue(pref, "email")}
                                  onChange={() =>
                                    handleMatrixToggle(
                                      pref.event_slug,
                                      "email",
                                    )
                                  }
                                  disabled={savingMatrix}
                                  label={`${pref.event_label} email notification`}
                                />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            },
          )}

          {preferences.length === 0 && (
            <p className="py-8 text-center text-sm text-[hsl(var(--muted-foreground))]">
              No notification preferences found. They will be auto-created when
              you first access this page.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
