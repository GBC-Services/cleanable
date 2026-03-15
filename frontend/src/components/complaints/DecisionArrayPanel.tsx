"use client";

/**
 * Decision Array Panel
 * =====================
 *
 * The Resolution Toolset for Support Architects. Shows three action
 * cards — Refund, Schedule Re-do, Cancel & Blacklist — plus an internal
 * notes section. Each action calls the backend resolution engine.
 */

import { useState } from "react";
import {
  DollarSign,
  Banknote,
  CalendarPlus,
  Ban,
  StickyNote,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  Complaint,
  ResolutionAction,
  RefundPayload,
  ScheduleRedoPayload,
  CancelBlacklistPayload,
} from "@/types/complaints";

interface DecisionArrayPanelProps {
  complaint: Complaint;
  onActionComplete: () => void;
}

export default function DecisionArrayPanel({
  complaint,
  onActionComplete,
}: DecisionArrayPanelProps) {
  const [expandedAction, setExpandedAction] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Refund state
  const [refundType, setRefundType] = useState<"refund_partial" | "refund_full">("refund_full");
  const [refundAmount, setRefundAmount] = useState("");
  const [refundNotes, setRefundNotes] = useState("");

  // Re-do state
  const [useDifferentAgency, setUseDifferentAgency] = useState(false);
  const [redoNotes, setRedoNotes] = useState("");

  // Blacklist state
  const [blacklistNotes, setBlacklistNotes] = useState("");

  // Note state
  const [internalNote, setInternalNote] = useState("");

  const isResolved = complaint.status === "resolved" || complaint.status === "closed";

  const toggleAction = (action: string) => {
    setExpandedAction(expandedAction === action ? null : action);
    setError(null);
    setSuccess(null);
  };

  const handleRefund = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload: RefundPayload = {
        refund_type: refundType,
        notes: refundNotes,
      };
      if (refundType === "refund_partial" && refundAmount) {
        payload.amount = parseFloat(refundAmount);
      }
      await api.post(`/support/complaints/${complaint.uuid}/refund/`, payload);
      setSuccess("Refund processed successfully.");
      setRefundAmount("");
      setRefundNotes("");
      onActionComplete();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Refund failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleRedo = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload: ScheduleRedoPayload = {
        use_different_agency: useDifferentAgency,
        notes: redoNotes,
      };
      await api.post(`/support/complaints/${complaint.uuid}/redo/`, payload);
      setSuccess("Re-cleaning scheduled successfully.");
      setRedoNotes("");
      onActionComplete();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Re-do scheduling failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleBlacklist = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload: CancelBlacklistPayload = { notes: blacklistNotes };
      await api.post(`/support/complaints/${complaint.uuid}/blacklist/`, payload);
      setSuccess("Agency blacklisted and bookings reassigned.");
      setBlacklistNotes("");
      onActionComplete();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Blacklist action failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleNote = async () => {
    if (!internalNote.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await api.post(`/support/complaints/${complaint.uuid}/note/`, {
        notes: internalNote,
      });
      setSuccess("Note added.");
      setInternalNote("");
      onActionComplete();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to add note.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
        Resolution Toolset
      </h4>

      {/* Alerts */}
      {error && (
        <div className="flex items-start gap-2 rounded-lg bg-red-50 p-3">
          <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-500" />
          <p className="text-xs text-red-700">{error}</p>
        </div>
      )}
      {success && (
        <div className="flex items-start gap-2 rounded-lg bg-green-50 p-3">
          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-green-500" />
          <p className="text-xs text-green-700">{success}</p>
        </div>
      )}

      {isResolved && (
        <div className="flex items-start gap-2 rounded-lg bg-slate-50 p-3">
          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
          <p className="text-xs text-slate-500">
            This complaint has been resolved. Notes can still be added.
          </p>
        </div>
      )}

      {/* ── 1. Refund ─────────────────────────────────────────────────── */}
      <ActionCard
        title="Refund"
        subtitle="Partial or full via Stripe"
        icon={<DollarSign className="h-4 w-4 text-violet-500" />}
        color="violet"
        expanded={expandedAction === "refund"}
        onToggle={() => toggleAction("refund")}
        disabled={isResolved}
      >
        <div className="space-y-3">
          <div className="flex gap-2">
            <button
              data-testid="button-refund-full"
              onClick={() => setRefundType("refund_full")}
              className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition ${
                refundType === "refund_full"
                  ? "bg-violet-100 text-violet-800 ring-1 ring-violet-300"
                  : "bg-slate-50 text-slate-600 hover:bg-slate-100"
              }`}
            >
              <Banknote className="inline h-3.5 w-3.5 mr-1" />
              Full Refund
            </button>
            <button
              data-testid="button-refund-partial"
              onClick={() => setRefundType("refund_partial")}
              className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition ${
                refundType === "refund_partial"
                  ? "bg-violet-100 text-violet-800 ring-1 ring-violet-300"
                  : "bg-slate-50 text-slate-600 hover:bg-slate-100"
              }`}
            >
              <DollarSign className="inline h-3.5 w-3.5 mr-1" />
              Partial Refund
            </button>
          </div>

          {refundType === "refund_partial" && (
            <input
              data-testid="input-refund-amount"
              type="number"
              step="0.01"
              min="0.01"
              placeholder="Refund amount (USD)"
              value={refundAmount}
              onChange={(e) => setRefundAmount(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-violet-200"
            />
          )}

          <textarea
            data-testid="textarea-refund-notes"
            value={refundNotes}
            onChange={(e) => setRefundNotes(e.target.value)}
            placeholder="Reason for refund..."
            rows={2}
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-violet-200 resize-none"
          />

          <button
            data-testid="button-execute-refund"
            onClick={handleRefund}
            disabled={loading || (refundType === "refund_partial" && !refundAmount)}
            className="w-full flex items-center justify-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <DollarSign className="h-4 w-4" />
            )}
            Process Refund
          </button>
        </div>
      </ActionCard>

      {/* ── 2. Schedule Re-do ─────────────────────────────────────────── */}
      <ActionCard
        title="Schedule Re-do"
        subtitle="High-priority re-cleaning"
        icon={<CalendarPlus className="h-4 w-4 text-sky-500" />}
        color="sky"
        expanded={expandedAction === "redo"}
        onToggle={() => toggleAction("redo")}
        disabled={isResolved}
      >
        <div className="space-y-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              data-testid="checkbox-different-agency"
              type="checkbox"
              checked={useDifferentAgency}
              onChange={(e) => setUseDifferentAgency(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            <span className="text-xs text-slate-700 font-medium">
              Assign to a different agency
            </span>
          </label>

          <textarea
            data-testid="textarea-redo-notes"
            value={redoNotes}
            onChange={(e) => setRedoNotes(e.target.value)}
            placeholder="Additional instructions..."
            rows={2}
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-200 resize-none"
          />

          <button
            data-testid="button-execute-redo"
            onClick={handleRedo}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <CalendarPlus className="h-4 w-4" />
            )}
            Schedule Re-cleaning
          </button>
        </div>
      </ActionCard>

      {/* ── 3. Cancel & Blacklist ─────────────────────────────────────── */}
      <ActionCard
        title="Cancel & Blacklist"
        subtitle="Terminate service + re-assign bookings"
        icon={<Ban className="h-4 w-4 text-red-500" />}
        color="red"
        expanded={expandedAction === "blacklist"}
        onToggle={() => toggleAction("blacklist")}
        disabled={isResolved}
      >
        <div className="space-y-3">
          <div className="flex items-start gap-2 rounded-lg bg-red-50 p-3">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-500" />
            <p className="text-xs text-red-700">
              This will cancel the current service, blacklist the agency for this
              resident, and automatically re-assign all future recurring bookings
              to a different agency.
            </p>
          </div>

          <textarea
            data-testid="textarea-blacklist-notes"
            value={blacklistNotes}
            onChange={(e) => setBlacklistNotes(e.target.value)}
            placeholder="Reason for blacklisting..."
            rows={2}
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-red-200 resize-none"
          />

          <button
            data-testid="button-execute-blacklist"
            onClick={handleBlacklist}
            disabled={loading || !complaint.company}
            className="w-full flex items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Ban className="h-4 w-4" />
            )}
            Cancel & Blacklist Agency
          </button>
        </div>
      </ActionCard>

      {/* ── 4. Internal Note ──────────────────────────────────────────── */}
      <div className="rounded-xl bg-white ring-1 ring-slate-100 p-4">
        <div className="flex items-center gap-2 mb-3">
          <StickyNote className="h-4 w-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-700">
            Internal Note
          </span>
        </div>
        <textarea
          data-testid="textarea-internal-note"
          value={internalNote}
          onChange={(e) => setInternalNote(e.target.value)}
          placeholder="Add an internal note..."
          rows={2}
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200 resize-none"
        />
        <button
          data-testid="button-add-note"
          onClick={handleNote}
          disabled={loading || !internalNote.trim()}
          className="mt-2 flex items-center gap-2 rounded-lg bg-slate-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
          Add Note
        </button>
      </div>
    </div>
  );
}

