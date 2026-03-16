/**
 * Cybernetic Command Center types — platform integrations and
 * notification preference matrix.
 * Must match the Django governance models exactly.
 */

// ── PlatformIntegration ─────────────────────────────────────────────

export type IntegrationCategory = "proactive" | "voice" | "device";

export interface PlatformIntegration {
  id: string;
  slug: string;
  name: string;
  description: string;
  category: IntegrationCategory;
  icon: string;
  is_enabled: boolean;
  config: Record<string, unknown>;
  toggled_by: number | null;
  toggled_by_email: string;
  toggled_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlatformIntegrationListItem {
  id: string;
  slug: string;
  name: string;
  category: IntegrationCategory;
  icon: string;
  is_enabled: boolean;
  toggled_at: string | null;
}

export const INTEGRATION_CATEGORY_META: Record<
  IntegrationCategory,
  { label: string; icon: string; description: string }
> = {
  proactive: {
    label: "Proactive Intelligence",
    icon: "Brain",
    description: "AI-driven features that anticipate user needs",
  },
  voice: {
    label: "Voice Assistants",
    icon: "Mic",
    description: "Voice-activated booking and management hooks",
  },
  device: {
    label: "Device Access",
    icon: "Lock",
    description: "Smart home device API connections",
  },
};

// ── NotificationPreference ──────────────────────────────────────────

export interface NotificationPreference {
  id: string;
  event_slug: string;
  event_label: string;
  event_category: string;
  in_app: boolean;
  sms: boolean;
  email: boolean;
  created_at: string;
  updated_at: string;
}

export interface LifecycleEvent {
  slug: string;
  label: string;
  category: string;
}

export interface NotificationMatrixUpdate {
  event_slug: string;
  in_app?: boolean;
  sms?: boolean;
  email?: boolean;
}

export interface BulkUpdatePayload {
  preferences: NotificationMatrixUpdate[];
}

export interface BulkUpdateResponse {
  updated_count: number;
  preferences: NotificationPreference[];
}

// ── Event category display metadata ─────────────────────────────────

export const EVENT_CATEGORY_META: Record<
  string,
  { icon: string; color: string }
> = {
  Bookings: {
    icon: "Calendar",
    color: "text-blue-600 dark:text-blue-400",
  },
  Jobs: {
    icon: "Briefcase",
    color: "text-emerald-600 dark:text-emerald-400",
  },
  "Quality Assurance": {
    icon: "CheckCircle",
    color: "text-purple-600 dark:text-purple-400",
  },
  Payroll: {
    icon: "DollarSign",
    color: "text-green-600 dark:text-green-400",
  },
  Location: {
    icon: "MapPin",
    color: "text-orange-600 dark:text-orange-400",
  },
  "IoT & Devices": {
    icon: "Cpu",
    color: "text-pink-600 dark:text-pink-400",
  },
  Support: {
    icon: "HeadphonesIcon",
    color: "text-amber-600 dark:text-amber-400",
  },
  Security: {
    icon: "Shield",
    color: "text-red-600 dark:text-red-400",
  },
};
