/**
 * Fiscal Auditor Dashboard
 * =========================
 *
 * Central command for payroll oversight. Shows KPIs, payroll cycles,
 * activity statements, tax document reviews, and payment hold controls.
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Banknote,
  Receipt,
  FileText,
  ShieldAlert,
  Loader2,
  DollarSign,
  TrendingUp,
  Clock,
  AlertTriangle,
  BarChart3,
} from "lucide-react";
import { api } from "@/lib/api";
import type { FiscalDashboardStats } from "@/types/payroll";
import ActivityStatementTable from "@/components/payroll/ActivityStatementTable";
import PayrollCycleView from "@/components/payroll/PayrollCycleView";
import TaxDocumentManager from "@/components/payroll/TaxDocumentManager";

type Tab = "cycles" | "statements" | "tax-docs";

export default function FiscalAuditorDashboard() {
  const [stats, setStats] = useState<FiscalDashboardStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>("cycles");

  const loadStats = useCallback(async () => {
    try {
      const data = await api.get<FiscalDashboardStats>("/payroll/stats/");
      setStats(data);
    } catch {
      // silently fail — stats are non-critical
    } finally {
      setStatsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const fmtCurrency = (val: string | undefined) => {
    if (!val) return "$0.00";
    const n = parseFloat(val);
    return isNaN(n)
      ? "$0.00"
      : `$${n.toLocaleString("en-US", { minimumFractionDigits: 2 })}`;
  };

  const tabs: { id: Tab; label: string; icon: typeof Banknote }[] = [
    { id: "cycles", label: "Payroll Cycles", icon: Banknote },
    { id: "statements", label: "Activity Statements", icon: Receipt },
    { id: "tax-docs", label: "Tax Documents", icon: FileText },
  ];

  return (
    <div className="space-y-6 p-4 sm:p-6">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div>
        <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
          <BarChart3 className="h-6 w-6 text-brand-500" />
          Fiscal Auditor Dashboard
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Payroll oversight, compliance review, and payout management
        </p>
      </div>

      {/* ── KPI cards ──────────────────────────────────────────────── */}
      {statsLoading ? (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="h-5 w-5 animate-spin text-brand-500" />
        </div>
      ) : stats ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <KPICard
            icon={<Clock className="h-4 w-4 text-blue-500" />}
            label="Open Cycles"
            value={String(stats.open_cycles)}
          />
          <KPICard
            icon={<TrendingUp className="h-4 w-4 text-amber-500" />}
            label="Processing"
            value={String(stats.processing_cycles)}
          />
          <KPICard
            icon={<ShieldAlert className="h-4 w-4 text-red-500" />}
            label="Held"
            value={String(stats.held_cycles)}
            highlight={stats.held_cycles > 0}
          />
          <KPICard
            icon={<DollarSign className="h-4 w-4 text-green-500" />}
            label="Paid (30d)"
            value={fmtCurrency(stats.paid_this_month)}
          />
          <KPICard
            icon={<AlertTriangle className="h-4 w-4 text-red-400" />}
            label="Active Holds"
            value={String(stats.active_holds)}
            highlight={stats.active_holds > 0}
          />
          <KPICard
            icon={<FileText className="h-4 w-4 text-amber-400" />}
            label="Pending Docs"
            value={String(stats.pending_tax_docs)}
            highlight={stats.pending_tax_docs > 0}
          />
        </div>
      ) : null}

      {/* ── 30-day revenue row ─────────────────────────────────────── */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MiniStat label="Revenue (30d)" value={fmtCurrency(stats.revenue_30d)} />
          <MiniStat
            label="Agency Fees (30d)"
            value={fmtCurrency(stats.agency_fees_30d)}
          />
          <MiniStat
            label="Pro Wages (30d)"
            value={fmtCurrency(stats.pro_wages_30d)}
          />
          <MiniStat
            label="Platform Margin (30d)"
            value={fmtCurrency(stats.platform_fees_30d)}
            accent
          />
        </div>
      )}

      {/* ── Tabs ───────────────────────────────────────────────────── */}
      <div className="border-b border-gray-200">
        <div className="flex gap-4 -mb-px">
          {tabs.map((tab) => {
            const active = activeTab === tab.id;
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 border-b-2 px-1 pb-2 text-sm font-medium
                  transition-colors ${
                    active
                      ? "border-brand-500 text-brand-600"
                      : "border-transparent text-gray-500 hover:text-gray-700"
                  }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Tab content ────────────────────────────────────────────── */}
      {activeTab === "cycles" && <PayrollCycleView />}
      {activeTab === "statements" && <ActivityStatementTable />}
      {activeTab === "tax-docs" && <TaxDocumentManager />}
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────

function KPICard({
  icon,
  label,
  value,
  highlight = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-3 ${
        highlight
          ? "border-red-200 bg-red-50"
          : "border-gray-200 bg-white"
      }`}
    >
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <p
        className={`text-lg font-bold ${
          highlight ? "text-red-700" : "text-gray-900"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function MiniStat({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-3 py-2">
      <p className="text-xs text-gray-500">{label}</p>
      <p
        className={`text-sm font-semibold font-mono ${
          accent ? "text-emerald-600" : "text-gray-800"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
