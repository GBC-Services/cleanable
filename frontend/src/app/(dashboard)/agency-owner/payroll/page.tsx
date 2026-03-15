/**
 * Agency Owner — Payroll & Tax Documents
 * ========================================
 *
 * Tabbed view: Activity Statements, Payroll Cycles, and Tax Documents
 * scoped to the authenticated agency owner's company.
 */

"use client";

import { useState } from "react";
import {
  Banknote,
  Receipt,
  FileText,
} from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import ActivityStatementTable from "@/components/payroll/ActivityStatementTable";
import PayrollCycleView from "@/components/payroll/PayrollCycleView";
import TaxDocumentManager from "@/components/payroll/TaxDocumentManager";

type Tab = "statements" | "cycles" | "tax-docs";

export default function AgencyOwnerPayrollPage() {
  const { user } = useAuthStore();
  const agencyId = user?.company ?? undefined;
  const [activeTab, setActiveTab] = useState<Tab>("statements");

  const tabs: { id: Tab; label: string; icon: typeof Banknote }[] = [
    { id: "statements", label: "Activity Statements", icon: Receipt },
    { id: "cycles", label: "Payroll Cycles", icon: Banknote },
    { id: "tax-docs", label: "Tax Documents", icon: FileText },
  ];

  return (
    <div className="space-y-6 p-4 sm:p-6">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div>
        <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
          <Banknote className="h-6 w-6 text-brand-500" />
          Payroll & Compliance
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Activity statements, payroll history, and tax document management
        </p>
      </div>

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
      {activeTab === "statements" && (
        <ActivityStatementTable
          agencyId={agencyId}
          showAgencyColumn={false}
        />
      )}
      {activeTab === "cycles" && <PayrollCycleView agencyId={agencyId} />}
      {activeTab === "tax-docs" && <TaxDocumentManager agencyId={agencyId} />}
    </div>
  );
}
