/**
 * IoT & Smart Home Types
 * =======================
 *
 * TypeScript interfaces matching the Django IoT models and API responses.
 */

// ── Connected Device ────────────────────────────────────────────────

export type DeviceProvider = "august" | "yale" | "smartthings";
export type DeviceStatus = "active" | "disconnected" | "pending";

export interface ConnectedDevice {
  id: number;
  uuid: string;
  provider: DeviceProvider;
  provider_device_id?: string;
  device_name: string;
  device_model: string;
  status: DeviceStatus;
  smart_access_enabled: boolean;
  last_synced_at: string | null;
  token_expires_at?: string | null;
  is_token_expired?: boolean;
  metadata?: Record<string, unknown>;
  place: number | null;
  place_name: string | null;
  created_at: string;
  updated_at: string;
}

// ── Smart Lock Access Token ─────────────────────────────────────────

export type AccessTokenStatus = "active" | "used" | "expired" | "revoked";

export interface SmartLockAccessToken {
  id: number;
  uuid: string;
  device: number;
  device_name: string;
  device_provider: string;
  booking: number;
  service_pro: number;
  service_pro_name: string;
  valid_from: string;
  valid_until: string;
  status: AccessTokenStatus;
  is_valid: boolean;
  created_at: string;
}

// ── Voice Assistant Link ────────────────────────────────────────────

export type VoicePlatform = "alexa" | "siri" | "google";

export interface VoiceAssistantLink {
  id: number;
  uuid: string;
  platform: VoicePlatform;
  platform_display: string;
  is_active: boolean;
  linked_at: string;
  updated_at: string;
}

// ── API Request/Response Types ──────────────────────────────────────

export interface OAuthURLResponse {
  authorize_url: string;
  state: string;
  provider: string;
}

export interface DeviceCreatePayload {
  provider: DeviceProvider;
  code: string;
  redirect_uri: string;
  device_name?: string;
  place_id?: number | null;
}

export interface DeviceUpdatePayload {
  device_name?: string;
  smart_access_enabled?: boolean;
  place_id?: number | null;
}

export interface SmartAccessTogglePayload {
  enabled: boolean;
}

export interface VoiceLinkCreatePayload {
  platform: VoicePlatform;
  platform_user_id?: string;
}

export interface ProviderLock {
  device_id: string;
  name: string;
  model: string;
  status: string;
}

// ── Emergency Lockout Types ──────────────────────────────────────

export interface EmergencyLockoutPayload {
  place_id?: number | null;
  reason?: string;
}

export interface EmergencyLockoutResponse {
  detail: string;
  revoked_count: number;
  devices_locked: number;
  failed_provider_revocations: string[];
}

// ── Provider Metadata ───────────────────────────────────────────────

export const PROVIDER_INFO: Record<
  DeviceProvider,
  { name: string; icon: string; color: string }
> = {
  august: {
    name: "August",
    icon: "🔐",
    color: "#FF6B35",
  },
  yale: {
    name: "Yale",
    icon: "🔒",
    color: "#003B71",
  },
  smartthings: {
    name: "SmartThings",
    icon: "🏠",
    color: "#15BFFF",
  },
};

export const VOICE_PLATFORM_INFO: Record<
  VoicePlatform,
  { name: string; icon: string; color: string; description: string }
> = {
  alexa: {
    name: "Amazon Alexa",
    icon: "🔵",
    color: "#00CAFF",
    description: "Control bookings and locks with Alexa voice commands.",
  },
  siri: {
    name: "Apple Siri",
    icon: "🟣",
    color: "#A855F7",
    description: "Use Siri Shortcuts to manage bookings hands-free.",
  },
  google: {
    name: "Google Assistant",
    icon: "🔴",
    color: "#EA4335",
    description: "Coming soon — manage bookings via Google Assistant.",
  },
};
