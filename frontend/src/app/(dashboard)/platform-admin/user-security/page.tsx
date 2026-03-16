"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type {
  AdminUserEntry,
  SecurityAction,
  SecurityActionType,
} from "@/types/admin-backend";
import { SECURITY_ACTION_META } from "@/types/admin-backend";

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

const ROLE_COLORS: Record<number, string> = {
  10: "bg-sky-500/10 text-sky-600",
  20: "bg-violet-500/10 text-violet-600",
  30: "bg-emerald-500/10 text-emerald-600",
  40: "bg-amber-500/10 text-amber-600",
  50: "bg-blue-500/10 text-blue-600",
  60: "bg-pink-500/10 text-pink-600",
  70: "bg-orange-500/10 text-orange-600",
};

// ── User Row ─────────────────────────────────────────────────────────

function UserRow({
  user,
  onAction,
  isSelected,
  onClick,
}: {
  user: AdminUserEntry;
  onAction: (userId: number, action: SecurityActionType) => void;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-4 rounded-lg border p-4 transition-all cursor-pointer",
        isSelected
          ? "border-brand-500/30 bg-brand-500/5"
          : "border-[hsl(var(--border))] bg-[hsl(var(--card))] hover:border-[hsl(var(--border))]/60",
      )}
      onClick={onClick}
    >
      {/* Avatar */}
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[hsl(var(--muted))] text-sm font-semibold text-[hsl(var(--foreground))]">
        {(user.first_name?.[0] || user.email[0]).toUpperCase()}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-[hsl(var(--foreground))] truncate">
            {user.full_name}
          </h3>
          <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", ROLE_COLORS[user.role])}>
            {user.role_display}
          </span>
          {!user.is_active && (
            <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-[10px] font-medium text-red-600">
              Locked
            </span>
          )}
          {user.mfa_enabled && (
            <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-600">
              MFA
            </span>
          )}
        </div>
        <p className="text-xs text-[hsl(var(--muted-foreground))]">{user.email}</p>
      </div>

      {/* Meta */}
      <div className="text-right text-[10px] text-[hsl(var(--muted-foreground))] hidden sm:block">
        <p>Joined {formatDate(user.date_joined)}</p>
        <p>Last login {formatDate(user.last_login)}</p>
      </div>

      {/* Quick Actions */}
      <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={() => onAction(user.id, "password_force_reset")}
          title="Force Password Reset"
          className="rounded-md p-2 text-[hsl(var(--muted-foreground))] transition-colors hover:bg-amber-500/10 hover:text-amber-600"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" />
          </svg>
        </button>
        {user.is_active ? (
          <button
            onClick={() => onAction(user.id, "account_lock")}
            title="Lock Account"
            className="rounded-md p-2 text-[hsl(var(--muted-foreground))] transition-colors hover:bg-red-500/10 hover:text-red-600"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
            </svg>
          </button>
        ) : (
          <button
            onClick={() => onAction(user.id, "account_unlock")}
            title="Unlock Account"
            className="rounded-md p-2 text-[hsl(var(--muted-foreground))] transition-colors hover:bg-emerald-500/10 hover:text-emerald-600"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 10.5V6.75a4.5 4.5 0 119 0v3.75M3.75 21.75h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H3.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

// ── Action History Panel ─────────────────────────────────────────────

function HistoryPanel({ userId }: { userId: number | null }) {
  const [history, setHistory] = useState<SecurityAction[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!userId) {
      setHistory([]);
      return;
    }
    setIsLoading(true);
    api
      .get<SecurityAction[]>(`/governance/user-security/history/?target_user=${userId}`)
      .then(setHistory)
      .catch(console.error)
      .finally(() => setIsLoading(false));
  }, [userId]);

  if (!userId) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-[hsl(var(--muted-foreground))]">
        Select a user to view their security history.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-16 animate-pulse rounded-lg bg-[hsl(var(--muted))]" />
        ))}
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-[hsl(var(--muted-foreground))]">
        No security actions recorded for this user.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {history.map((action) => {
        const meta = SECURITY_ACTION_META[action.action];
        return (
          <div
            key={action.id}
            className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-3"
          >
            <div className="flex items-start gap-2">
              <div
                className={cn(
                  "mt-0.5 flex h-6 w-6 items-center justify-center rounded-md",
                  meta.severity === "critical" ? "bg-red-500/10 text-red-600" :
                  meta.severity === "warning" ? "bg-amber-500/10 text-amber-600" :
                  "bg-blue-500/10 text-blue-600",
                )}
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-[hsl(var(--foreground))]">
                  {meta.label}
                </p>
                <p className="text-[10px] text-[hsl(var(--muted-foreground))]">
                  by {action.admin_email} — {formatDate(action.created_at)}
                </p>
                {action.reason && (
                  <p className="mt-1 text-[10px] text-[hsl(var(--muted-foreground))]">
                    Reason: {action.reason}
                  </p>
                )}
              </div>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-[10px] font-medium",
                  action.status === "completed" ? "bg-emerald-500/10 text-emerald-600" :
                  action.status === "failed" ? "bg-red-500/10 text-red-600" :
                  "bg-amber-500/10 text-amber-600",
                )}
              >
                {action.status}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Confirmation Modal ───────────────────────────────────────────────

function ConfirmActionModal({
  action,
  userName,
  onClose,
  onConfirm,
  isLoading,
  result,
}: {
  action: SecurityActionType | null;
  userName: string;
  onClose: () => void;
  onConfirm: (reason: string) => void;
  isLoading: boolean;
  result: SecurityAction | null;
}) {
  const [reason, setReason] = useState("");

  if (!action) return null;

  const meta = SECURITY_ACTION_META[action];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] shadow-2xl">
        <div className="px-6 py-4 border-b border-[hsl(var(--border))]">
          <h2 className="text-sm font-semibold text-[hsl(var(--foreground))]">
            {meta.label}
          </h2>
          <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
            This action will be performed on {userName}.
          </p>
        </div>

        <div className="px-6 py-5 space-y-4">
          {meta.severity === "critical" && (
            <div className="rounded-md bg-red-500/10 px-3 py-2 text-xs text-red-600">
              This is a critical security action and will be logged permanently.
            </div>
          )}

          {result ? (
            <div className="space-y-2">
              <div className="rounded-md bg-emerald-500/10 px-3 py-2 text-xs text-emerald-600">
                Action completed successfully.
              </div>
              {result.metadata && Boolean((result.metadata as Record<string, unknown>).temp_password) && (
                <div className="rounded-md bg-amber-500/10 px-3 py-2">
                  <p className="text-xs font-medium text-amber-600">Temporary Password</p>
                  <p className="mt-1 font-mono text-sm text-[hsl(var(--foreground))] select-all">
                    {String((result.metadata as Record<string, unknown>).temp_password)}
                  </p>
                  <p className="mt-1 text-[10px] text-amber-600">
                    Copy this now. It will not be shown again.
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div>
              <label className="block text-xs font-medium text-[hsl(var(--foreground))]">
                Reason (optional)
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                placeholder="Why is this action needed?"
                className="mt-1 w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-[hsl(var(--border))] px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-md px-4 py-2 text-xs font-medium text-[hsl(var(--muted-foreground))]"
          >
            {result ? "Close" : "Cancel"}
          </button>
          {!result && (
            <button
              onClick={() => onConfirm(reason)}
              disabled={isLoading}
              className={cn(
                "rounded-md px-4 py-2 text-xs font-medium text-white disabled:opacity-40",
                meta.severity === "critical" ? "bg-red-600 hover:bg-red-700" : "bg-[hsl(var(--foreground))]",
              )}
            >
              {isLoading ? "Processing..." : "Confirm"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────

export default function UserSecurityPage() {
  const [users, setUsers] = useState<AdminUserEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<number | "all">("all");
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [actionModal, setActionModal] = useState<{
    userId: number;
    action: SecurityActionType;
    userName: string;
  } | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionResult, setActionResult] = useState<SecurityAction | null>(null);

  const fetchUsers = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (roleFilter !== "all") params.set("role", String(roleFilter));
      const query = params.toString();
      const data = await api.get<AdminUserEntry[]>(
        `/governance/user-security/${query ? `?${query}` : ""}`,
      );
      setUsers(data);
    } catch (err) {
      console.error("Failed to fetch users:", err);
    } finally {
      setIsLoading(false);
    }
  }, [search, roleFilter]);

  useEffect(() => {
    const timer = setTimeout(fetchUsers, 300);
    return () => clearTimeout(timer);
  }, [fetchUsers]);

  const handleAction = (userId: number, action: SecurityActionType) => {
    const user = users.find((u) => u.id === userId);
    if (!user) return;
    setActionModal({ userId, action, userName: user.full_name });
    setActionResult(null);
  };

  const handleConfirmAction = async (reason: string) => {
    if (!actionModal) return;
    setActionLoading(true);
    try {
      const result = await api.post<SecurityAction>("/governance/user-security/action/", {
        target_user_id: actionModal.userId,
        action: actionModal.action,
        reason,
      });
      setActionResult(result);
      // Refresh user list to reflect changes (e.g., account lock)
      fetchUsers();
    } catch (err) {
      console.error("Failed to perform action:", err);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold tracking-tight text-[hsl(var(--foreground))]">
          User Security
        </h1>
        <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
          Manage passwords, MFA enrollment, and account access for all platform users.
        </p>
      </div>

      {/* Search + Filter bar */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[hsl(var(--muted-foreground))]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or email..."
            className="w-full rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] py-2 pl-9 pr-3 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
        <select
          value={roleFilter === "all" ? "all" : String(roleFilter)}
          onChange={(e) => setRoleFilter(e.target.value === "all" ? "all" : Number(e.target.value))}
          className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-3 py-2 text-sm text-[hsl(var(--foreground))] focus:border-brand-500 focus:outline-none"
        >
          <option value="all">All Roles</option>
          <option value="10">Resident</option>
          <option value="20">Platform Admin</option>
          <option value="30">Agency Owner</option>
          <option value="40">Service Pro</option>
          <option value="50">Support Architect</option>
          <option value="60">QA Inspector</option>
          <option value="70">Fiscal Auditor</option>
        </select>
      </div>

      {/* Two-column layout: Users list + History panel */}
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        {/* Users list */}
        <div className="space-y-2">
          {isLoading ? (
            [...Array(5)].map((_, i) => (
              <div key={i} className="h-20 animate-pulse rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--muted))]" />
            ))
          ) : users.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[hsl(var(--border))] py-16">
              <p className="text-sm font-medium text-[hsl(var(--foreground))]">
                No users found
              </p>
              <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
                Try adjusting your search or filters.
              </p>
            </div>
          ) : (
            users.map((user) => (
              <UserRow
                key={user.id}
                user={user}
                onAction={handleAction}
                isSelected={selectedUserId === user.id}
                onClick={() => setSelectedUserId(user.id)}
              />
            ))
          )}
        </div>

        {/* History panel */}
        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Security History
          </h3>
          <HistoryPanel userId={selectedUserId} />
        </div>
      </div>

      {/* Action confirmation modal */}
      <ConfirmActionModal
        action={actionModal?.action || null}
        userName={actionModal?.userName || ""}
        onClose={() => {
          setActionModal(null);
          setActionResult(null);
        }}
        onConfirm={handleConfirmAction}
        isLoading={actionLoading}
        result={actionResult}
      />
    </div>
  );
}
