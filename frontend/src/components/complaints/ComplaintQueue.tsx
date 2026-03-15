"use client";

/**
 * Complaint Queue
 * ================
 *
 * Filterable list of complaints with real-time escalation indicators.
 * Used in the Support Architect dashboard.
 */

import {
  AlertTriangle,
  UserX,
  ShieldAlert,
  Clock,
  Inbox,
  Loader2,
  ArrowUp,
  CheckCircle2,
  Filter,
} from "lucide-react";
import type {
  Complaint,
  ComplaintScenario,
  ComplaintStatus,
  ComplaintUrgency,
  COMPLAINT_STATUS_INFO,
  URGENCY_INFO,
} from "@/types/complaints";

const STATUS_MAP: Record<ComplaintStatus, { label: string; color: string; bg: string }> = {
  open: { label: "Open", color: "text-red-700", bg: "bg-red-50" },
  acknowledged: { label: "Acknowledged", color: "text-amber-700", bg: "bg-amber-50" },
  investigating: { label: "Investigating", color: "text-blue-700", bg: "bg-blue-50" },
  resolved: { label: "Resolved", color: "text-green-700", bg: "bg-green-50" },
  closed: { label: "Closed", color: "text-slate-500", bg: "bg-slate-100" },
};

const URGENCY_MAP: Record<ComplaintUrgency, { label: string; color: string; bg: string }> = {
  10: { label: "Low", color: "text-slate-500", bg: "bg-slate-100" },
  20: { label: "Medium", color: "text-blue-700", bg: "bg-blue-50" },
  30: { label: "High", color: "text-amber-700", bg: "bg-amber-50" },
  40: { label: "Critical", color: "text-red-700", bg: "bg-red-50" },
};

const SCENARIO_ICONS: Record<ComplaintScenario, typeof AlertTriangle> = {
  incomplete_clean: AlertTriangle,
  no_show: UserX,
  damage_reported: ShieldAlert,
  late_arrival: Clock,
};

const SCENARIO_COLORS: Record<ComplaintScenario, string> = {
  incomplete_clean: "text-amber-500",
  no_show: "text-red-500",
  damage_reported: "text-red-600",
  late_arrival: "text-indigo-500",
};

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

interface ComplaintQueueProps {
  complaints: Complaint[];
  loading: boolean;
  selectedId: number | null;
  filterStatus: string;
  filterScenario: string;
  onFilterStatusChange: (v: string) => void;
  onFilterScenarioChange: (v: string) => void;
  onSelect: (complaint: Complaint) => void;
}

export default function ComplaintQueue({
  complaints,
  loading,
  selectedId,
  filterStatus,
  filterScenario,
  onFilterStatusChange,
  onFilterScenarioChange,
  onSelect,
}: ComplaintQueueProps) {
  return (
    <div>
      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Filter className="h-4 w-4 text-slate-400" />
        <select
          data-testid="select-complaint-status"
          value={filterStatus}
          onChange={(e) => onFilterStatusChange(e.target.value)}
          className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
        >
          <option value="active">Active</option>
          <option value="all">All</option>
          <option value="open">Open</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="investigating">Investigating</option>
          <option value="resolved">Resolved</option>
        </select>
        <select
          data-testid="select-complaint-scenario"
          value={filterScenario}
          onChange={(e) => onFilterScenarioChange(e.target.value)}
          className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
        >
          <option value="all">All Scenarios</option>
          <option value="incomplete_clean">Incomplete Clean</option>
          <option value="no_show">No-Show</option>
          <option value="damage_reported">Damage Reported</option>
          <option value="late_arrival">Late Arrival</option>
        </select>
      </div>

      {/* List */}
      <div className="space-y-2">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-sm text-slate-400">
            <Loader2 className="h-4 w-4 animate-spin mr-2" /> Loading complaints...
          </div>
        ) : complaints.length === 0 ? (
          <div className="rounded-xl bg-white p-8 text-center shadow-sm ring-1 ring-slate-100">
            <Inbox className="mx-auto h-8 w-8 text-slate-300 mb-2" />
            <p className="text-sm text-slate-500">No complaints found.</p>
          </div>
        ) : (
          complaints.map((c) => {
            const ScenarioIcon = SCENARIO_ICONS[c.scenario] || AlertTriangle;
            const scenarioColor = SCENARIO_COLORS[c.scenario] || "text-slate-500";
            const statusInfo = STATUS_MAP[c.status];
            const urgencyInfo = URGENCY_MAP[c.urgency];

            return (
              <button
                key={c.id}
                data-testid={`complaint-row-${c.id}`}
                onClick={() => onSelect(c)}
                className={`w-full text-left rounded-xl bg-white p-4 shadow-sm ring-1 transition hover:ring-indigo-200 ${
                  selectedId === c.id
                    ? "ring-indigo-300 bg-indigo-50/30"
                    : "ring-slate-100"
                }`}
              >
                <div className="flex items-start justify-between mb-1.5">
                  <div className="flex items-center gap-2 min-w-0">
                    <ScenarioIcon className={`h-4 w-4 shrink-0 ${scenarioColor}`} />
                    <span className="text-sm font-semibold text-slate-800 truncate">
                      {c.scenario_display}
                    </span>
                    {c.urgency >= 30 && (
                      <ArrowUp
                        className={`h-3.5 w-3.5 shrink-0 ${
                          c.urgency === 40 ? "text-red-500" : "text-amber-500"
                        }`}
                      />
                    )}
                  </div>
                  <span className="text-xs text-slate-400 shrink-0 ml-2">
                    {timeAgo(c.escalated_at || c.created)}
                  </span>
                </div>

                <p className="text-xs text-slate-500 line-clamp-2 mb-2">
                  {c.description}
                </p>

                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${statusInfo?.bg} ${statusInfo?.color}`}
                  >
                    {statusInfo?.label}
                  </span>
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${urgencyInfo?.bg} ${urgencyInfo?.color}`}
                  >
                    {urgencyInfo?.label}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    Booking #{c.booking_short_id}
                  </span>
                  {c.company_name && (
                    <span className="text-[10px] text-slate-400">
                      {c.company_name}
                    </span>
                  )}
                  {c.actions_count > 0 && (
                    <span className="inline-flex items-center gap-0.5 text-[10px] text-green-600">
                      <CheckCircle2 className="h-2.5 w-2.5" />
                      {c.actions_count} action{c.actions_count > 1 ? "s" : ""}
                    </span>
                  )}
                  <span className="text-[10px] text-slate-400 ml-auto">
                    {c.resident_name}
                  </span>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
