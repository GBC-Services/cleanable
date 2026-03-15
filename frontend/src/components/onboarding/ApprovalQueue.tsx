/**
 * ApprovalQueue — Agency Owner's Incoming Join Requests
 * ======================================================
 *
 * Real-time WebSocket-powered queue showing Service Pro join requests.
 * Agency Owners can approve or reject with one click.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  UserPlus,
  Check,
  X,
  Clock,
  Loader2,
  AlertTriangle,
  Users,
  Bell,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import type {
  ManagerApprovalRequest,
  WSApprovalRequest,
} from "@/types/onboarding";

export default function ApprovalQueue() {
  const { user, tokens } = useAuthStore();
  const [requests, setRequests] = useState<ManagerApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rejectUuid, setRejectUuid] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const wsRef = useRef<WebSocket | null>(null);

  // ── Load existing requests ─────────────────────────────────────────

  const loadRequests = useCallback(async () => {
    try {
      const data = await api.get<ManagerApprovalRequest[]>(
        "/onboarding/approval-requests/?status=pending"
      );
      setRequests(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load requests");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRequests();
  }, [loadRequests]);

  // ── WebSocket for real-time notifications ──────────────────────────

  useEffect(() => {
    if (!user?.company || !tokens?.access) return;

    const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${
      window.location.host
    }/ws/onboarding/approvals/${user.company}/?token=${tokens.access}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg: WSApprovalRequest = JSON.parse(event.data);
        if (msg.type === "approval_request") {
          // Reload the full list to get complete data
          loadRequests();
        }
      } catch {}
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [user, tokens, loadRequests]);

  // ── Actions ────────────────────────────────────────────────────────

  const approveRequest = async (uuid: string) => {
    setActionLoading(uuid);
    try {
      await api.post(`/onboarding/approval-requests/${uuid}/action/`, {
        action: "approve",
      });
      setRequests((prev) => prev.filter((r) => r.uuid !== uuid));
    } catch (err: any) {
      setError(err?.message || "Failed to approve");
    } finally {
      setActionLoading(null);
    }
  };

  const rejectRequest = async (uuid: string) => {
    setActionLoading(uuid);
    try {
      await api.post(`/onboarding/approval-requests/${uuid}/action/`, {
        action: "reject",
        rejection_reason: rejectReason,
      });
      setRequests((prev) => prev.filter((r) => r.uuid !== uuid));
      setRejectUuid(null);
      setRejectReason("");
    } catch (err: any) {
      setError(err?.message || "Failed to reject");
    } finally {
      setActionLoading(null);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <UserPlus className="h-5 w-5 text-brand-500" />
          Join Requests
          {requests.length > 0 && (
            <span className="ml-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
              {requests.length}
            </span>
          )}
        </h3>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-brand-500" />
        </div>
      ) : requests.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center">
          <Users className="mx-auto h-8 w-8 text-gray-300" />
          <p className="mt-2 text-sm text-gray-500">
            No pending join requests.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {requests.map((req) => (
            <div
              key={req.uuid}
              className="rounded-lg border border-gray-200 bg-white p-4"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-semibold text-gray-900">
                    {req.service_pro_name}
                  </p>
                  <p className="text-xs text-gray-500">{req.service_pro_email}</p>
                  <div className="mt-2 flex items-center gap-3">
                    <span className="text-xs text-gray-400">
                      Typed: "{req.typed_agency_name}"
                    </span>
                    <span className="text-xs text-gray-400">
                      Match: {(req.match_score * 100).toFixed(0)}%
                    </span>
                    <span className="flex items-center gap-1 text-xs text-gray-400">
                      <Clock className="h-3 w-3" />
                      Expires {new Date(req.expires_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                {rejectUuid !== req.uuid && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => approveRequest(req.uuid)}
                      disabled={actionLoading === req.uuid}
                      className="flex items-center gap-1 rounded-lg bg-green-500 px-3 py-1.5
                                 text-sm font-medium text-white hover:bg-green-600
                                 disabled:opacity-50"
                    >
                      {actionLoading === req.uuid ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Check className="h-3.5 w-3.5" />
                      )}
                      Approve
                    </button>
                    <button
                      onClick={() => setRejectUuid(req.uuid)}
                      className="flex items-center gap-1 rounded-lg border border-red-200
                                 bg-white px-3 py-1.5 text-sm font-medium text-red-600
                                 hover:bg-red-50"
                    >
                      <X className="h-3.5 w-3.5" />
                      Reject
                    </button>
                  </div>
                )}
              </div>

              {/* Reject reason form */}
              {rejectUuid === req.uuid && (
                <div className="mt-3 flex items-center gap-2">
                  <input
                    type="text"
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    placeholder="Reason (optional)"
                    className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm
                               focus:border-red-400 focus:outline-none"
                  />
                  <button
                    onClick={() => rejectRequest(req.uuid)}
                    disabled={actionLoading === req.uuid}
                    className="rounded-lg bg-red-500 px-3 py-1.5 text-sm font-medium
                               text-white hover:bg-red-600 disabled:opacity-50"
                  >
                    {actionLoading === req.uuid ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      "Confirm Reject"
                    )}
                  </button>
                  <button
                    onClick={() => {
                      setRejectUuid(null);
                      setRejectReason("");
                    }}
                    className="rounded-md p-1.5 text-gray-400 hover:text-gray-600"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
