/**
 * ActivityStatementTable — Per-Job Ledger
 * =========================================
 *
 * Displays activity statements with agency pricing cross-referenced against
 * Service Pro wages. Filterable by date range, agency, and service pro.
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Receipt,
  Loader2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Search,
  Calendar,
  DollarSign,
} from "lucide-react";
import { api } from "@/lib/api";
import type { ActivityStatement } from "@/types/payroll";

interface Props {
  agencyId?: number;
  showAgencyColumn?: boolean;
}

export default function ActivityStatementTable({
  agencyId,
  showAgencyColumn = true,
}: Props) {
  const [statements, setStatements] = useState<ActivityStatement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedUuid, setExpandedUuid] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const loadStatements = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (agencyId) params.set("agency", String(agencyId));
      if (dateFrom) params.set("from", dateFrom);
      if (dateTo) params.set("to", dateTo);
      const qs = params.toString();
      const data = await api.get<ActivityStatement[]>(
        `/payroll/statements/${qs ? `?${qs}` : ""}`
      );
      setStatements(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load statements");
    } finally {
      setLoading(false);
    }
  }, [agencyId, dateFrom, dateTo]);

  useEffect(() => {
    loadStatements();
  }, [loadStatements]);

  const fmtCurrency = (val: string) => {
    const n = parseFloat(val);
    return isNaN(n) ? "$0.00" : `$${n.toFixed(2)}`;
  };

  return (
    <div className="space-y-4">
      {/* ── Filters ──────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">
            From
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm
                       focus:border-brand-400 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">
            To
          </label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm
                       focus:border-brand-400 focus:outline-none"
          />
        </div>
        <button
          onClick={loadStatements}
          className="flex items-center gap-1 rounded-md bg-brand-500 px-3 py-1.5
                     text-sm font-medium text-white hover:bg-brand-600"
        >
          <Search className="h-3.5 w-3.5" />
          Filter
        </button>
      </div>

      {/* ── Error ────────────────────────────────────────────────── */}
      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* ── Loading ──────────────────────────────────────────────── */}
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-brand-500" />
        </div>
      ) : statements.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center">
          <Receipt className="mx-auto h-8 w-8 text-gray-300" />
          <p className="mt-2 text-sm text-gray-500">
            No activity statements found.
          </p>
        </div>
      ) : (
        /* ── Table ──────────────────────────────────────────────── */
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-600">
                  Date
                </th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">
                  Booking
                </th>
                {showAgencyColumn && (
                  <th className="px-3 py-2 text-left font-medium text-gray-600">
                    Agency
                  </th>
                )}
                <th className="px-3 py-2 text-left font-medium text-gray-600">
                  Service Pro
                </th>
                <th className="px-3 py-2 text-right font-medium text-gray-600">
                  Client Charged
                </th>
                <th className="px-3 py-2 text-right font-medium text-gray-600">
                  Agency Fee
                </th>
                <th className="px-3 py-2 text-right font-medium text-gray-600">
                  Pro Wage
                </th>
                <th className="px-3 py-2 text-right font-medium text-gray-600">
                  Platform
                </th>
                <th className="px-3 py-2 w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {statements.map((s) => (
                <>
                  <tr
                    key={s.uuid}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() =>
                      setExpandedUuid(expandedUuid === s.uuid ? null : s.uuid)
                    }
                  >
                    <td className="px-3 py-2 text-gray-700 whitespace-nowrap">
                      {s.scheduled_date || "—"}
                    </td>
                    <td className="px-3 py-2 text-gray-700">
                      #{s.booking_short_id}
                    </td>
                    {showAgencyColumn && (
                      <td className="px-3 py-2 text-gray-700">
                        {s.agency_name}
                      </td>
                    )}
                    <td className="px-3 py-2 text-gray-700">
                      {s.service_pro_name}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-gray-800">
                      {fmtCurrency(s.client_charged)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-gray-800">
                      {fmtCurrency(s.agency_fee)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-gray-800">
                      {fmtCurrency(s.pro_wage)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-emerald-600">
                      {fmtCurrency(s.platform_fee)}
                    </td>
                    <td className="px-3 py-2">
                      {expandedUuid === s.uuid ? (
                        <ChevronUp className="h-4 w-4 text-gray-400" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-gray-400" />
                      )}
                    </td>
                  </tr>
                  {expandedUuid === s.uuid && (
                    <tr key={`${s.uuid}-detail`}>
                      <td
                        colSpan={showAgencyColumn ? 9 : 8}
                        className="bg-gray-50 px-4 py-3"
                      >
                        <div className="grid grid-cols-2 gap-4 text-xs text-gray-600 md:grid-cols-4">
                          <div>
                            <span className="font-medium">Services:</span>{" "}
                            {s.service_names || "N/A"}
                          </div>
                          <div>
                            <span className="font-medium">Tip:</span>{" "}
                            {fmtCurrency(s.tip_amount)}
                          </div>
                          <div>
                            <span className="font-medium">Completed:</span>{" "}
                            {s.completed_at
                              ? new Date(s.completed_at).toLocaleString()
                              : "—"}
                          </div>
                          <div>
                            <span className="font-medium">Pro Email:</span>{" "}
                            {s.service_pro_email}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