// ── Action Card Wrapper ─────────────────────────────────────────────────

function ActionCard({
  title,
  subtitle,
  icon,
  color,
  expanded,
  onToggle,
  disabled,
  children,
}: {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  color: string;
  expanded: boolean;
  onToggle: () => void;
  disabled: boolean;
  children: React.ReactNode;
}) {
  const borderColors: Record<string, string> = {
    violet: "ring-violet-200",
    sky: "ring-sky-200",
    red: "ring-red-200",
  };

  return (
    <div
      className={`rounded-xl bg-white ring-1 overflow-hidden transition-all ${
        expanded ? borderColors[color] || "ring-slate-200" : "ring-slate-100"
      } ${disabled ? "opacity-60" : ""}`}
    >
      <button
        data-testid={`button-toggle-${title.toLowerCase().replace(/\s+/g, "-")}`}
        onClick={onToggle}
        disabled={disabled}
        className="flex items-center justify-between w-full px-4 py-3 text-left hover:bg-slate-50 transition disabled:cursor-not-allowed"
      >
        <div className="flex items-center gap-3">
          {icon}
          <div>
            <p className="text-sm font-semibold text-slate-800">{title}</p>
            <p className="text-[10px] text-slate-400">{subtitle}</p>
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-slate-400" />
        ) : (
          <ChevronDown className="h-4 w-4 text-slate-400" />
        )}
      </button>
      {expanded && <div className="px-4 pb-4 pt-1">{children}</div>}
    </div>
  );
}
