/**
 * Governance types — feature toggles, privacy, break-glass, audit logs.
 * Must match the Django governance models exactly.
 */

// ── SystemFeatureToggle ──────────────────────────────────────────────

export type FeatureCategory =
  | "location"
  | "iot"
  | "media"
  | "ai"
  | "communications"
  | "security";

export type FeatureSeverity = "low" | "medium" | "high" | "critical";

export interface SystemFeatureToggle {
  id: string;
  slug: string;
  name: string;
  description: string;
  category: FeatureCategory;
  severity: FeatureSeverity;
  is_enabled: boolean;
  toggled_by: number | null;
  toggled_by_email: string;
  toggled_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SystemFeatureToggleListItem {
  id: string;
  slug: string;
  name: string;
  category: FeatureCategory;
  severity: FeatureSeverity;
  is_enabled: boolean;
  toggled_at: string | null;
}

// ── Category metadata for UI ─────────────────────────────────────────

export const CATEGORY_META: Record<
  FeatureCategory,
  { label: string; icon: string; color: string }
> = {
  location: {
    label: "Location Services",
    icon: "MapPin",
    color: "text-blue-600 dark:text-blue-400",
  },
  iot: {
    label: "IoT & Smart Home",
    icon: "Cpu",
    color: "text-purple-600 dark:text-purple-400",
  },
  media: {
    label: "Media & Recording",
    icon: "Video",
    color: "text-pink-600 dark:text-pink-400",
  },
  ai: {
    label: "AI & Machine Learning",
    icon: "Brain",
    color: "text-amber-600 dark:text-amber-400",
  },
  communications: {
    label: "Communications",
    icon: "Bell",
    color: "text-green-600 dark:text-green-400",
  },
  security: {
    label: "Security & Escalation",
    icon: "Shield",
    color: "text-red-600 dark:text-red-400",
  },
};

export const SEVERITY_META: Record<
  FeatureSeverity,
  { label: string; dotColor: string; bgColor: string }
> = {
  low: {
    label: "Low Risk",
    dotColor: "bg-green-500",
    bgColor: "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400",
  },
  medium: {
    label: "Medium Risk",
    dotColor: "bg-yellow-500",
    bgColor: "bg-yellow-50 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400",
  },
  high: {
    label: "High Risk",
    dotColor: "bg-orange-500",
    bgColor: "bg-orange-50 text-orange-700 dark:bg-orange-900/20 dark:text-orange-400",
  },
  critical: {
    label: "Critical Risk",
    dotColor: "bg-red-500",
    bgColor: "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400",
  },
};

// ── GovernanceAuditLog ───────────────────────────────────────────────

export type AuditAction =
  | "feature_toggled"
  | "privacy_updated"
  | "break_glass_requested"
  | "break_glass_activated"
  | "break_glass_revoked"
  | "break_glass_expired"
  | "override_applied"
  | "override_reverted";

export type AuditSeverity = "info" | "warning" | "critical";

export interface GovernanceAuditLog {
  id: string;
  actor: number | null;
  actor_email: string;
  actor_role: number | null;
  action: AuditAction;
  severity: AuditSeverity;
  description: string;
  target_user: number | null;
  target_user_email: string;
  changes: Record<string, { old: unknown; new: unknown }>;
  related_feature_toggle: string | null;
  related_break_glass: string | null;
  ip_address: string | null;
  user_agent: string;
  timestamp: string;
}

// ── BreakGlassSession ────────────────────────────────────────────────

export type BreakGlassStatus = "pending" | "active" | "expired" | "revoked";

export interface BreakGlassSession {
  id: string;
  initiated_by: number;
  initiated_by_email: string;
  target_user: number;
  target_user_email: string;
  status: BreakGlassStatus;
  reason: string;
  escalation_reference: string;
  overrides_applied: Record<
    string,
    { original: boolean; overridden_to: boolean }
  >;
  requested_duration_minutes: number;
  activated_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  revoked_by: number | null;
  revoked_by_email: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
