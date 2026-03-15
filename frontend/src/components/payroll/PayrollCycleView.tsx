/**
 * PayrollCycleView — Payroll Cycle List + Detail Panel
 * =====================================================
 *
 * Shows all payroll cycles. Fiscal Auditors can close cycles, trigger
 * payouts, place holds, and download CSVs.
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Banknote,
  Loader2,
  AlertTriangle,
  Download,
  CreditCard,
  Lock,
  FileSpreadsheet,
  ChevronRight,
  ArrowLeft,
  ShieldAlert,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import { ROLES } from "@/types/auth";
import type {
  PayrollCycleListItem,
  PayrollCycleDetail,
  PayrollCycleStatus,
} from "@/types/payroll";
import { CYCLE_STATUS_INFO } from "@/types/payroll";
import PaymentHoldControls from "./PaymentHoldControls";

interface Props {
  agencyId?: number;
}

export default function PayrollCycleView({ agencyId }: Props) {
  const { user } = useAuthStore();
  const isAuditor = user?.role === ROLES.FISCAL_AUDITOR;
  const isAdmin = user?.role === ROLES.PLATFORM_ADMIN;
  const canManage = isAuditor || isAdmin;

  const [cycles, setCycles] = useState<PayrollCycleListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Detail view
  const [selectedUuid, setSelectedUuid] = useState<string | null>(null);
  const [detail, setDetail] = useState<PayrollCycleDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Status filter
  const [statusFilter, setStatusFilter] = useState<PayrollCycleStatus | "">("");

  const loadCycles = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (agencyId) params.set("agency", String(agencyId));
      if (statusFilter) params.set("status", statusFilter);
      const qs = params.toString();
      const data = await api.get<PayrollCycleListItem[]>(
        `/payroll/cycles/${qs ? `?${qs}` : ""}`
      );
      setCycles(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load cycles");
    } finally {
      setLoading(false);
    }
  }, [agencyId, statusFilter]);

  useEffect(() => {
    loadCycles();
  }, [loadCycles]);

  // ── Load detail ───────────────────────────────────────────────────

  const openDetail = async (uuid: string) => {
    setSelectedUuid(uuid);
    setDetailLoading(true);
    try {
      const data = await api.get<PayrollCycleDetail>(
        `/payroll/cycles/${uuid}/`
      );
      setDetail(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load cycle detail");
    } finally {
      setDetailLoading(false);
    }
  };

  // ── Actions ───────────────────────────────────────────────────────

  const closeCycle = async (uuid: string) => {
    setActionLoading(uuid);
    try {
      await api.post(`/payroll/cycles/${uuid}/close/`, {});
      loadCycles();
      if (selectedUuid === uuid) openDetail(uuid);
    } catch (err: any) {
      setError(err?.message || "Close failed");
    } finally {
      setActionLoading(null);
    }
  };

  const triggerPayout = async (uuid: string) => {
    setActionLoading(uuid);
    try {
      await api.post(`/payroll/cycles/${uuid}/payout/`, {});
      loadCycles();
      if (selectedUuid === uuid) openDetail(uuid);
    } catch (err: any) {
      setError(err?.message || "Payout failed");
    } finally {
      setActionLoading(null);
    }
  };

  const fmtCurrency = (val: string) => {
    const n = parseFloat(val);
    return isNaN(n) ? "$0.00" : `$${n.toLocaleString("en-US", { minimumFractionDigits: 2 })}`;
  };

  // ── Detail view ───────────────────────────────────────────────────

  if (selectedUuid) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => {
            setSelectedUuid(null);
            setDetail(null);
          }}
          className="flex items-center gap-1 text-sm text-brand-600 hover:text-brand-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Cycles
        </button>

        {detailLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-brand-500" />
          </div>
        ) : detail ? (
          <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  {detail.agency_name} — Payroll Cycle
                </h3>
                <p className="text-sm text-gray-500">
                  {detail.period_start} to {detail.period_end}
                </p>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-sm font-medium ${
                  CYCLE_STATUS_INFO[detail.status].color
                } ${CYCLE_STATUS_INFO[detail.status].bgColor}`}
              >
                {CYCLE_STATUS_INFO[detail.status].label}
              </span>
            </div>

            {/* KPI row */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              {[
                { label: "Jobs", value: String(detail.total_jobs) },
                { label: "Client Charged", value: fmtCurrency(detail.total_client_charged) },
                { label: "Agency Fees", value: fmtCurrency(detail.total_agency_fees) },
                { label: "Pro Wages", value: fmtCurrency(detail.total_pro_wages) },
                { label: "Platform", value: fmtCurrency(detail.total_platform_fees) },
              ].map((kpi) => (
                <div
                  key={kpi.label}
                  className="rounded-lg border border-gray-200 bg-white p-3 text-center"
                >
                  <p className="text-xs text-gray-500">{kpi.label}</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {kpi.value}
                  </p>
                </div>
              ))}
            </div>

            {/* Action buttons */}
            {canManage && (
              <div className="flex flex-wrap gap-2">
                {detail.status === "open" && (
                  <button
                    onClick={() => closeCycle(detail.uuid)}
                    disabled={actionLoading === detail.uuid}
                    className="flex items-center gap-1 rounded-lg bg-amber-500 px-4 py-2
                               text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50"
                  >
                    <FileSpreadsheet className="h-4 w-4" />
                    Close Cycle & Generate CSV
                  </button>
                )}
                {detail.status === "processing" && !detail.has_active_hold && (
                  <button
                    onClick={() => triggerPayout(detail.uuid)}
                    disabled={actionLoading === detail.uuid}
                    className="flex items-center gap-1 rounded-lg bg-green-500 px-4 py-2
                               text-sm font-medium text-white hover:bg-green-600 disabled:opacity-50"
                  >
                    <CreditCard className="h-4 w-4" />
                    Trigger Stripe Payout
                  </button>
                )}
                {detail.csv_file && (
                  <a
                    href={`/api/v1/payroll/cycles/${detail.uuid}/csv/`}
                    className="flex items-center gap-1 rounded-lg border border-gray-300
                               bg-white px-4 py-2 text-sm font-medium text-gray-700
                               hover:bg-gray-50"
                  >
                    <Download className="h-4 w-4" />
                    Download CSV
                  </a>
                )}
              </div>
            )}

            {/* Stripe info */}
            {detail.stripe_transfer_id && (
              <div className="rounded-lg bg-green-50 p-3 text-sm text-green-700">
                Paid via Stripe Transfer: {detail.stripe_transfer_id}{" "}
                {detail.paid_at && `on ${new Date(detail.paid_at).toLocaleString()}`}
              </div>
            )}

            {/* Payment Holds section */}
            {canManage && (
              <PaymentHoldControls
                cycleUuid={detail.uuid}
                cycleStatus={detail.status}
                holds={detail.holds}
                onUpdate={() => openDetail(detail.uuid)}
              />
            )}

            {/* Line items */}
            {detail.line_items.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">
                  Activity Statements ({detail.line_items.length})
                </h4>
                <div className="overflow-x-auto rounded-lg border border-gray-200">
                  <table className="min-w-full divide-y divide-gray-200 text-xs">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Date</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Booking</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Service Pro</th>
                        <th className="px-3 py-2 text-right font-medium text-gray-600">Agency Fee</th>
                        <th className="px-3 py-2 text-right font-medium text-gray-600">Pro Wage</th>
                        <th className="px-3 py-2 text-right font-medium text-gray-600">Platform</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 bg-white">
                      {detail.line_items.map((item) => (
                        <tr key={item.uuid}>
                          <td className="px-3 py-2 text-gray-700">
                            {item.scheduled_date || "—"}
                          </td>
                          <td className="px-3 py-2 text-gray-700">
                            #{item.booking_short_id}
                          </td>
                          <td className="px-3 py-2 text-gray-700">
                            {item.service_pro_name}
                          </td>
                          <td className="px-3 py-2 text-right font-mono">
                            {fmtCurrency(item.agency_fee)}
                          </td>
                          <td className="px-3 py-2 text-right font-mono">
                            {fmtCurrency(item.pro_wage)}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-emerald-600">
                            {fmtCurrency(item.platform_fee)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    );
  }

  // ── List view ─────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as PayrollCycleStatus | "")}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm"
        >
          <option value="">All Statuses</option>
          <option value="open">Open</option>
          <option value="processing">Processing</option>
          <option value="held">Held</option>
          <option value="paid">Paid</option>
        </select>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-brand-500" />
        </div>
      ) : cycles.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center">
          <Banknote className="mx-auto h-8 w-8 text-gray-300" />
          <p className="mt-2 text-sm text-gray-500">No payroll cycles found.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {cycles.map((c) => {
            const info = CYCLE_STATUS_INFO[c.status];
            return (
              <div
                key={c.uuid}
                onClick={() => openDetail(c.uuid)}
                className="flex items-center justify-between rounded-lg border
                           border-gray-200 bg-white p-4 cursor-pointer hover:bg-gray-50
                           transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div>
                    <p className="text-sm font-semibold text-gray-900">
                      {c.agency_name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {c.period_start} — {c.period_end} &middot;{" "}
                      {c.total_jobs} jobs
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-mono font-semibold text-gray-800">
                    {fmtCurrency(c.total_agency_fees)}
                  </span>
                  {c.has_active_hold && (
                    <ShieldAlert className="h-4 w-4 text-red-500" />
                  )}
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${info.color} ${info.bgColor}`}
                  >
                    {info.label}
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-400" />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
