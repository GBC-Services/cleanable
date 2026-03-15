"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Eye,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  Camera,
  Sparkles,
  Filter,
  Clock,
  BarChart3,
  ThumbsUp,
  ThumbsDown,
  Info,
} from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import { api } from "@/lib/api";
import type {
  JobVerification,
  VerificationStatus,
} from "@/types/support";

// ── Status display map ────────────────────────────────────────────────

const VSTATUS_MAP: Record<
  VerificationStatus,
  { label: string; color: string; bg: string; icon: typeof Clock }
> = {
  10: { label: "Pending", color: "text-slate-500", bg: "bg-slate-100", icon: Clock },
  20: { label: "Analyzing", color: "text-blue-700", bg: "bg-blue-50", icon: Loader2 },
  30: { label: "Approved", color: "text-green-700", bg: "bg-green-50", icon: CheckCircle2 },
  40: { label: "Flagged", color: "text-amber-700", bg: "bg-amber-50", icon: AlertTriangle },
  50: { label: "Rejected", color: "text-red-700", bg: "bg-red-50", icon: XCircle },
  60: { label: "Manual Review", color: "text-purple-700", bg: "bg-purple-50", icon: Eye },
};

// ── Helpers ────────────────────────────────────────────────────────────

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

function scoreColor(score: number): string {
  if (score >= 0.85) return "text-green-600";
  if (score >= 0.60) return "text-amber-600";
  return "text-red-600";
}

function scoreBg(score: number): string {
  if (score >= 0.85) return "bg-green-50";
  if (score >= 0.60) return "bg-amber-50";
  return "bg-red-50";
}

// ── Main Page ──────────────────────────────────────────────────────────

