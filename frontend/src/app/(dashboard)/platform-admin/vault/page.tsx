"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type {
  SecretVaultEntry,
  SecretVaultCreatePayload,
  VaultProvider,
  VaultScope,
  VaultEnvironment,
  VaultStatus,
} from "@/types/admin-backend";
import { PROVIDER_META, SCOPE_META, STATUS_META } from "@/types/admin-backend";

// ── Helpers ──────────────────────────────────────────────────────────

function cn(...classes: (string | false | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

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

// ── Icon Components ──────────────────────────────────────────────────

function IconKey({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" />
    </svg>
  );
}

function IconShield({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
    </svg>
  );
}

function IconRefresh({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
    </svg>
  );
}

function IconBan({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
    </svg>
  );
}

function IconPlus({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  );
}

function IconX({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

// ── Vault Card ───────────────────────────────────────────────────────

function VaultCard({
  entry,
  onRotate,
  onRevoke,
  isLoading,
}: {
  entry: SecretVaultEntry;
  onRotate: (id: string) => void;
  onRevoke: (id: string) => void;
  isLoading: boolean;
}) {
  const provider = PROVIDER_META[entry.provider];
  const scope = SCOPE_META[entry.scope];
  const statusMeta = STATUS_META[entry.status];

  return (
    <div
      className={cn(
        "rounded-lg border transition-all duration-200",
        entry.status === "active"
          ? "border-[hsl(var(--border))] bg-[hsl(var(--card))]"
          : "border-[hsl(var(--border))] bg-[hsl(var(--card))] opacity-60",
      )}
    >
      <div className="p-5">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2.5">
              <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg bg-[hsl(var(--muted))]", provider.color)}>
                <IconKey className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[hsl(var(--foreground))]">
                  {entry.label}
                </h3>
                <p className="text-[11px] text-[hsl(var(--muted-foreground))]">
                  {provider.label}
                </p>
              </div>
            </div>
          </div>

          {/* Status dot */}
          <div className="flex items-center gap-1.5">
            <span className={cn("h-2 w-2 rounded-full", statusMeta.dot)} />
            <span className="text-[11px] font-medium text-[hsl(var(--muted-foreground))]">
              {statusMeta.label}
            </span>
          </div>
        </div>

        {/* Masked key display */}
        <div className="mt-4 rounded-md bg-[hsl(var(--muted))] px-3 py-2 font-mono text-xs text-[hsl(var(--muted-foreground))]">
          {entry.masked_value}
        </div>

        {/* Metadata row */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", scope.badge)}>
            {scope.label}
          </span>
          <span className={cn(
            "rounded-full px-2 py-0.5 text-[10px] font-medium",
            entry.environment === "production"
              ? "bg-red-500/10 text-red-600"
              : "bg-sky-500/10 text-sky-600",
          )}>
            {entry.environment === "production" ? "Production" : "Sandbox"}
          </span>
          {entry.auto_rotate && (
            <span className="rounded-full bg-violet-500/10 px-2 py-0.5 text-[10px] font-medium text-violet-600">
              Auto-rotate: {entry.rotation_interval_days}d
            </span>
          )}
          {entry.is_due_for_rotation && (
            <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-600">
              Rotation due
            </span>
          )}
        </div>

        {/* Timestamps */}
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-[hsl(var(--muted-foreground))]">
          <span>Created {formatDate(entry.created_at)}</span>
          {entry.rotation_count > 0 && (
            <span>Rotated {entry.rotation_count}x — Last {formatDate(entry.last_rotated_at)}</span>
          )}
          {entry.revoked_at && (
            <span>Revoked {formatDate(entry.revoked_at)}</span>
          )}
        </div>

        {/* Actions */}
        {entry.status === "active" && (
          <div className="mt-4 flex gap-2 border-t border-[hsl(var(--border))] pt-3">
            <button
              onClick={() => onRotate(entry.id)}
              disabled={isLoading}
              className="flex items-center gap-1.5 rounded-md bg-[hsl(var(--muted))] px-3 py-1.5 text-xs font-medium text-[hsl(var(--foreground))] transition-colors hover:bg-[hsl(var(--muted))]/80 disabled:opacity-40"
            >
              <IconRefresh className="h-3.5 w-3.5" />
              Rotate
            </button>
            <button
              onClick={() => onRevoke(entry.id)}
              disabled={isLoading}
              className="flex items-center gap-1.5 rounded-md bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-500/20 disabled:opacity-40"
            >
              <IconBan className="h-3.5 w-3.5" />
              Revoke
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Create Modal ─────────────────────────────────────────────────────

function CreateSecretModal({
  isOpen,
  onClose,
  onCreate,
  isLoading,
}: {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (data: SecretVaultCreatePayload) => void;
  isLoading: boolean;
}) {
  const [form, setForm] = useState<SecretVaultCreatePayload>({
    label: "",
    provider: "stripe",
    scope: "full",
    environment: "sandbox",
    encrypted_value: "",
    auto_rotate: false,
    rotation_interval_days: 90,
    notes: "",
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] shadow-2xl">
        <div className="flex items-center justify-between border-b border-[hsl(var(--border))] px-6 py-4">
          <h2 className="text-sm font-semibold text-[hsl(var(--foreground))]">
            Add New Secret
          </h2>
          <button onClick={onClose} className="rounded-md p-1 hover:bg-[hsl(var(--muted))]">
            <IconX className="h-4 w-4 text-[hsl(var(--muted-foreground))]" />
          </button>
        </div>

        <div className="space-y-4 px-6 py-5">
          {/* Label */}
          <div>
            <label className="block text-xs font-medium text-[hsl(var(--foreground))]">Label</label>
            <input
              type="text"
              value={form.label}
              onChange={(e) => setForm({ ...form, label: e.target.value })}
              placeholder="e.g. Stripe Live Key"
              className="mt-1 w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>

          {/* Provider + Scope row */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-[hsl(var(--foreground))]">Provider</label>
              <select
                value={form.provider}
                onChange={(e) => setForm({ ...form, provider: e.target.value as VaultProvider })}
                className="mt-1 w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] focus:border-brand-500 focus:outline-none"
              >
                {Object.entries(PROVIDER_META).map(([key, meta]) => (
                  <option key={key} value={key}>{meta.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-[hsl(var(--foreground))]">Scope</label>
              <select
                value={form.scope}
                onChange={(e) => setForm({ ...form, scope: e.target.value as VaultScope })}
                className="mt-1 w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] focus:border-brand-500 focus:outline-none"
              >
                {Object.entries(SCOPE_META).map(([key, meta]) => (
                  <option key={key} value={key}>{meta.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Environment */}
          <div>
            <label className="block text-xs font-medium text-[hsl(var(--foreground))]">Environment</label>
            <div className="mt-1.5 flex gap-2">
              {(["sandbox", "production"] as VaultEnvironment[]).map((env) => (
                <button
                  key={env}
                  onClick={() => setForm({ ...form, environment: env })}
                  className={cn(
                    "flex-1 rounded-md border px-3 py-2 text-xs font-medium transition-all",
                    form.environment === env
                      ? env === "production"
                        ? "border-red-500/30 bg-red-500/10 text-red-600"
                        : "border-brand-500/30 bg-brand-500/10 text-brand-500"
                      : "border-[hsl(var(--border))] bg-[hsl(var(--background))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))]",
                  )}
                >
                  {env === "production" ? "Production" : "Sandbox"}
                </button>
              ))}
            </div>
          </div>

          {/* Key value */}
          <div>
            <label className="block text-xs font-medium text-[hsl(var(--foreground))]">API Key / Secret</label>
            <input
              type="password"
              value={form.encrypted_value}
              onChange={(e) => setForm({ ...form, encrypted_value: e.target.value })}
              placeholder="sk_live_••••••••••"
              className="mt-1 w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 font-mono text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>

          {/* Auto-rotate */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setForm({ ...form, auto_rotate: !form.auto_rotate })}
              className={cn(
                "relative h-5 w-9 rounded-full transition-colors duration-200",
                form.auto_rotate ? "bg-brand-500" : "bg-[hsl(var(--muted))]",
              )}
            >
              <span
                className={cn(
                  "absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white transition-transform duration-200 shadow-sm",
                  form.auto_rotate && "translate-x-4",
                )}
              />
            </button>
            <span className="text-xs text-[hsl(var(--foreground))]">
              Auto-rotate every
            </span>
            <input
              type="number"
              value={form.rotation_interval_days}
              onChange={(e) => setForm({ ...form, rotation_interval_days: Number(e.target.value) })}
              disabled={!form.auto_rotate}
              min={1}
              max={365}
              className="w-16 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-2 py-1 text-center text-xs text-[hsl(var(--foreground))] disabled:opacity-40 focus:border-brand-500 focus:outline-none"
            />
            <span className="text-xs text-[hsl(var(--muted-foreground))]">days</span>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-xs font-medium text-[hsl(var(--foreground))]">Notes (optional)</label>
            <textarea
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              rows={2}
              className="mt-1 w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t border-[hsl(var(--border))] px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-md px-4 py-2 text-xs font-medium text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
          >
            Cancel
          </button>
          <button
            onClick={() => onCreate(form)}
            disabled={isLoading || !form.label || !form.encrypted_value}
            className="rounded-md bg-[hsl(var(--foreground))] px-4 py-2 text-xs font-medium text-[hsl(var(--background))] transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {isLoading ? "Creating..." : "Add Secret"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Rotate Modal ─────────────────────────────────────────────────────

function RotateModal({
  entry,
  onClose,
  onConfirm,
  isLoading,
}: {
  entry: SecretVaultEntry | null;
  onClose: () => void;
  onConfirm: (id: string, newValue: string) => void;
  isLoading: boolean;
}) {
  const [newValue, setNewValue] = useState("");

  if (!entry) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] shadow-2xl">
        <div className="px-6 py-4 border-b border-[hsl(var(--border))]">
          <h2 className="text-sm font-semibold text-[hsl(var(--foreground))]">
            Rotate Secret
          </h2>
          <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
            Replace "{entry.label}" with a new key value.
          </p>
        </div>
        <div className="px-6 py-5">
          <div className="mb-3 rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-600">
            The old key will be invalidated immediately. Current: {entry.masked_value}
          </div>
          <input
            type="password"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder="Paste new API key..."
            className="w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 font-mono text-sm text-[hsl(var(--foreground))] focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
        <div className="flex justify-end gap-2 border-t border-[hsl(var(--border))] px-6 py-4">
          <button onClick={onClose} className="rounded-md px-4 py-2 text-xs font-medium text-[hsl(var(--muted-foreground))]">
            Cancel
          </button>
          <button
            onClick={() => onConfirm(entry.id, newValue)}
            disabled={isLoading || newValue.length < 8}
            className="rounded-md bg-[hsl(var(--foreground))] px-4 py-2 text-xs font-medium text-[hsl(var(--background))] disabled:opacity-40"
          >
            {isLoading ? "Rotating..." : "Confirm Rotation"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────

export default function VaultPage() {
  const [secrets, setSecrets] = useState<SecretVaultEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [rotateEntry, setRotateEntry] = useState<SecretVaultEntry | null>(null);
  const [envFilter, setEnvFilter] = useState<"all" | VaultEnvironment>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | VaultStatus>("all");

  const fetchSecrets = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (envFilter !== "all") params.set("environment", envFilter);
      if (statusFilter !== "all") params.set("status", statusFilter);
      const query = params.toString();
      const data = await api.get<SecretVaultEntry[]>(
        `/governance/vault/${query ? `?${query}` : ""}`,
      );
      setSecrets(data);
    } catch (err) {
      console.error("Failed to fetch vault secrets:", err);
    } finally {
      setIsLoading(false);
    }
  }, [envFilter, statusFilter]);

  useEffect(() => {
    fetchSecrets();
  }, [fetchSecrets]);

  const handleCreate = async (payload: SecretVaultCreatePayload) => {
    setActionLoading(true);
    try {
      await api.post("/governance/vault/", payload);
      setShowCreate(false);
      await fetchSecrets();
    } catch (err) {
      console.error("Failed to create secret:", err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRotate = async (id: string, newValue: string) => {
    setActionLoading(true);
    try {
      await api.post(`/governance/vault/${id}/rotate/`, { new_value: newValue });
      setRotateEntry(null);
      await fetchSecrets();
    } catch (err) {
      console.error("Failed to rotate secret:", err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevoke = async (id: string) => {
    if (!confirm("Are you sure you want to revoke this secret? This cannot be undone.")) return;
    setActionLoading(true);
    try {
      await api.post(`/governance/vault/${id}/revoke/`, { reason: "Admin revocation via Vault UI" });
      await fetchSecrets();
    } catch (err) {
      console.error("Failed to revoke secret:", err);
    } finally {
      setActionLoading(false);
    }
  };

  const activeCount = secrets.filter((s) => s.status === "active").length;
  const rotationDue = secrets.filter((s) => s.is_due_for_rotation).length;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[hsl(var(--foreground))]">
            Secret Vault
          </h1>
          <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
            Manage API keys and secrets for third-party integrations.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 rounded-lg bg-[hsl(var(--foreground))] px-4 py-2 text-xs font-semibold text-[hsl(var(--background))] transition-opacity hover:opacity-90"
        >
          <IconPlus className="h-3.5 w-3.5" />
          Add Secret
        </button>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          <p className="text-[11px] font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Total Secrets
          </p>
          <p className="mt-1 text-2xl font-bold text-[hsl(var(--foreground))]">{secrets.length}</p>
        </div>
        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          <p className="text-[11px] font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Active
          </p>
          <p className="mt-1 text-2xl font-bold text-emerald-500">{activeCount}</p>
        </div>
        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          <p className="text-[11px] font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Rotation Due
          </p>
          <p className={cn("mt-1 text-2xl font-bold", rotationDue > 0 ? "text-amber-500" : "text-[hsl(var(--foreground))]")}>
            {rotationDue}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        <div className="flex rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-0.5">
          {(["all", "sandbox", "production"] as const).map((env) => (
            <button
              key={env}
              onClick={() => setEnvFilter(env)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-all",
                envFilter === env
                  ? "bg-[hsl(var(--foreground))] text-[hsl(var(--background))]"
                  : "text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]",
              )}
            >
              {env === "all" ? "All Envs" : env === "production" ? "Production" : "Sandbox"}
            </button>
          ))}
        </div>
        <div className="flex rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-0.5">
          {(["all", "active", "revoked"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-all",
                statusFilter === s
                  ? "bg-[hsl(var(--foreground))] text-[hsl(var(--background))]"
                  : "text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]",
              )}
            >
              {s === "all" ? "All Status" : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Secret Cards Grid */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-48 animate-pulse rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--muted))]" />
          ))}
        </div>
      ) : secrets.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[hsl(var(--border))] py-16">
          <IconShield className="h-10 w-10 text-[hsl(var(--muted-foreground))]" />
          <p className="mt-3 text-sm font-medium text-[hsl(var(--foreground))]">
            No secrets yet
          </p>
          <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
            Add your first API key to get started.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {secrets.map((entry) => (
            <VaultCard
              key={entry.id}
              entry={entry}
              onRotate={(id) => setRotateEntry(secrets.find((s) => s.id === id) || null)}
              onRevoke={handleRevoke}
              isLoading={actionLoading}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      <CreateSecretModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        onCreate={handleCreate}
        isLoading={actionLoading}
      />
      <RotateModal
        entry={rotateEntry}
        onClose={() => setRotateEntry(null)}
        onConfirm={handleRotate}
        isLoading={actionLoading}
      />
    </div>
  );
}
