/**
 * AgencyFuzzyMatch — Service Pro Registration Flow
 * ===================================================
 *
 * Step 1: Service Pro types their agency name
 * Step 2: Fuzzy-match results displayed with confidence scores
 * Step 3: Select match → triggers Manager Approval Request via WebSocket
 * Step 4: Live status updates via WS until approved/rejected
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Search,
  Building2,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Send,
  AlertTriangle,
  Percent,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import type {
  AgencyMatchResult,
  ManagerApprovalRequest,
  ApprovalStatus,
  WSApprovalResult,
  APPROVAL_STATUS_INFO,
} from "@/types/onboarding";

// ── Status badge colors ──────────────────────────────────────────────

const STATUS_COLORS: Record<ApprovalStatus, { text: string; bg: string }> = {
  pending: { text: "text-amber-700", bg: "bg-amber-50 border-amber-200" },
  approved: { text: "text-green-700", bg: "bg-green-50 border-green-200" },
  rejected: { text: "text-red-700", bg: "bg-red-50 border-red-200" },
  expired: { text: "text-gray-500", bg: "bg-gray-100 border-gray-200" },
};

export default function AgencyFuzzyMatch() {
  const { user, tokens } = useAuthStore();
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<AgencyMatchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState<AgencyMatchResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [approval, setApproval] = useState<ManagerApprovalRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Debounced fuzzy search ─────────────────────────────────────────

  const searchAgency = useCallback(async (name: string) => {
    if (name.trim().length < 2) {
      setMatches([]);
      return;
    }
    setSearching(true);
    setError(null);
    try {
      const results = await api.post<AgencyMatchResult[]>(
        "/onboarding/fuzzy-match/",
        { agency_name: name }
      );
      setMatches(results);
    } catch (err: any) {
      setError(err?.message || "Search failed");
    } finally {
      setSearching(false);
    }
  }, []);

  const handleInput = (value: string) => {
    setQuery(value);
    setSelected(null);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => searchAgency(value), 400);
  };

  // ── Submit approval request ────────────────────────────────────────

  const submitRequest = async () => {
    if (!selected) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.post<ManagerApprovalRequest>(
        "/onboarding/request-approval/",
        {
          agency_id: selected.agency_id,
          typed_agency_name: query,
          match_score: selected.match_score,
        }
      );
      setApproval(result);
      connectWebSocket();
    } catch (err: any) {
      setError(err?.message || "Failed to submit request");
    } finally {
      setSubmitting(false);
    }
  };

  // ── WebSocket for live approval status ─────────────────────────────

  const connectWebSocket = useCallback(() => {
    if (!tokens?.access) return;
    const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${
      window.location.host
    }/ws/onboarding/notifications/?token=${tokens.access}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg: WSApprovalResult = JSON.parse(event.data);
        if (msg.type === "approval_result" && approval) {
          setApproval((prev) =>
            prev ? { ...prev, status: msg.data.status } : prev
          );
        }
      } catch {}
    };

    ws.onerror = () => {
      // Silent — will poll as fallback
    };

    return () => ws.close();
  }, [tokens, approval]);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // ── Confidence bar color ───────────────────────────────────────────

  const getScoreColor = (score: number) => {
    if (score >= 0.95) return "bg-green-500";
    if (score >= 0.85) return "bg-brand-500";
    return "bg-amber-500";
  };

  // ── Render: Approval submitted ─────────────────────────────────────

  if (approval) {
    const statusInfo = STATUS_COLORS[approval.status];
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <div className="mb-4 flex items-center gap-3">
          {approval.status === "pending" && (
            <Clock className="h-6 w-6 text-amber-500 animate-pulse" />
          )}
          {approval.status === "approved" && (
            <CheckCircle2 className="h-6 w-6 text-green-500" />
          )}
          {approval.status === "rejected" && (
            <XCircle className="h-6 w-6 text-red-500" />
          )}
          <h3 className="text-lg font-semibold text-gray-900">
            Join Request {approval.status === "pending" ? "Submitted" : approval.status === "approved" ? "Approved" : "Rejected"}
          </h3>
        </div>

        <div className={`rounded-lg border p-4 ${statusInfo.bg}`}>
          <p className={`text-sm font-medium ${statusInfo.text}`}>
            {approval.status === "pending" && (
              <>Waiting for the manager at <span className="font-bold">{approval.agency_name}</span> to review your request...</>
            )}
            {approval.status === "approved" && (
              <>You have been approved to join <span className="font-bold">{approval.agency_name}</span>. Welcome aboard.</>
            )}
            {approval.status === "rejected" && (
              <>Your request to join <span className="font-bold">{approval.agency_name}</span> was declined.
                {approval.rejection_reason && (
                  <span className="block mt-1 text-xs">{approval.rejection_reason}</span>
                )}
              </>
            )}
          </p>
        </div>

        <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
          <span>Match confidence: {(approval.match_score * 100).toFixed(0)}%</span>
          <span>·</span>
          <span>Submitted {new Date(approval.created_at).toLocaleString()}</span>
        </div>
      </div>
    );
  }

  // ── Render: Search & Select ────────────────────────────────────────

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Building2 className="h-5 w-5 text-brand-500" />
          Join Your Agency
        </h3>
        <p className="mt-1 text-sm text-gray-500">
          Type your agency or cleaning company name to get started.
        </p>
      </div>

      {/* Search Input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => handleInput(e.target.value)}
          placeholder="e.g. Acme Cleaning Services"
          className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-4
                     text-sm text-gray-900 placeholder-gray-400 transition
                     focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
        />
        {searching && (
          <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-brand-500" />
        )}
      </div>

      {error && (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Match Results */}
      {matches.length > 0 && (
        <div className="mt-3 space-y-2">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Matches Found
          </p>
          {matches.map((match) => (
            <button
              key={match.agency_id}
              onClick={() => setSelected(match)}
              className={`w-full rounded-lg border p-3 text-left transition
                ${
                  selected?.agency_id === match.agency_id
                    ? "border-brand-500 bg-brand-50 ring-2 ring-brand-500/20"
                    : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50"
                }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-gray-400" />
                  <span className="text-sm font-medium text-gray-900">
                    {match.agency_name}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-16 rounded-full bg-gray-200 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${getScoreColor(match.match_score)}`}
                      style={{ width: `${match.match_score * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-500 tabular-nums">
                    {(match.match_score * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {query.length >= 2 && !searching && matches.length === 0 && (
        <p className="mt-3 text-sm text-gray-500">
          No matching agencies found. Check the spelling or contact your manager.
        </p>
      )}

      {/* Submit Button */}
      {selected && (
        <button
          onClick={submitRequest}
          disabled={submitting}
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-brand-500
                     px-4 py-2.5 text-sm font-medium text-white transition
                     hover:bg-brand-600 disabled:opacity-50"
        >
          {submitting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
          Request to Join {selected.agency_name}
        </button>
      )}
    </div>
  );
}
