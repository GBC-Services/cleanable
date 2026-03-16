/**
 * Admin Backend Types
 * ====================
 *
 * TypeScript interfaces for the Secret Vault, Role Permission Matrix,
 * User Security Management, and Command Palette modules.
 */

// ── Secret Vault ──────────────────────────────────────────────────────

export type VaultProvider =
  | "stripe"
  | "mapbox"
  | "twilio"
  | "smart_lock"
  | "cloudflare"
  | "sendgrid"
  | "custom";

export type VaultScope = "read" | "write" | "full";
export type VaultEnvironment = "sandbox" | "production";
export type VaultStatus = "active" | "rotated" | "revoked" | "expired";

export interface SecretVaultEntry {
  id: string;
  label: string;
  provider: VaultProvider;
  scope: VaultScope;
  environment: VaultEnvironment;
  status: VaultStatus;
  masked_value: string;
  key_prefix: string;
  key_hint: string;
  auto_rotate: boolean;
  rotation_interval_days: number;
  last_rotated_at: string | null;
  next_rotation_at: string | null;
  rotation_count: number;
  created_by: number | null;
  created_by_email: string;
  revoked_by: number | null;
  revoked_by_email: string;
  revoked_at: string | null;
  revoke_reason: string;
  notes: string;
  is_due_for_rotation: boolean;
  created_at: string;
  updated_at: string;
}

export interface SecretVaultCreatePayload {
  label: string;
  provider: VaultProvider;
  scope: VaultScope;
  environment: VaultEnvironment;
  encrypted_value: string;
  auto_rotate: boolean;
  rotation_interval_days: number;
  notes?: string;
}

export const PROVIDER_META: Record<
  VaultProvider,
  { label: string; icon: string; color: string }
> = {
  stripe: { label: "Stripe", icon: "credit-card", color: "text-purple-500" },
  mapbox: { label: "Mapbox", icon: "map", color: "text-blue-500" },
  twilio: { label: "Twilio", icon: "phone", color: "text-red-500" },
  smart_lock: { label: "Smart Lock", icon: "lock", color: "text-amber-500" },
  cloudflare: { label: "Cloudflare", icon: "cloud", color: "text-orange-500" },
  sendgrid: { label: "SendGrid", icon: "mail", color: "text-sky-500" },
  custom: { label: "Custom", icon: "key", color: "text-gray-500" },
};

export const SCOPE_META: Record<VaultScope, { label: string; badge: string }> = {
  read: { label: "Read Only", badge: "bg-emerald-500/10 text-emerald-600" },
  write: { label: "Write Only", badge: "bg-amber-500/10 text-amber-600" },
  full: { label: "Full Access", badge: "bg-red-500/10 text-red-600" },
};

export const STATUS_META: Record<
  VaultStatus,
  { label: string; dot: string }
> = {
  active: { label: "Active", dot: "bg-emerald-500" },
  rotated: { label: "Rotated", dot: "bg-blue-500" },
  revoked: { label: "Revoked", dot: "bg-red-500" },
  expired: { label: "Expired", dot: "bg-gray-400" },
};

// ── Role Permission Matrix ────────────────────────────────────────────

export interface PermissionMatrixEntry {
  id: string;
  role: number;
  role_display: string;
  permission: string;
  permission_display: string;
  is_granted: boolean;
  updated_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface RoleDefinition {
  value: number;
  label: string;
}

export interface PermissionDefinition {
  value: string;
  label: string;
}

export interface PermissionMatrixResponse {
  entries: PermissionMatrixEntry[];
  roles: RoleDefinition[];
  permissions: PermissionDefinition[];
  matrix: Record<number, Record<string, boolean>>;
}

export interface PermissionMatrixUpdatePayload {
  entries: {
    role: number;
    permission: string;
    is_granted: boolean;
  }[];
}

// ── User Security ─────────────────────────────────────────────────────

export type SecurityActionType =
  | "password_force_reset"
  | "mfa_enroll"
  | "mfa_revoke"
  | "account_lock"
  | "account_unlock";

export interface AdminUserEntry {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: number;
  role_display: string;
  is_active: boolean;
  is_verified: boolean;
  is_superuser: boolean;
  mfa_enabled: boolean;
  date_joined: string;
  last_login: string | null;
}

export interface SecurityAction {
  id: string;
  admin: number | null;
  admin_email: string;
  target_user: number;
  target_user_email: string;
  target_user_name: string;
  action: SecurityActionType;
  status: string;
  reason: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export const SECURITY_ACTION_META: Record<
  SecurityActionType,
  { label: string; icon: string; severity: "info" | "warning" | "critical" }
> = {
  password_force_reset: {
    label: "Force Password Reset",
    icon: "key-round",
    severity: "critical",
  },
  mfa_enroll: {
    label: "Enable MFA",
    icon: "shield-check",
    severity: "info",
  },
  mfa_revoke: {
    label: "Revoke MFA",
    icon: "shield-off",
    severity: "warning",
  },
  account_lock: {
    label: "Lock Account",
    icon: "lock",
    severity: "critical",
  },
  account_unlock: {
    label: "Unlock Account",
    icon: "lock-open",
    severity: "warning",
  },
};

// ── Command Palette ───────────────────────────────────────────────────

export type SearchResultType =
  | "user"
  | "vault"
  | "feature"
  | "integration"
  | "navigation";

export interface CommandPaletteResult {
  type: SearchResultType;
  id: string | number;
  title: string;
  subtitle: string;
  url: string;
}

export interface CommandPaletteResponse {
  results: CommandPaletteResult[];
}

export const RESULT_TYPE_META: Record<
  SearchResultType,
  { label: string; icon: string }
> = {
  user: { label: "User", icon: "user" },
  vault: { label: "Secret", icon: "key" },
  feature: { label: "Feature", icon: "toggle-left" },
  integration: { label: "Integration", icon: "plug" },
  navigation: { label: "Navigate", icon: "arrow-right" },
};
