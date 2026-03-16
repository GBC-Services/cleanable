"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type {
  PermissionMatrixResponse,
  RoleDefinition,
  PermissionDefinition,
} from "@/types/admin-backend";

// ── Helpers ──────────────────────────────────────────────────────────

function cn(...classes: (string | false | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

// Role badge colors (consistent with the platform)
const ROLE_COLORS: Record<number, string> = {
  10: "bg-sky-500/10 text-sky-600",
  20: "bg-violet-500/10 text-violet-600",
  30: "bg-emerald-500/10 text-emerald-600",
  40: "bg-amber-500/10 text-amber-600",
  50: "bg-blue-500/10 text-blue-600",
  60: "bg-pink-500/10 text-pink-600",
  70: "bg-orange-500/10 text-orange-600",
};

// ── Permission Cell ──────────────────────────────────────────────────

function PermissionCell({
  isGranted,
  onChange,
  disabled,
}: {
  isGranted: boolean;
  onChange: (granted: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={() => onChange(!isGranted)}
      disabled={disabled}
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded-md transition-all duration-150",
        isGranted
          ? "bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/25"
          : "bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] hover:bg-red-500/10 hover:text-red-500",
        disabled && "opacity-40 cursor-not-allowed",
      )}
    >
      {isGranted ? (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
        </svg>
      ) : (
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      )}
    </button>
  );
}

// ── Main Page ────────────────────────────────────────────────────────

export default function PermissionsMatrixPage() {
  const [matrix, setMatrix] = useState<Record<number, Record<string, boolean>>>({});
  const [roles, setRoles] = useState<RoleDefinition[]>([]);
  const [permissions, setPermissions] = useState<PermissionDefinition[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [pendingChanges, setPendingChanges] = useState<
    { role: number; permission: string; is_granted: boolean }[]
  >([]);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saved" | "error">("idle");

  const fetchMatrix = useCallback(async () => {
    try {
      const data = await api.get<PermissionMatrixResponse>(
        "/governance/permissions/matrix/",
      );
      setMatrix(data.matrix);
      setRoles(data.roles);
      setPermissions(data.permissions);
    } catch (err) {
      console.error("Failed to fetch permission matrix:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMatrix();
  }, [fetchMatrix]);

  const handleToggle = (role: number, permission: string, granted: boolean) => {
    // Update local matrix immediately for instant feedback
    setMatrix((prev) => ({
      ...prev,
      [role]: {
        ...prev[role],
        [permission]: granted,
      },
    }));

    // Track pending changes
    setPendingChanges((prev) => {
      const existing = prev.findIndex(
        (c) => c.role === role && c.permission === permission,
      );
      const newEntry = { role, permission, is_granted: granted };
      if (existing >= 0) {
        const updated = [...prev];
        updated[existing] = newEntry;
        return updated;
      }
      return [...prev, newEntry];
    });

    setSaveStatus("idle");
  };

  const handleSave = async () => {
    if (pendingChanges.length === 0) return;
    setIsSaving(true);
    setSaveStatus("idle");

    try {
      const data = await api.put<PermissionMatrixResponse>(
        "/governance/permissions/matrix/",
        { entries: pendingChanges },
      );
      setMatrix(data.matrix);
      setPendingChanges([]);
      setSaveStatus("saved");
      setTimeout(() => setSaveStatus("idle"), 2000);
    } catch (err) {
      console.error("Failed to save permissions:", err);
      setSaveStatus("error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setPendingChanges([]);
    fetchMatrix();
    setSaveStatus("idle");
  };

  // Count granted permissions per role
  const roleGrantCount = (role: number): number => {
    if (!matrix[role]) return 0;
    return Object.values(matrix[role]).filter(Boolean).length;
  };

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="h-8 w-64 animate-pulse rounded bg-[hsl(var(--muted))]" />
        <div className="h-[500px] animate-pulse rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--muted))]" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[hsl(var(--foreground))]">
            Permissions Matrix
          </h1>
          <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
            Control which capabilities each role has across the platform.
          </p>
        </div>

        {/* Save controls */}
        <div className="flex items-center gap-2">
          {pendingChanges.length > 0 && (
            <span className="rounded-full bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-600">
              {pendingChanges.length} unsaved {pendingChanges.length === 1 ? "change" : "changes"}
            </span>
          )}
          {saveStatus === "saved" && (
            <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-600">
              Saved
            </span>
          )}
          {saveStatus === "error" && (
            <span className="rounded-full bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-600">
              Error saving
            </span>
          )}
          {pendingChanges.length > 0 && (
            <>
              <button
                onClick={handleReset}
                disabled={isSaving}
                className="rounded-md px-3 py-1.5 text-xs font-medium text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] disabled:opacity-40"
              >
                Discard
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="rounded-md bg-[hsl(var(--foreground))] px-4 py-1.5 text-xs font-semibold text-[hsl(var(--background))] transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                {isSaving ? "Saving..." : "Save Changes"}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Matrix Grid */}
      <div className="overflow-x-auto rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))]">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[hsl(var(--border))]">
              <th className="sticky left-0 z-10 bg-[hsl(var(--card))] px-4 py-3 text-left">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                  Permission
                </span>
              </th>
              {roles.map((role) => (
                <th key={role.value} className="px-2 py-3 text-center">
                  <div className="flex flex-col items-center gap-1">
                    <span
                      className={cn(
                        "inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold",
                        ROLE_COLORS[role.value] || "bg-gray-100 text-gray-600",
                      )}
                    >
                      {role.label}
                    </span>
                    <span className="text-[10px] text-[hsl(var(--muted-foreground))]">
                      {roleGrantCount(role.value)}/{permissions.length}
                    </span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {permissions.map((perm, idx) => (
              <tr
                key={perm.value}
                className={cn(
                  "border-b border-[hsl(var(--border))] transition-colors",
                  idx % 2 === 0 ? "" : "bg-[hsl(var(--muted))]/30",
                )}
              >
                <td className="sticky left-0 z-10 bg-[hsl(var(--card))] px-4 py-2.5">
                  <span className="text-xs font-medium text-[hsl(var(--foreground))]">
                    {perm.label}
                  </span>
                </td>
                {roles.map((role) => (
                  <td key={`${role.value}-${perm.value}`} className="px-2 py-2.5 text-center">
                    <div className="flex justify-center">
                      <PermissionCell
                        isGranted={matrix[role.value]?.[perm.value] ?? false}
                        onChange={(granted) => handleToggle(role.value, perm.value, granted)}
                      />
                    </div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 text-[11px] text-[hsl(var(--muted-foreground))]">
        <div className="flex items-center gap-1.5">
          <div className="flex h-5 w-5 items-center justify-center rounded bg-emerald-500/15 text-emerald-600">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
          </div>
          Granted
        </div>
        <div className="flex items-center gap-1.5">
          <div className="flex h-5 w-5 items-center justify-center rounded bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          Denied
        </div>
        <span className="ml-auto">
          Click any cell to toggle. Changes are batched until you save.
        </span>
      </div>
    </div>
  );
}
