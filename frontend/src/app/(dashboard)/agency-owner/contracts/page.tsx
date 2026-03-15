/**
 * Agency Owner — Contracts & Service Areas Page
 * ================================================
 *
 * Tabbed interface:
 *   1. Join Requests — Approve/reject Service Pro onboarding
 *   2. Service Areas — Mapbox geofence editor
 *   3. Contracts — Generate, sign, and download binding agreements
 */

"use client";

import { useState } from "react";
import { UserPlus, Layers, FileText } from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import ApprovalQueue from "@/components/onboarding/ApprovalQueue";
import GeofenceEditor from "@/components/onboarding/GeofenceEditor";
import ContractTab from "@/components/onboarding/ContractTab";

const TABS = [
  { id: "requests", label: "Join Requests", icon: UserPlus },
  { id: "areas", label: "Service Areas", icon: Layers },
  { id: "contracts", label: "Contracts", icon: FileText },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function AgencyContractsPage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState<TabId>("requests");

  const agencyId = (user as any)?.company_id || (user as any)?.company || 0;

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          Onboarding & Contracts
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Manage team join requests, define service coverage areas, and handle contracts.
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="mb-6 flex border-b border-gray-200">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition
                ${
                  isActive
                    ? "border-brand-500 text-brand-600"
                    : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
                }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      {activeTab === "requests" && <ApprovalQueue />}
      {activeTab === "areas" && <GeofenceEditor agencyId={agencyId} />}
      {activeTab === "contracts" && <ContractTab agencyId={agencyId} />}
    </div>
  );
}
