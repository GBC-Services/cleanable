"use client";

/**
 * Complaint Form
 * ===============
 *
 * Resident-facing form to submit a complaint. Supports the four
 * predefined scenarios with description and booking reference.
 */

import { useState } from "react";
import {
  AlertTriangle,
  UserX,
  ShieldAlert,
  Clock,
  Loader2,
  CheckCircle2,
  XCircle,
  Send,
} from "lucide-react";
import { api } from "@/lib/api";
import type { ComplaintScenario, ComplaintCreatePayload } from "@/types/complaints";

const SCENARIOS: {
  value: ComplaintScenario;
  label: string;
  icon: typeof AlertTriangle;
  color: string;
  description: string;
}[] = [
  {
    value: "incomplete_clean",
    label: "Incomplete Clean",
    icon: AlertTriangle,
    color: "text-amber-500 bg-amber-50 ring-amber-200",
    description: "Areas were missed or cleaning was not thorough.",
  },
  {
    value: "no_show",
    label: "No-Show",
    icon: UserX,
    color: "text-red-500 bg-red-50 ring-red-200",
    description: "The cleaner did not arrive for the scheduled appointment.",
  },
  {
    value: "damage_reported",
    label: "Damage Reported",
    icon: ShieldAlert,
    color: "text-red-600 bg-red-50 ring-red-200",
    description: "Property or belongings were damaged during the service.",
  },
  {
    value: "late_arrival",
    label: "Late Arrival",
    icon: Clock,
    color: "text-indigo-500 bg-indigo-50 ring-indigo-200",
    description: "The cleaner arrived significantly later than scheduled.",
  },
];

interface ComplaintFormProps {
  bookingId: number;
  cleaningId?: number | null;
  onSuccess?: () => void;
  onCancel?: () => void;
}

export default function ComplaintForm({
  bookingId,
  cleaningId,
  onSuccess,
  onCancel,
}: ComplaintFormProps) {
  const [selectedScenario, setSelectedScenario] = useState<ComplaintScenario | null>(null);
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async () => {
    if (!selectedScenario || !description.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const payload: ComplaintCreatePayload = {
        booking: bookingId,
        scenario: selectedScenario,
        description: description.trim(),
      };
      if (cleaningId) {
        payload.cleaning = cleaningId;
      }
      await api.post("/support/complaints/", payload);
      setSuccess(true);
      onSuccess?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to submit complaint.");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-100 text-center">
        <CheckCircle2 className="mx-auto h-10 w-10 text-green-500 mb-3" />
        <h3 className="text-lg font-bold text-slate-900 mb-1">Complaint Submitted</h3>
        <p className="text-sm text-slate-500">
          Your complaint has been escalated to our Support team. You will receive
          real-time updates via SMS and push notifications.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-white shadow-sm ring-1 ring-slate-100 overflow-hidden">
      <div className="border-b border-slate-100 px-5 py-4">
        <h3 className="text-sm font-bold text-slate-900">Report an Issue</h3>
        <p className="text-xs text-slate-500 mt-0.5">
          Select what happened and describe the issue.
        </p>
      </div>

      <div className="px-5 py-4 space-y-4">
        {/* Scenario Selection */}
        <div className="grid grid-cols-2 gap-2">
          {SCENARIOS.map((s) => {
            const Icon = s.icon;
            const isSelected = selectedScenario === s.value;
            return (
              <button
                key={s.value}
                data-testid={`scenario-${s.value}`}
                onClick={() => setSelectedScenario(s.value)}
                className={`flex flex-col items-center gap-1.5 rounded-xl p-3 text-center ring-1 transition ${
                  isSelected
                    ? s.color
                    : "bg-white ring-slate-100 hover:ring-slate-200"
                }`}
              >
                <Icon
                  className={`h-5 w-5 ${
                    isSelected ? "" : "text-slate-400"
                  }`}
                />
                <span
                  className={`text-xs font-semibold ${
                    isSelected ? "" : "text-slate-600"
                  }`}
                >
                  {s.label}
                </span>
                <span className="text-[10px] text-slate-400 leading-tight">
                  {s.description}
                </span>
              </button>
            );
          })}
        </div>

        {/* Description */}
        <textarea
          data-testid="textarea-complaint-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe what happened in detail..."
          rows={4}
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-200 resize-none"
        />

        {/* Error */}
        {error && (
          <div className="flex items-start gap-2 rounded-lg bg-red-50 p-3">
            <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-500" />
            <p className="text-xs text-red-700">{error}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          {onCancel && (
            <button
              data-testid="button-cancel-complaint"
              onClick={onCancel}
              className="flex-1 rounded-lg bg-slate-100 px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-200"
            >
              Cancel
            </button>
          )}
          <button
            data-testid="button-submit-complaint"
            onClick={handleSubmit}
            disabled={loading || !selectedScenario || !description.trim()}
            className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            Submit Complaint
          </button>
        </div>
      </div>
    </div>
  );
}
