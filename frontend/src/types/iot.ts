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

// ── GPS Tracking & Geofencing Types ─────────────────────────────────

export type ServiceProLocationStatus =
  | "en_route"
  | "arrived"
  | "in_progress"
  | "completed";

export interface ServiceProLocation {
  uuid: string;
  latitude: number;
  longitude: number;
  accuracy_meters: number | null;
  heading: number | null;
  speed_mps: number | null;
  eta_minutes: number | null;
  status: ServiceProLocationStatus;
  is_within_geofence: boolean;
  distance_to_property_meters: number | null;
  last_updated_at: string;
  service_pro_name: string;
}

export interface PropertyGeofence {
  uuid: string;
  latitude: number;
  longitude: number;
  radius_meters: number;
  geocoded_address: string;
  is_active: boolean;
  created_at: string;
}

export type GeofenceEventType =
  | "enter"
  | "exit"
  | "auto_unlock"
  | "auto_unlock_failed";

export interface GeofenceEvent {
  uuid: string;
  event_type: GeofenceEventType;
  event_display: string;
  latitude: number;
  longitude: number;
  distance_meters: number;
  metadata: Record<string, unknown>;
  created_at: string;
}

// ── WebSocket Message Types ──────────────────────────────────────────

export interface WSLocationUpdate {
  type: "location_update";
  latitude: number;
  longitude: number;
  accuracy: number | null;
  heading: number | null;
  speed: number | null;
  eta_minutes: number | null;
  status: ServiceProLocationStatus;
  distance_to_property: number | null;
  is_within_geofence: boolean;
  geofence_event: GeofenceEventType | null;
  timestamp: string;
}

export interface WSGeofenceEvent {
  type: "geofence_event";
  event: string;
  distance_meters: number;
  device_name: string;
  timestamp: string;
}

export interface WSStatusUpdate {
  type: "status_update";
  status: ServiceProLocationStatus;
  timestamp: string;
}

export type WSTrackingMessage =
  | WSLocationUpdate
  | WSGeofenceEvent
  | WSStatusUpdate
  | { type: "connected"; booking_uuid: string; message: string }
  | { type: "error"; message: string };

// ── Predictive Recommendations ──────────────────────────────────────

export type RecommendationType =
  | "deep_clean"
  | "regular"
  | "seasonal"
  | "weather_triggered"
  | "frequency_adjustment";

export interface PredictiveRecommendation {
  type: RecommendationType;
  title: string;
  description: string;
  suggested_date: string;
  confidence: number;
  reasoning: string;
  services: string[];
}

export interface WeatherData {
  current: {
    temp: number;
    humidity: number;
    weather: string;
    description: string;
  };
  forecast: Array<{
    date: string;
    temp_high: number;
    temp_low: number;
    weather: string;
    description: string;
    precipitation_chance: number;
  }>;
}

export interface RecommendationResponse {
  recommendations: PredictiveRecommendation[];
  weather_context: WeatherData;
  analysis_summary: string;
  generated_at: string;
}

export const RECOMMENDATION_TYPE_INFO: Record<
  RecommendationType,
  { label: string; color: string; icon: string }
> = {
  deep_clean: {
    label: "Deep Clean",
    color: "#3B82F6",
    icon: "sparkles",
  },
  regular: {
    label: "Regular Clean",
    color: "#10B981",
    icon: "calendar",
  },
  seasonal: {
    label: "Seasonal",
    color: "#F59E0B",
    icon: "sun",
  },
  weather_triggered: {
    label: "Weather Alert",
    color: "#EF4444",
    icon: "cloud-rain",
  },
  frequency_adjustment: {
    label: "Schedule Tip",
    color: "#8B5CF6",
    icon: "clock",
  },
};

// ── Ghost Mode & Fleet Management Types ──────────────────────────────

export interface GhostModeState {
  uuid: string;
  is_active: boolean;
  activated_at: string | null;
  deactivated_at: string | null;
  last_manual_checkin_at: string | null;
  last_manual_checkin_lat: number | null;
  last_manual_checkin_lng: number | null;
  service_pro_name: string;
  is_strict_tracking_enforced: boolean;
}

export interface StrictTrackingRule {
  uuid: string;
  service_pro: number;
  service_pro_name: string;
  service_pro_email: string;
  is_enforced: boolean;
  reason: string;
  created_at: string;
  updated_at: string;
}

export type GhostAlertResolution =
  | "pending"
  | "checked_in"
  | "dismissed"
  | "escalated";

export interface GhostModeAlert {
  uuid: string;
  service_pro: number;
  service_pro_name: string;
  booking: number | null;
  alert_type: "ghost_during_job" | "manual_checkin";
  alert_type_display: string;
  resolution: GhostAlertResolution;
  resolution_display: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
  resolved_at: string | null;
}

export interface FleetServicePro {
  id: number;
  email: string;
  full_name: string;
  ghost_mode_active: boolean;
  ghost_mode_since: string | null;
  strict_tracking_enforced: boolean;
  strict_tracking_reason: string;
  last_gps_lat: number | null;
  last_gps_lng: number | null;
  last_gps_time: string | null;
  pending_alerts_count: number;
}

export interface GPSHistoryEntry {
  id: number;
  service_pro: number;
  service_pro_name: string;
  booking: number | null;
  latitude: number;
  longitude: number;
  accuracy_meters: number | null;
  heading: number | null;
  speed_mps: number | null;
  ghost_mode_active: boolean;
  recorded_at: string;
}

export const GHOST_ALERT_RESOLUTION_INFO: Record<
  GhostAlertResolution,
  { label: string; color: string }
> = {
  pending: { label: "Pending", color: "#F59E0B" },
  checked_in: { label: "Checked In", color: "#10B981" },
  dismissed: { label: "Dismissed", color: "#6B7280" },
  escalated: { label: "Escalated", color: "#EF4444" },
};

export const LOCATION_STATUS_INFO: Record<
  ServiceProLocationStatus,
  { label: string; color: string; description: string }
> = {
  en_route: {
    label: "En Route",
    color: "#3B82F6",
    description: "Your cleaner is on the way.",
  },
  arrived: {
    label: "Arrived",
    color: "#10B981",
    description: "Your cleaner has arrived at the property.",
  },
  in_progress: {
    label: "In Progress",
    color: "#F59E0B",
    description: "Cleaning is in progress.",
  },
  completed: {
    label: "Completed",
    color: "#6B7280",
    description: "The cleaning session has ended.",
  },
};
