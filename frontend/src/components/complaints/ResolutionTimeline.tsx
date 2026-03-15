"use client";

/**
 * Resolution Timeline
 * ====================
 *
 * Displays the audit trail of all resolution actions taken on a
 * complaint, with notification dispatch details.
 */

import {
  DollarSign,
  Banknote,
  CalendarPlus,
  Ban,
  StickyNote,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Smartphone,
  Bell,
  Mail,
  Monitor,
} from "lucide-react";
import type {
  ResolutionAction,
  ResolutionActionType,
  ExecutionStatus,
  ComplaintNotification,
  NotificationChannel,
} from "@/types/complaints";

const ACTION_ICONS: Record<ResolutionActionType, typeof DollarSign> = {
  refund_partial: DollarSign,
  refund_full: Banknote,
  schedule_redo: CalendarPlus,
  cancel_blacklist: Ban,
  note: StickyNote,
};

const ACTION_COLORS: Record<ResolutionActionType, string> = {
  refund_partial: "text-violet-500 bg-violet-50",
  refund_full: "text-violet-600 bg-violet-50",
  schedule_redo: "text-sky-500 bg-sky-50",
  cancel_blacklist: "text-red-500 bg-red-50",
  note: "text-slate-500 bg-slate-50",
};

const EXEC_ICONS: Record<ExecutionStatus, typeof CheckCircle2> = {
  completed: CheckCircle2,
  failed: XCircle,
  pending: Clock,
  processing: Loader2,
};

const CHANNEL_ICONS: Record<NotificationChannel, typeof Smartphone> = {
  sms: Smartphone,
  push: Bell,
  email: Mail,
  in_app: Monitor,
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

interface ResolutionTimelineProps {
  actions: ResolutionAction[];
}

export default function ResolutionTimeline({ actions }: ResolutionTimelineProps) {
  if (!actions || actions.length === 0) {
    return (
      <div className="rounded-lg bg-slate-50 p-4 text-center">
        <StickyNote className="mx-auto h-6 w-6 text-slate-300 mb-1" />
        <p className="text-xs text-slate-400">No resolution actions yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
        Resolution History
      </h4>
      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-4 top-0 bottom-0 w-px bg-slate-200" />

        <div className="space-y-4">
          {actions.map((action) => {
            const Icon = ACTION_ICONS[action.action_type] || StickyNote;
            const colorClasses = ACTION_COLORS[action.action_type] || "text-slate-500 bg-slate-50";
            const ExecIcon = EXEC_ICONS[action.execution_status] || Clock;

            return (
              <div key={action.id} className="relative pl-10">
                {/* Timeline dot */}
                <div
                  className={`absolute left-2 top-1 flex h-5 w-5 items-center justify-center rounded-full ${colorClasses}`}
                >
                  <Icon className="h-3 w-3" />
                </div>

                <div className="rounded-lg bg-white ring-1 ring-slate-100 p-3">
                  {/* Header */}
                  <div className="flex items-start justify-between mb-1">
                    <div>
                      <span className="text-xs font-bold text-slate-800">
                        {action.action_type_display}
                      </span>
                      <span className="text-[10px] text-slate-400 ml-2">
                        by {action.performed_by_name}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <ExecIcon
                        className={`h-3 w-3 ${
                          action.execution_status === "completed"
                            ? "text-green-500"
                            : action.execution_status === "failed"
                            ? "text-red-500"
                            : action.execution_status === "processing"
                            ? "text-blue-500 animate-spin"
                            : "text-slate-400"
                        }`}
                      />
                      <span className="text-[10px] text-slate-500">
                        {action.execution_status_display}
                      </span>
                    </div>
                  </div>

                  {/* Details */}
                  {action.refund_amount && (
                    <p className="text-xs text-violet-700 font-medium">
                      ${parseFloat(action.refund_amount).toFixed(2)} refunded
                      {action.stripe_refund_id && (
                        <span className="text-slate-400 ml-1">
                          ({action.stripe_refund_id})
                        </span>
                      )}
                    </p>
                  )}
                  {action.redo_assigned_company && (
                    <p className="text-xs text-sky-700">
                      Re-cleaning assigned to Company #{action.redo_assigned_company}
                    </p>
                  )}
                  {action.blacklisted_company && (
                    <p className="text-xs text-red-700">
                      Agency #{action.blacklisted_company} blacklisted
                      {action.reassigned_bookings_count > 0 && (
                        <span>
                          {" "}— {action.reassigned_bookings_count} booking(s) reassigned
                        </span>
                      )}
                    </p>
                  )}
                  {action.notes && (
                    <p className="text-xs text-slate-600 mt-1 whitespace-pre-wrap">
                      {action.notes}
                    </p>
                  )}

                  {/* Timestamp */}
                  <p className="text-[10px] text-slate-400 mt-2">
                    {timeAgo(action.executed_at || action.created)}
                  </p>

                  {/* Notifications sent */}
                  {action.notifications && action.notifications.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-slate-100">
                      <p className="text-[10px] font-semibold text-slate-400 mb-1">
                        Notifications ({action.notifications.length})
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {action.notifications.map((notif: ComplaintNotification) => {
                          const ChIcon = CHANNEL_ICONS[notif.channel] || Monitor;
                          return (
                            <span
                              key={notif.id}
                              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-medium ${
                                notif.status === "sent"
                                  ? "bg-green-50 text-green-700"
                                  : notif.status === "failed"
                                  ? "bg-red-50 text-red-600"
                                  : "bg-slate-50 text-slate-500"
                              }`}
                            >
                              <ChIcon className="h-2.5 w-2.5" />
                              {notif.channel_display} → {notif.recipient_name}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
