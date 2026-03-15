/**
 * Onboarding & Contracting Types
 * =================================
 *
 * TypeScript interfaces matching the Django onboarding models and API responses.
 */

// ── Fuzzy Match ─────────────────────────────────────────────────────

export interface AgencyMatchResult {
  agency_id: number;
  agency_name: string;
  match_score: number;
  uuid: string;
}

// ── Manager Approval Request ────────────────────────────────────────

export type ApprovalStatus = "pending" | "approved" | "rejected" | "expired";

export interface ManagerApprovalRequest {
  uuid: string;
  service_pro: number;
  service_pro_name: string;
  service_pro_email: string;
  agency: number;
  agency_name: string;
  typed_agency_name: string;
  match_score: number;
  status: ApprovalStatus;
  reviewed_by: number | null;
  reviewed_at: string | null;
  rejection_reason: string;
  expires_at: string;
  created_at: string;
}

export interface ApprovalAction {
  action: "approve" | "reject";
  rejection_reason?: string;
}

// ── WebSocket Messages ──────────────────────────────────────────────

export interface WSApprovalRequest {
  type: "approval_request";
  data: {
    uuid: string;
    service_pro_name: string;
    service_pro_email: string;
    typed_agency_name: string;
    match_score: number;
    created_at: string;
    expires_at: string;
  };
}

export interface WSApprovalResult {
  type: "approval_result";
  data: {
    uuid: string;
    agency_name: string;
    status: ApprovalStatus;
    rejection_reason: string;
  };
}

// ── Agency Service Area (Geofence) ──────────────────────────────────

export interface GeoJSONGeometry {
  type: "Polygon" | "MultiPolygon";
  coordinates: number[][][] | number[][][][];
}

export interface GeoJSONFeature {
  type: "Feature";
  geometry: GeoJSONGeometry;
  properties?: Record<string, unknown>;
}

export interface AgencyServiceArea {
  uuid: string;
  agency: number;
  name: string;
  geojson: GeoJSONFeature;
  color: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ServiceAreaFormData {
  name: string;
  geojson: GeoJSONFeature;
  color: string;
}

// ── Coverage Check ──────────────────────────────────────────────────

export interface CoverageCheckResult {
  covered: boolean;
  agencies: Array<{
    id: number;
    name: string;
    uuid: string;
  }>;
  location: {
    lng: number;
    lat: number;
  };
}

// ── Contracts ───────────────────────────────────────────────────────

export type ContractStatus =
  | "draft"
  | "pending_signatures"
  | "fully_signed"
  | "expired"
  | "revoked";

export interface ContractSignature {
  uuid: string;
  signer_role: "agency_owner" | "platform_admin";
  signer_full_name: string;
  signer_email: string;
  signature_hash: string;
  ip_address: string;
  is_valid: boolean;
  signed_at: string;
}

export interface AgencyContractListItem {
  uuid: string;
  agency: number;
  agency_name: string;
  version: number;
  status: ContractStatus;
  effective_date: string | null;
  expiry_date: string | null;
  created_at: string;
  signatures_count: number;
  required_signatures_count: number;
}

export interface AgencyContractDetail {
  uuid: string;
  agency: number;
  agency_name: string;
  version: number;
  status: ContractStatus;
  service_areas_snapshot: Array<{
    name: string;
    geojson: GeoJSONFeature;
    color: string;
  }>;
  pricing_snapshot: {
    snapshot_date: string;
    fees: Array<{
      service_name: string;
      client_fee: string;
      subcontractor_fee: string;
    }>;
  };
  terms_text: string;
  pdf_file: string | null;
  pdf_generated_at: string | null;
  document_hash: string;
  required_signers: Array<{
    role: string;
    user_id: number | null;
  }>;
  effective_date: string | null;
  expiry_date: string | null;
  created_at: string;
  updated_at: string;
  signatures: ContractSignature[];
}

export interface ContractSignInput {
  signer_full_name: string;
  signer_role: "agency_owner" | "platform_admin";
}

export interface GenerateContractInput {
  agency_id: number;
  expiry_months?: number;
}

// ── Status Helpers ──────────────────────────────────────────────────

export const APPROVAL_STATUS_INFO: Record<
  ApprovalStatus,
  { label: string; color: string; bgColor: string }
> = {
  pending: { label: "Pending", color: "text-amber-700", bgColor: "bg-amber-50" },
  approved: { label: "Approved", color: "text-green-700", bgColor: "bg-green-50" },
  rejected: { label: "Rejected", color: "text-red-700", bgColor: "bg-red-50" },
  expired: { label: "Expired", color: "text-gray-500", bgColor: "bg-gray-100" },
};

export const CONTRACT_STATUS_INFO: Record<
  ContractStatus,
  { label: string; color: string; bgColor: string }
> = {
  draft: { label: "Draft", color: "text-gray-600", bgColor: "bg-gray-100" },
  pending_signatures: { label: "Pending Signatures", color: "text-amber-700", bgColor: "bg-amber-50" },
  fully_signed: { label: "Fully Signed", color: "text-green-700", bgColor: "bg-green-50" },
  expired: { label: "Expired", color: "text-red-600", bgColor: "bg-red-50" },
  revoked: { label: "Revoked", color: "text-red-700", bgColor: "bg-red-100" },
};
