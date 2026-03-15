/**
 * Support & QA Types
 * ===================
 *
 * TypeScript interfaces for the AI-driven support triage pipeline,
 * post-job spatial verification (QA), privacy detection, and GDPR purge.
 */

// ── Ticket Status ────────────────────────────────────────────────────

export type TicketStatus = 10 | 20 | 30 | 40 | 50;

export const TICKET_STATUS = {
  NEW: 10 as const,
  IN_WORK: 20 as const,
  RESOLVED: 30 as const,
  CANCELLED: 40 as const,
  ESCALATED: 50 as const,
};

export const TICKET_STATUS_INFO: Record<
  TicketStatus,
  { label: string; color: string; bgColor: string }
> = {
  10: { label: "New", color: "#3B82F6", bgColor: "#EFF6FF" },
  20: { label: "In Work", color: "#F59E0B", bgColor: "#FFFBEB" },
  30: { label: "Resolved", color: "#10B981", bgColor: "#ECFDF5" },
  40: { label: "Cancelled", color: "#6B7280", bgColor: "#F9FAFB" },
  50: { label: "Escalated", color: "#EF4444", bgColor: "#FEF2F2" },
};

// ── Ticket Priority ──────────────────────────────────────────────────

export type TicketPriority = 10 | 20 | 30 | 40;

export const TICKET_PRIORITY = {
  LOW: 10 as const,
  MEDIUM: 20 as const,
  HIGH: 30 as const,
  URGENT: 40 as const,
};

export const TICKET_PRIORITY_INFO: Record<
  TicketPriority,
  { label: string; color: string; bgColor: string; icon: string }
> = {
  10: { label: "Low", color: "#6B7280", bgColor: "#F9FAFB", icon: "minus" },
  20: {
    label: "Medium",
    color: "#3B82F6",
    bgColor: "#EFF6FF",
    icon: "equal",
  },
  30: {
    label: "High",
    color: "#F59E0B",
    bgColor: "#FFFBEB",
    icon: "arrow-up",
  },
  40: {
    label: "Urgent",
    color: "#EF4444",
    bgColor: "#FEF2F2",
    icon: "alert-triangle",
  },
};

// ── Sentiment ────────────────────────────────────────────────────────

export type TicketSentiment = "positive" | "negative" | "neutral";

export const SENTIMENT_INFO: Record<
  TicketSentiment,
  { label: string; color: string; bgColor: string; icon: string }
> = {
  positive: {
    label: "Positive",
    color: "#10B981",
    bgColor: "#ECFDF5",
    icon: "smile",
  },
  negative: {
    label: "Negative",
    color: "#EF4444",
    bgColor: "#FEF2F2",
    icon: "frown",
  },
  neutral: {
    label: "Neutral",
    color: "#6B7280",
    bgColor: "#F9FAFB",
    icon: "meh",
  },
};

// ── AI Category ──────────────────────────────────────────────────────

export type AICategory =
  | "billing"
  | "scheduling"
  | "quality"
  | "access"
  | "cancellation"
  | "technical"
  | "feedback"
  | "other";

export const AI_CATEGORY_INFO: Record<
  AICategory,
  { label: string; color: string; icon: string }
> = {
  billing: { label: "Billing", color: "#8B5CF6", icon: "credit-card" },
  scheduling: { label: "Scheduling", color: "#3B82F6", icon: "calendar" },
  quality: { label: "Quality", color: "#F59E0B", icon: "star" },
  access: { label: "Access", color: "#EF4444", icon: "key" },
  cancellation: { label: "Cancellation", color: "#6B7280", icon: "x-circle" },
  technical: { label: "Technical", color: "#0EA5E9", icon: "wrench" },
  feedback: { label: "Feedback", color: "#10B981", icon: "message-square" },
  other: { label: "Other", color: "#9CA3AF", icon: "help-circle" },
};

// ── Support Ticket ───────────────────────────────────────────────────

export interface TicketMessage {
  id: number;
  uuid: string;
  text: string;
  user: number;
  user_name: string;
  created: string;
  updated: string;
}

export interface TicketStatusChange {
  id: number;
  uuid: string;
  status: TicketStatus;
  status_display: string;
  user: number;
  user_name: string | null;
  created: string;
}

