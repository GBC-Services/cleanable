/**
 * Complaint & Resolution Pipeline Types
 * =======================================
 *
 * TypeScript interfaces for the proactive support resolution system
 * with predefined Decision Array actions.
 */

// ── Complaint Scenarios ──────────────────────────────────────────────

export type ComplaintScenario =
  | "incomplete_clean"
  | "no_show"
  | "damage_reported"
  | "late_arrival";

export const COMPLAINT_SCENARIOS: Record<
  ComplaintScenario,
  { label: string; color: string; bgColor: string; icon: string }
> = {
  incomplete_clean: {
    label: "Incomplete Clean",
    color: "#F59E0B",
    bgColor: "#FFFBEB",
    icon: "alert-triangle",
  },
  no_show: {
    label: "No-Show",
    color: "#EF4444",
    bgColor: "#FEF2F2",
    icon: "user-x",
  },
  damage_reported: {
    label: "Damage Reported",
    color: "#DC2626",
    bgColor: "#FEE2E2",
    icon: "shield-alert",
  },
  late_arrival: {
    label: "Late Arrival",
    color: "#6366F1",
    bgColor: "#EEF2FF",
    icon: "clock",
  },
};

// ── Complaint Status ─────────────────────────────────────────────────

export type ComplaintStatus =
  | "open"
  | "acknowledged"
  | "investigating"
  | "resolved"
  | "closed";

export const COMPLAINT_STATUS_INFO: Record<
  ComplaintStatus,
  { label: string; color: string; bgColor: string }
> = {
  open: { label: "Open", color: "#EF4444", bgColor: "#FEF2F2" },
  acknowledged: { label: "Acknowledged", color: "#F59E0B", bgColor: "#FFFBEB" },
  investigating: { label: "Investigating", color: "#3B82F6", bgColor: "#EFF6FF" },
  resolved: { label: "Resolved", color: "#10B981", bgColor: "#ECFDF5" },
  closed: { label: "Closed", color: "#6B7280", bgColor: "#F9FAFB" },
};

// ── Urgency Levels ───────────────────────────────────────────────────

export type ComplaintUrgency = 10 | 20 | 30 | 40;

export const URGENCY_INFO: Record<
  ComplaintUrgency,
  { label: string; color: string; bgColor: string }
> = {
  10: { label: "Low", color: "#6B7280", bgColor: "#F9FAFB" },
  20: { label: "Medium", color: "#3B82F6", bgColor: "#EFF6FF" },
  30: { label: "High", color: "#F59E0B", bgColor: "#FFFBEB" },
  40: { label: "Critical", color: "#EF4444", bgColor: "#FEF2F2" },
};

// ── Resolution Action Types ──────────────────────────────────────────

export type ResolutionActionType =
  | "refund_partial"
  | "refund_full"
  | "schedule_redo"
  | "cancel_blacklist"
  | "note";

export const ACTION_TYPE_INFO: Record<
  ResolutionActionType,
  { label: string; color: string; bgColor: string; icon: string }
> = {
  refund_partial: {
    label: "Partial Refund",
    color: "#8B5CF6",
    bgColor: "#F5F3FF",
    icon: "dollar-sign",
  },
  refund_full: {
    label: "Full Refund",
    color: "#7C3AED",
    bgColor: "#EDE9FE",
    icon: "banknote",
  },
  schedule_redo: {
    label: "Schedule Re-do",
    color: "#0EA5E9",
    bgColor: "#F0F9FF",
    icon: "calendar-plus",
  },
  cancel_blacklist: {
    label: "Cancel & Blacklist",
    color: "#DC2626",
    bgColor: "#FEE2E2",
    icon: "ban",
  },
  note: {
    label: "Internal Note",
    color: "#6B7280",
    bgColor: "#F9FAFB",
    icon: "sticky-note",
  },
};

export type ExecutionStatus = "pending" | "processing" | "completed" | "failed";

export const EXEC_STATUS_INFO: Record<
  ExecutionStatus,
  { label: string; color: string }
> = {
  pending: { label: "Pending", color: "#6B7280" },
  processing: { label: "Processing", color: "#3B82F6" },
  completed: { label: "Completed", color: "#10B981" },
  failed: { label: "Failed", color: "#EF4444" },
};

// ── Notification Channel ─────────────────────────────────────────────

export type NotificationChannel = "sms" | "push" | "email" | "in_app";

export const CHANNEL_INFO: Record<
  NotificationChannel,
  { label: string; icon: string }
> = {
  sms: { label: "SMS", icon: "smartphone" },
  push: { label: "Push", icon: "bell" },
  email: { label: "Email", icon: "mail" },
  in_app: { label: "In-App", icon: "monitor" },
};

// ── Data Interfaces ──────────────────────────────────────────────────

export interface ComplaintNotification {
  id: number;
  uuid: string;
  channel: NotificationChannel;
  channel_display: string;
  status: string;
  status_display: string;
  recipient: number;
  recipient_name: string;
  message_body: string;
  sent_at: string | null;
  error_detail: string;
  created: string;
}

export interface ResolutionAction {
  id: number;
  uuid: string;
  action_type: ResolutionActionType;
  action_type_display: string;
  execution_status: ExecutionStatus;
  execution_status_display: string;
  performed_by: number;
  performed_by_name: string;
  notes: string;
  refund_amount: string | null;
  stripe_refund_id: string | null;
  redo_cleaning: number | null;
  redo_assigned_company: number | null;
  blacklisted_company: number | null;
  reassigned_bookings_count: number;
  executed_at: string | null;
  created: string;
  notifications?: ComplaintNotification[];
}

export interface Complaint {
  id: number;
  uuid: string;
  scenario: ComplaintScenario;
  scenario_display: string;
  status: ComplaintStatus;
  status_display: string;
  urgency: ComplaintUrgency;
  urgency_display: string;
  description: string;
  resident: number;
  resident_name: string;
  booking: number;
  booking_short_id: number;
  cleaning: number | null;
  company: number | null;
  company_name: string | null;
  assigned_to: number | null;
  assigned_to_name: string | null;
  escalated_at: string | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
  evidence_photos: string[] | null;
  actions_count: number;
  resolution_actions?: ResolutionAction[];
  notifications?: ComplaintNotification[];
  created: string;
  updated: string;
}

export interface ComplaintStats {
  total: number;
  open: number;
  unacknowledged: number;
  resolved_today: number;
  by_scenario: Record<string, number>;
  by_urgency: Record<string, number>;
  actions_today: number;
  active_blacklists: number;
}

// ── Payload Types ────────────────────────────────────────────────────

export interface ComplaintCreatePayload {
  booking: number;
  cleaning?: number | null;
  scenario: ComplaintScenario;
  description: string;
  evidence_photos?: string[] | null;
}

export interface RefundPayload {
  refund_type: "refund_partial" | "refund_full";
  amount?: number | null;
  notes?: string;
}

export interface ScheduleRedoPayload {
  use_different_agency?: boolean;
  preferred_company_id?: number | null;
  notes?: string;
}

export interface CancelBlacklistPayload {
  notes?: string;
}

export interface AgencyBlacklistEntry {
  id: number;
  uuid: string;
  resident: number;
  resident_name: string;
  company: number;
  company_name: string | null;
  complaint: number;
  reason: string;
  blacklisted_at: string;
  created: string;
}
