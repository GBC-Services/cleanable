/**
 * Auth types shared across the frontend.
 * Role integer values must match the Django User model exactly.
 */

export const ROLES = {
  RESIDENT: 10,
  PLATFORM_ADMIN: 20,
  AGENCY_OWNER: 30,
  SERVICE_PRO: 40,
  SUPPORT_ARCHITECT: 50,
  QA_INSPECTOR: 60,
  FISCAL_AUDITOR: 70,
} as const;

export type RoleValue = (typeof ROLES)[keyof typeof ROLES];

export const ROLE_SLUGS: Record<RoleValue, string> = {
  [ROLES.RESIDENT]: "resident",
  [ROLES.PLATFORM_ADMIN]: "platform_admin",
  [ROLES.AGENCY_OWNER]: "agency_owner",
  [ROLES.SERVICE_PRO]: "service_pro",
  [ROLES.SUPPORT_ARCHITECT]: "support_architect",
  [ROLES.QA_INSPECTOR]: "qa_inspector",
  [ROLES.FISCAL_AUDITOR]: "fiscal_auditor",
};

/** Maps role values to their dashboard base paths. */
export const ROLE_DASHBOARD_PATHS: Record<RoleValue, string> = {
  [ROLES.RESIDENT]: "/resident",
  [ROLES.SERVICE_PRO]: "/service-pro",
  [ROLES.AGENCY_OWNER]: "/agency-owner",
  [ROLES.QA_INSPECTOR]: "/qa-inspector",
  [ROLES.SUPPORT_ARCHITECT]: "/support-architect",
  [ROLES.PLATFORM_ADMIN]: "/platform-admin",
  [ROLES.FISCAL_AUDITOR]: "/fiscal-auditor",
};

export interface JWTPayload {
  user_id: number;
  email: string;
  role: RoleValue;
  role_slug: string;
  full_name: string;
  company_id?: number;
  exp: number;
  iat: number;
  jti: string;
  token_type: string;
}

export interface TokenPair {
  access: string;
  refresh: string;
}

export interface UserProfile {
  id: number;
  uuid: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  role: RoleValue;
  role_display: string;
  is_verified: boolean;
  company: number | null;
  image_small: string | null;
  image_xsmall: string | null;
  date_joined: string;
}

export interface AuthResponse {
  user: UserProfile;
  tokens: TokenPair;
}

export interface RegisterPayload {
  email: string;
  password: string;
  password_confirm: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  role?: RoleValue;
}

export interface LoginPayload {
  email: string;
  password: string;
}
