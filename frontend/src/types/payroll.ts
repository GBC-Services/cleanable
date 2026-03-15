/**
 * Payroll & Fiscal Auditing Types
 * ================================
 *
 * TypeScript interfaces matching the Django payroll models and API responses.
 */

// ── Activity Statement ──────────────────────────────────────────────

export interface ActivityStatement {
  uuid: string;
  cleaning: number;
  booking: number;
  booking_short_id: number | null;
  agency: number;
  agency_name: string;
  service_pro: number;
  service_pro_name: string;
  service_pro_email: string;
  client_charged: string;
  agency_fee: string;
  pro_wage: string;
  platform_fee: string;
  tip_amount: string;
  service_names: string;
  scheduled_date: string | null;
  completed_at: string | null;
  payroll_cycle: string | null;
  created: string;
}

// ── Payroll Cycle ───────────────────────────────────────────────────

export type PayrollCycleStatus = "open" | "processing" | "paid" | "held";

export interface PayrollCycleListItem {
  uuid: string;
  agency: number;
  agency_name: string;
  period_start: string;
  period_end: string;
  status: PayrollCycleStatus;
  total_jobs: number;
  total_client_charged: string;
  total_agency_fees: string;
  total_pro_wages: string;
  total_platform_fees: string;
  total_tips: string;
  stripe_transfer_id: string | null;
  paid_at: string | null;
  has_active_hold: boolean;
  line_item_count: number;
  created: string;
}

export interface PayrollCycleDetail extends PayrollCycleListItem {
  line_items: ActivityStatement[];
  holds: PaymentHold[];
  csv_file: string | null;
}

// ── Tax Document ────────────────────────────────────────────────────

export type TaxDocumentType = "w9" | "1099" | "other";
export type TaxDocumentStatus = "pending" | "approved" | "rejected";

export interface TaxDocument {
  uuid: string;
  agency: number;
  agency_name: string;
  uploaded_by: number;
  uploaded_by_name: string;
  document_type: TaxDocumentType;
  file: string;
  original_filename: string;
  tax_year: number;
  status: TaxDocumentStatus;
  reviewed_by: number | null;
  reviewed_by_name: string;
  reviewed_at: string | null;
  notes: string;
  created: string;
}

// ── Payment Hold ────────────────────────────────────────────────────

export type PaymentHoldStatus = "active" | "released" | "escalated";

export interface PaymentHold {
  uuid: string;
  payroll_cycle: string;
  placed_by: number;
  placed_by_name: string;
  reason: string;
  status: PaymentHoldStatus;
  released_by: number | null;
  released_by_name: string;
  released_at: string | null;
  release_notes: string;
  created: string;
}

// ── Dashboard Stats ─────────────────────────────────────────────────

export interface FiscalDashboardStats {
  open_cycles: number;
  processing_cycles: number;
  held_cycles: number;
  paid_this_month: string;
  active_holds: number;
  pending_tax_docs: number;
  statements_30d: number;
  revenue_30d: string;
  agency_fees_30d: string;
  pro_wages_30d: string;
  platform_fees_30d: string;
}

// ── Status display helpers ──────────────────────────────────────────

export const CYCLE_STATUS_INFO: Record<
  PayrollCycleStatus,
  { label: string; color: string; bgColor: string }
> = {
  open: { label: "Open", color: "text-blue-700", bgColor: "bg-blue-50" },
  processing: { label: "Processing", color: "text-amber-700", bgColor: "bg-amber-50" },
  paid: { label: "Paid", color: "text-green-700", bgColor: "bg-green-50" },
  held: { label: "Held", color: "text-red-700", bgColor: "bg-red-50" },
};

export const TAX_DOC_STATUS_INFO: Record<
  TaxDocumentStatus,
  { label: string; color: string; bgColor: string }
> = {
  pending: { label: "Pending Review", color: "text-amber-700", bgColor: "bg-amber-50" },
  approved: { label: "Approved", color: "text-green-700", bgColor: "bg-green-50" },
  rejected: { label: "Rejected", color: "text-red-700", bgColor: "bg-red-50" },
};

export const HOLD_STATUS_INFO: Record<
  PaymentHoldStatus,
  { label: string; color: string; bgColor: string }
> = {
  active: { label: "Active Hold", color: "text-red-700", bgColor: "bg-red-50" },
  released: { label: "Released", color: "text-green-700", bgColor: "bg-green-50" },
  escalated: { label: "Escalated", color: "text-orange-700", bgColor: "bg-orange-50" },
};

export const TAX_DOC_TYPE_LABELS: Record<TaxDocumentType, string> = {
  w9: "W-9",
  "1099": "1099",
  other: "Other",
};
