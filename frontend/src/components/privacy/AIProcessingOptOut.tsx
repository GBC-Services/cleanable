"use client";

import { useState } from "react";
import {
  ShieldAlert,
  Bot,
  Eye,
  Loader2,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";

// ── Types ──────────────────────────────────────────────────────────────

interface AIProcessingOptOutProps {
  initialOptOut: boolean;
  onUpdate?: (optOut: boolean) => void;
}

// ── Component ──────────────────────────────────────────────────────────

/**
 * Resident AI Processing Opt-Out Toggle
 *
 * When enabled, Service Pro verification videos will bypass Cloudflare AI
 * analysis entirely and be routed to a human QA Inspector or Agency Owner
 * for manual approval.
 */
export default function AIProcessingOptOut({
  initialOptOut,
  onUpdate,
}: AIProcessingOptOutProps) {
  const { tokens } = useAuthStore();
  const [optOut, setOptOut] = useState(initialOptOut);
  const [isUpdating, setIsUpdating] = useState(false);
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

  const handleToggle = async () => {
    if (!tokens?.access || isUpdating) return;

    const newValue = !optOut;
    setIsUpdating(true);
    setMessage(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/governance/privacy/`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${tokens.access}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          resident_ai_processing_opt_out: newValue,
        }),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || "Failed to update preference.");
      }

      setOptOut(newValue);
      onUpdate?.(newValue);
      setMessage({
        type: "success",
        text: newValue
          ? "AI processing opt-out enabled. Verification videos will be reviewed by a human."
          : "AI processing re-enabled. Verification videos will be analyzed by AI.",
      });
    } catch (err: unknown) {
      setMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to update preference.",
      });
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="rounded-xl bg-white shadow-sm ring-1 ring-slate-100 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-slate-100 px-6 py-4">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-purple-50">
          <ShieldAlert className="h-5 w-5 text-purple-600" />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-slate-800">
            AI Processing Opt-Out
          </h2>
          <p className="text-xs text-slate-500">
            Control how verification videos of your property are analyzed
          </p>
        </div>
      </div>

      {/* Body */}
      <div className="px-6 py-5 space-y-4">
        {/* Toggle Row */}
        <div className="flex items-start gap-4">
          <button
            data-testid="toggle-ai-opt-out"
            onClick={handleToggle}
            disabled={isUpdating}
            className={`
              relative mt-0.5 inline-flex h-6 w-11 shrink-0 cursor-pointer
              items-center rounded-full transition-colors duration-200
              focus-visible:outline-none focus-visible:ring-2
              focus-visible:ring-purple-500 focus-visible:ring-offset-2
              disabled:opacity-50 disabled:cursor-not-allowed
              ${optOut ? "bg-purple-600" : "bg-slate-200"}
            `}
            role="switch"
            aria-checked={optOut}
            aria-label="Toggle AI processing opt-out"
          >
            <span
              className={`
                inline-block h-4 w-4 rounded-full bg-white shadow-sm
                transition-transform duration-200
                ${optOut ? "translate-x-6" : "translate-x-1"}
              `}
            />
            {isUpdating && (
              <Loader2 className="absolute inset-0 m-auto h-3 w-3 animate-spin text-white" />
            )}
          </button>

          <div className="flex-1">
            <p className="text-sm font-medium text-slate-800">
              {optOut ? "AI processing is disabled" : "AI processing is enabled"}
            </p>
            <p className="mt-0.5 text-xs text-slate-500">
              {optOut
                ? "Your Service Pro's verification videos will not be analyzed by AI. A human QA Inspector or Agency Owner will review them manually."
                : "Service Pro verification videos will be automatically analyzed by Cloudflare Workers AI for cleanliness scoring."}
            </p>
          </div>
        </div>

        {/* Info Cards */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div
            className={`
              rounded-lg p-3 transition-colors
              ${optOut ? "bg-purple-50 ring-1 ring-purple-100" : "bg-slate-50"}
            `}
          >
            <div className="flex items-center gap-2 mb-1">
              <Eye className={`h-4 w-4 ${optOut ? "text-purple-600" : "text-slate-400"}`} />
              <span className={`text-xs font-semibold ${optOut ? "text-purple-800" : "text-slate-600"}`}>
                Human Review
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Videos are reviewed by a certified QA Inspector for quality verification.
            </p>
          </div>

          <div
            className={`
              rounded-lg p-3 transition-colors
              ${!optOut ? "bg-blue-50 ring-1 ring-blue-100" : "bg-slate-50"}
            `}
          >
            <div className="flex items-center gap-2 mb-1">
              <Bot className={`h-4 w-4 ${!optOut ? "text-blue-600" : "text-slate-400"}`} />
              <span className={`text-xs font-semibold ${!optOut ? "text-blue-800" : "text-slate-600"}`}>
                AI Analysis
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Cloudflare Workers AI scans for cleanliness, with privacy blur detection for faces and documents.
            </p>
          </div>
        </div>

        {/* Status message */}
        {message && (
          <div
            className={`
              flex items-start gap-2 rounded-lg p-3 text-xs
              ${message.type === "success"
                ? "bg-green-50 text-green-700"
                : "bg-red-50 text-red-700"
              }
            `}
            data-testid={`message-${message.type}`}
          >
            {message.type === "success" ? (
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            ) : (
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            )}
            <span>{message.text}</span>
          </div>
        )}
      </div>
    </div>
  );
}