export default function QAInspectorDashboard() {
  const { user } = useAuthStore();

  const [verifications, setVerifications] = useState<JobVerification[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedV, setSelectedV] = useState<JobVerification | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>("review");
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // ── Fetch ─────────────────────────────────────────────────────────

  const fetchVerifications = useCallback(async () => {
    try {
      setLoading(true);
      let query = "/support/verify/?";
      if (filterStatus === "review") {
        // Show flagged + manual review
        query += "status=40&status=60";
      } else if (filterStatus !== "all") {
        query += `status=${filterStatus}`;
      }
      const res = await api.get<JobVerification[] | { results: JobVerification[] }>(query);
      const list = Array.isArray(res) ? res : res.results ?? [];
      setVerifications(list);
      setError(null);
    } catch {
      setError("Failed to load verifications.");
    } finally {
      setLoading(false);
    }
  }, [filterStatus]);

  const fetchDetail = async (uuid: string) => {
    setLoadingDetail(true);
    try {
      const res = await api.get<JobVerification>(`/support/verify/${uuid}/`);
      setSelectedV(res);
    } catch {
      setError("Failed to load verification details.");
    } finally {
      setLoadingDetail(false);
    }
  };

  useEffect(() => {
    fetchVerifications();
  }, [fetchVerifications]);

  // ── Review Actions ────────────────────────────────────────────────

  const handleReview = async (approve: boolean) => {
    if (!selectedV) return;
    setReviewing(true);
    try {
      await api.post(`/support/verify/${selectedV.uuid}/review/`, {
        status: approve ? 30 : 50,
        reviewer_notes: reviewNotes,
      });
      setSuccessMsg(`Verification ${approve ? "approved" : "rejected"}.`);
      setTimeout(() => setSuccessMsg(null), 3000);
      setSelectedV(null);
      setReviewNotes("");
      fetchVerifications();
    } catch {
      setError("Failed to submit review.");
    } finally {
      setReviewing(false);
    }
  };

  // ── Stats ─────────────────────────────────────────────────────────

  const pendingReview = verifications.filter(
    (v) => v.status === 40 || v.status === 60,
  ).length;
  const approved = verifications.filter((v) => v.status === 30).length;
  const rejected = verifications.filter((v) => v.status === 50).length;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">QA Inspector</h1>
        <p className="mt-1 text-sm text-slate-500">
          Review AI-analyzed post-job verifications and override
          decisions when needed.
        </p>
      </div>

      {/* Stats Row */}
      <div className="mb-6 grid grid-cols-3 gap-3">
        <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
          <div className="flex items-center gap-2 mb-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-50">
              <Eye className="h-4 w-4 text-amber-500" />
            </span>
            <span className="text-xs font-medium text-slate-500">
              Needs Review
            </span>
          </div>
          <p className="text-xl font-bold text-slate-900">{pendingReview}</p>
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
          <div className="flex items-center gap-2 mb-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-green-50">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            </span>
            <span className="text-xs font-medium text-slate-500">
              Approved
            </span>
          </div>
          <p className="text-xl font-bold text-slate-900">{approved}</p>
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
          <div className="flex items-center gap-2 mb-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-red-50">
              <XCircle className="h-4 w-4 text-red-500" />
            </span>
            <span className="text-xs font-medium text-slate-500">
              Rejected
            </span>
          </div>
          <p className="text-xl font-bold text-slate-900">{rejected}</p>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="mb-4 flex items-start gap-3 rounded-lg bg-red-50 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}
      {successMsg && (
        <div className="mb-4 flex items-start gap-3 rounded-lg bg-green-50 p-4">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
          <p className="text-sm text-green-700">{successMsg}</p>
        </div>
      )}

      {/* Filters */}
      <div className="mb-4 flex items-center gap-2">
        <Filter className="h-4 w-4 text-slate-400" />
        <select
          data-testid="select-verification-filter"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
        >
          <option value="review">Needs Review</option>
          <option value="all">All</option>
          <option value="30">Approved</option>
          <option value="50">Rejected</option>
          <option value="10">Pending</option>
          <option value="20">Analyzing</option>
        </select>
      </div>

      {/* Main Content — Two-panel */}
      <div className="flex gap-6 flex-col lg:flex-row">
        {/* Left: Verification Queue */}
        <div className="flex-1 min-w-0">
          <div className="space-y-2">
            {loading ? (
              <div className="flex items-center justify-center py-12 text-sm text-slate-400">
                <Loader2 className="h-4 w-4 animate-spin mr-2" /> Loading...
              </div>
            ) : verifications.length === 0 ? (
              <div className="rounded-xl bg-white p-8 text-center shadow-sm ring-1 ring-slate-100">
                <Camera className="mx-auto h-8 w-8 text-slate-300 mb-2" />
                <p className="text-sm text-slate-500">
                  No verifications found.
                </p>
              </div>
            ) : (
              verifications.map((v) => (
                <VerificationRow
                  key={v.id}
                  verification={v}
                  isSelected={selectedV?.id === v.id}
                  onClick={() => fetchDetail(v.uuid)}
                />
              ))
            )}
          </div>
        </div>

        {/* Right: Detail Panel */}
        <div className="lg:w-[480px] shrink-0">
          {loadingDetail ? (
            <div className="rounded-xl bg-white p-8 shadow-sm ring-1 ring-slate-100 text-center">
              <Loader2 className="mx-auto h-6 w-6 animate-spin text-indigo-500" />
            </div>
          ) : selectedV ? (
            <div className="rounded-xl bg-white shadow-sm ring-1 ring-slate-100 overflow-hidden sticky top-4">
              {/* Header */}
              <div className="border-b border-slate-100 px-5 py-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">
                      Verification #{selectedV.id}
                    </h3>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {selectedV.service_pro_name} &middot; Booking #
                      {selectedV.booking} &middot;{" "}
                      {timeAgo(selectedV.created)}
                    </p>
                  </div>
                  {(() => {
                    const info = VSTATUS_MAP[selectedV.status];
                    return (
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${info?.bg} ${info?.color}`}
                      >
                        {info?.label}
                      </span>
                    );
                  })()}
                </div>
              </div>

              {/* Media Preview */}
              {selectedV.media_file && (
                <div className="border-b border-slate-100">
                  {selectedV.media_type === "video" ? (
                    <video
                      src={selectedV.media_file}
                      controls
                      className="w-full max-h-64 object-contain bg-black"
                      data-testid="detail-video"
                    />
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={selectedV.media_file}
                      alt="Post-job verification"
                      className="w-full max-h-64 object-contain bg-black"
                      data-testid="detail-image"
                    />
                  )}
                </div>
              )}

              {/* Score + AI Summary */}
              {selectedV.cleanliness_score !== null && (
                <div
                  className={`px-5 py-4 border-b border-slate-100 ${scoreBg(selectedV.cleanliness_score)}`}
                >
                  <div className="flex items-center gap-4">
                    <div className="text-center">
                      <p
                        className={`text-3xl font-bold ${scoreColor(selectedV.cleanliness_score)}`}
                      >
                        {Math.round(selectedV.cleanliness_score * 100)}%
                      </p>
                      <p className="text-xs text-slate-500">Score</p>
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-1.5 mb-1">
                        <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
                        <span className="text-xs font-semibold text-indigo-700">
                          AI Assessment
                        </span>
                      </div>
                      <p className="text-xs text-slate-600">
                        {selectedV.ai_summary}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Issues */}
              {selectedV.issues_detected &&
                selectedV.issues_detected.length > 0 && (
                  <div className="px-5 py-4 border-b border-slate-100">
                    <p className="text-xs font-semibold text-slate-500 mb-2">
                      Issues Detected
                    </p>
                    <ul className="space-y-1">
                      {selectedV.issues_detected.map((issue, i) => (
                        <li
                          key={i}
                          className="flex items-start gap-2 text-xs text-amber-700"
                        >
                          <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0" />
                          {issue}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

              {/* Previous Review */}
              {selectedV.reviewed_at && (
                <div className="px-5 py-3 border-b border-slate-100 bg-slate-50">
                  <p className="text-xs text-slate-500">
                    Reviewed {timeAgo(selectedV.reviewed_at)}
                    {selectedV.reviewer_notes &&
                      ` — "${selectedV.reviewer_notes}"`}
                  </p>
                </div>
              )}

              {/* Review Actions */}
              {(selectedV.status === 40 || selectedV.status === 60) && (
                <div className="px-5 py-4 space-y-3">
                  <textarea
                    data-testid="textarea-review-notes"
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    placeholder="Review notes (optional)..."
                    rows={2}
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-200 resize-none"
                  />
                  <div className="flex gap-2">
                    <button
                      data-testid="button-approve-verification"
                      onClick={() => handleReview(true)}
                      disabled={reviewing}
                      className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-green-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-green-700 disabled:opacity-50"
                    >
                      {reviewing ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <ThumbsUp className="h-4 w-4" />
                      )}
                      Approve
                    </button>
                    <button
                      data-testid="button-reject-verification"
                      onClick={() => handleReview(false)}
                      disabled={reviewing}
                      className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-50"
                    >
                      {reviewing ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <ThumbsDown className="h-4 w-4" />
                      )}
                      Reject
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-xl bg-white p-8 shadow-sm ring-1 ring-slate-100 text-center">
              <Eye className="mx-auto h-8 w-8 text-slate-300 mb-2" />
              <p className="text-sm text-slate-500">
                Select a verification to review
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Info */}
      <div className="mt-6 flex items-start gap-2.5 text-xs text-slate-400">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <p>
          Jobs scoring above 85% are auto-approved. Scores between 60–85% are
          flagged for your review. Below 60% are sent to manual review. Your
          decision overrides the AI.
        </p>
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────

function VerificationRow({
  verification,
  isSelected,
  onClick,
}: {
  verification: JobVerification;
  isSelected: boolean;
  onClick: () => void;
}) {
  const info = VSTATUS_MAP[verification.status];
  const StatusIcon = info?.icon || Clock;

  return (
    <button
      data-testid={`verification-row-${verification.id}`}
      onClick={onClick}
      className={`w-full text-left rounded-xl bg-white p-4 shadow-sm ring-1 transition hover:ring-indigo-200 ${
        isSelected ? "ring-indigo-300 bg-indigo-50/30" : "ring-slate-100"
      }`}
    >
      <div className="flex items-start justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <Camera className="h-3.5 w-3.5 text-slate-400" />
          <span className="text-sm font-semibold text-slate-800">
            Verification #{verification.id}
          </span>
        </div>
        <span className="text-xs text-slate-400">
          {timeAgo(verification.created)}
        </span>
      </div>

      <p className="text-xs text-slate-500 mb-2">
        {verification.service_pro_name} &middot; Booking #
        {verification.booking}
      </p>

      <div className="flex items-center gap-2 flex-wrap">
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${info?.bg} ${info?.color}`}
        >
          <StatusIcon className="h-3 w-3" />
          {info?.label}
        </span>

        {verification.cleanliness_score !== null && (
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold ${scoreBg(verification.cleanliness_score)} ${scoreColor(verification.cleanliness_score)}`}
          >
            {Math.round(verification.cleanliness_score * 100)}%
          </span>
        )}

        {verification.issues_detected &&
          verification.issues_detected.length > 0 && (
            <span className="text-[10px] text-amber-500">
              {verification.issues_detected.length} issue(s)
            </span>
          )}

        {verification.analyzed_at && (
          <Sparkles className="h-3 w-3 text-indigo-400" />
        )}
      </div>
    </button>
  );
}