export interface SupportTicket {
  id: number;
  uuid: string;
  subject: string | null;
  text: string;
  status: TicketStatus;
  status_display: string;
  priority: TicketPriority;
  priority_display: string;
  sentiment: TicketSentiment | null;
  sentiment_score: number | null;
  ai_category: AICategory | null;
  ai_summary: string | null;
  ai_suggested_response?: string | null;
  ai_triaged_at: string | null;
  user: number;
  user_name: string;
  assigned_to: number | null;
  assigned_to_name: string | null;
  category: number | null;
  category_name: string | null;
  booking: number | null;
  resolution_notes?: string | null;
  resolved_at: string | null;
  comments?: string | null;
  messages?: TicketMessage[];
  status_changes?: TicketStatusChange[];
  created: string;
  updated: string;
}

// ── Ticket Stats (Dashboard) ─────────────────────────────────────────

export interface TicketStats {
  total: number;
  open: number;
  resolved_today: number;
  escalated: number;
  unassigned: number;
  priority_breakdown: {
    low: number;
    medium: number;
    high: number;
    urgent: number;
  };
  sentiment_breakdown: Record<string, number>;
  category_breakdown: Record<string, number>;
  avg_sentiment_score: number | null;
}

// ── Ticket Create / Update Payloads ──────────────────────────────────

export interface TicketCreatePayload {
  subject: string;
  text: string;
  category?: number | null;
  booking?: number | null;
}

export interface TicketUpdatePayload {
  status?: TicketStatus;
  priority?: TicketPriority;
  assigned_to?: number | null;
  comments?: string;
  resolution_notes?: string;
}

export interface TicketResolvePayload {
  resolution_notes?: string;
}

export interface TicketMessagePayload {
  text: string;
}

// ── Job Verification ─────────────────────────────────────────────────

export type VerificationStatus = 10 | 20 | 30 | 40 | 50 | 60;

export const VERIFICATION_STATUS = {
  PENDING: 10 as const,
  ANALYZING: 20 as const,
  APPROVED: 30 as const,
  FLAGGED: 40 as const,
  REJECTED: 50 as const,
  MANUAL_REVIEW: 60 as const,
};

export const VERIFICATION_STATUS_INFO: Record<
  VerificationStatus,
  { label: string; color: string; bgColor: string; icon: string }
> = {
  10: {
    label: "Pending",
    color: "#6B7280",
    bgColor: "#F9FAFB",
    icon: "clock",
  },
  20: {
    label: "Analyzing",
    color: "#3B82F6",
    bgColor: "#EFF6FF",
    icon: "loader",
  },
  30: {
    label: "Approved",
    color: "#10B981",
    bgColor: "#ECFDF5",
    icon: "check-circle",
  },
  40: {
    label: "Flagged",
    color: "#F59E0B",
    bgColor: "#FFFBEB",
    icon: "alert-triangle",
  },
  50: {
    label: "Rejected",
    color: "#EF4444",
    bgColor: "#FEF2F2",
    icon: "x-circle",
  },
  60: {
    label: "Manual Review",
    color: "#8B5CF6",
    bgColor: "#F5F3FF",
    icon: "eye",
  },
};

// ── Privacy Detection ────────────────────────────────────────────────

export interface BlurRegion {
  type: "face" | "photo" | "document";
  description: string;
  confidence: number;
}

export interface PrivacyDetection {
  has_faces: boolean;
  has_family_photos: boolean;
  has_sensitive_documents: boolean;
  detected_items: string[];
  privacy_risk_score: number;
  blur_regions: BlurRegion[];
}

// ── Job Verification (extended with privacy fields) ──────────────────

export interface JobVerification {
  id: number;
  uuid: string;
  booking: number;
  booking_uuid: string;
  service_pro: number;
  service_pro_name: string;
  media_type: "image" | "video";
  media_file: string;
  status: VerificationStatus;
  status_display: string;
  cleanliness_score: number | null;
  ai_summary: string | null;
  ai_analysis?: Record<string, unknown> | null;
  issues_detected: string[] | null;
  analyzed_at: string | null;
  privacy_metadata?: PrivacyDetection | null;
  privacy_scrubbed: boolean;
  ai_opt_out: boolean;
  r2_key?: string | null;
  reviewed_by: number | null;
  reviewer_notes: string | null;
  reviewed_at: string | null;
  created: string;
  updated: string;
}

export interface VerificationReviewPayload {
  status: 30 | 50; // APPROVED or REJECTED
  reviewer_notes?: string;
}

// ── GDPR Purge Media ─────────────────────────────────────────────────

export interface PurgeMediaPayload {
  resident_id: number;
  reason?: string;
}

export interface PurgeMediaResponse {
  detail: string;
  purged_count: number;
  purged_verification_ids: number[];
  resident_id: number;
  resident_email: string;
}
