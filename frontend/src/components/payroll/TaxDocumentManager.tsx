/**
 * TaxDocumentManager — W-9 / 1099 Compliance Tab
 * =================================================
 *
 * Agency Owners upload compliance files.
 * Fiscal Auditors review (approve/reject) them.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  FileText,
  Upload,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Trash2,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import { ROLES } from "@/types/auth";
import type {
  TaxDocument,
  TaxDocumentType,
  TaxDocumentStatus,
} from "@/types/payroll";
import {
  TAX_DOC_STATUS_INFO,
  TAX_DOC_TYPE_LABELS,
} from "@/types/payroll";

interface Props {
  agencyId?: number;
}

export default function TaxDocumentManager({ agencyId }: Props) {
  const { user } = useAuthStore();
  const isAuditor =
    user?.role === ROLES.FISCAL_AUDITOR || user?.role === ROLES.PLATFORM_ADMIN;
  const isAgencyOwner = user?.role === ROLES.AGENCY_OWNER;

  const [docs, setDocs] = useState<TaxDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Upload form state
  const [showUpload, setShowUpload] = useState(false);
  const [docType, setDocType] = useState<TaxDocumentType>("w9");
  const [taxYear, setTaxYear] = useState(new Date().getFullYear());
  const [notes, setNotes] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const loadDocs = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (agencyId) params.set("agency", String(agencyId));
      const qs = params.toString();
      const data = await api.get<TaxDocument[]>(
        `/payroll/tax-documents/${qs ? `?${qs}` : ""}`
      );
      setDocs(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [agencyId]);

  useEffect(() => {
    loadDocs();
  }, [loadDocs]);

  // ── Upload ────────────────────────────────────────────────────────

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("document_type", docType);
      formData.append("tax_year", String(taxYear));
      formData.append("file", file);
      if (notes) formData.append("notes", notes);

      await api.postFormData("/payroll/tax-documents/", formData);
      setShowUpload(false);
      setNotes("");
      if (fileRef.current) fileRef.current.value = "";
      loadDocs();
    } catch (err: any) {
      setError(err?.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  // ── Review (Auditor) ──────────────────────────────────────────────

  const reviewDoc = async (uuid: string, reviewStatus: "approved" | "rejected") => {
    setActionLoading(uuid);
    try {
      await api.post(`/payroll/tax-documents/${uuid}/review/`, {
        status: reviewStatus,
      });
      loadDocs();
    } catch (err: any) {
      setError(err?.message || "Review failed");
    } finally {
      setActionLoading(null);
    }
  };

  // ── Delete ────────────────────────────────────────────────────────

  const deleteDoc = async (uuid: string) => {
    setActionLoading(uuid);
    try {
      await api.delete(`/payroll/tax-documents/${uuid}/`);
      setDocs((prev) => prev.filter((d) => d.uuid !== uuid));
    } catch (err: any) {
      setError(err?.message || "Delete failed");
    } finally {
      setActionLoading(null);
    }
  };

  // ── Status icon ───────────────────────────────────────────────────

  const StatusIcon = ({ s }: { s: TaxDocumentStatus }) => {
    if (s === "approved") return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    if (s === "rejected") return <XCircle className="h-4 w-4 text-red-500" />;
    return <Clock className="h-4 w-4 text-amber-500" />;
  };

  return (
    <div className="space-y-4">
      {/* ── Header ───────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <FileText className="h-5 w-5 text-brand-500" />
          Tax Documents
        </h3>
        {isAgencyOwner && (
          <button
            onClick={() => setShowUpload(!showUpload)}
            className="flex items-center gap-1 rounded-lg bg-brand-500 px-3 py-1.5
                       text-sm font-medium text-white hover:bg-brand-600"
          >
            <Upload className="h-3.5 w-3.5" />
            Upload
          </button>
        )}
      </div>

      {/* ── Upload form ──────────────────────────────────────────── */}
      {showUpload && (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Document Type
              </label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value as TaxDocumentType)}
                className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm"
              >
                <option value="w9">W-9</option>
                <option value="1099">1099</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Tax Year
              </label>
              <input
                type="number"
                value={taxYear}
                onChange={(e) => setTaxYear(Number(e.target.value))}
                min={2020}
                max={2099}
                className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                File
              </label>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"
                className="w-full text-sm file:mr-2 file:rounded file:border-0
                           file:bg-brand-50 file:px-3 file:py-1 file:text-sm
                           file:font-medium file:text-brand-700"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Notes (optional)
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="E.g., Updated W-9 for 2026"
              className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm"
            />
          </div>
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="flex items-center gap-1 rounded-lg bg-green-500 px-4 py-1.5
                       text-sm font-medium text-white hover:bg-green-600 disabled:opacity-50"
          >
            {uploading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Upload className="h-3.5 w-3.5" />
            )}
            Upload Document
          </button>
        </div>
      )}

      {/* ── Error ────────────────────────────────────────────────── */}
      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* ── Document list ────────────────────────────────────────── */}
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-brand-500" />
        </div>
      ) : docs.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center">
          <FileText className="mx-auto h-8 w-8 text-gray-300" />
          <p className="mt-2 text-sm text-gray-500">No tax documents.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {docs.map((doc) => {
            const info = TAX_DOC_STATUS_INFO[doc.status];
            return (
              <div
                key={doc.uuid}
                className="rounded-lg border border-gray-200 bg-white p-3 flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <StatusIcon s={doc.status} />
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {TAX_DOC_TYPE_LABELS[doc.document_type]} &mdash;{" "}
                      {doc.tax_year}
                    </p>
                    <p className="text-xs text-gray-500">
                      {doc.original_filename} &middot; Uploaded{" "}
                      {new Date(doc.created).toLocaleDateString()} by{" "}
                      {doc.uploaded_by_name}
                    </p>
                    {doc.notes && (
                      <p className="text-xs text-gray-400 mt-0.5">
                        {doc.notes}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${info.color} ${info.bgColor}`}
                  >
                    {info.label}
                  </span>

                  {isAuditor && doc.status === "pending" && (
                    <>
                      <button
                        onClick={() => reviewDoc(doc.uuid, "approved")}
                        disabled={actionLoading === doc.uuid}
                        className="rounded bg-green-500 px-2 py-1 text-xs font-medium text-white
                                   hover:bg-green-600 disabled:opacity-50"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => reviewDoc(doc.uuid, "rejected")}
                        disabled={actionLoading === doc.uuid}
                        className="rounded bg-red-500 px-2 py-1 text-xs font-medium text-white
                                   hover:bg-red-600 disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </>
                  )}

                  {(isAgencyOwner || isAuditor) && (
                    <button
                      onClick={() => deleteDoc(doc.uuid)}
                      disabled={actionLoading === doc.uuid}
                      className="rounded p-1 text-gray-400 hover:text-red-500"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
