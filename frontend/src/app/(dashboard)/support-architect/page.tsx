"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Inbox,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  ArrowUp,
  Send,
  Sparkles,
  BarChart3,
  MessageSquare,
  User,
  Filter,
  ChevronDown,
  ChevronUp,
  Smile,
  Frown,
  Meh,
  CreditCard,
  Calendar,
  Star,
  Key,
  XCircle,
  Wrench,
  HelpCircle,
  Zap,
} from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import { api } from "@/lib/api";
import type {
  SupportTicket,
  TicketStats,
  TicketStatus,
  TicketPriority,
  TicketSentiment,
  AICategory,
  TICKET_STATUS_INFO,
  TICKET_PRIORITY_INFO,
  SENTIMENT_INFO,
  AI_CATEGORY_INFO,
} from "@/types/support";

// ── Status / Priority / Sentiment display maps ────────────────────────

const STATUS_MAP: Record<TicketStatus, { label: string; color: string; bg: string }> = {
  10: { label: "New", color: "text-blue-700", bg: "bg-blue-50" },
  20: { label: "In Work", color: "text-amber-700", bg: "bg-amber-50" },
  30: { label: "Resolved", color: "text-green-700", bg: "bg-green-50" },
  40: { label: "Cancelled", color: "text-slate-500", bg: "bg-slate-100" },
  50: { label: "Escalated", color: "text-red-700", bg: "bg-red-50" },
};

const PRIORITY_MAP: Record<TicketPriority, { label: string; color: string; bg: string }> = {
  10: { label: "Low", color: "text-slate-500", bg: "bg-slate-100" },
  20: { label: "Medium", color: "text-blue-700", bg: "bg-blue-50" },
  30: { label: "High", color: "text-amber-700", bg: "bg-amber-50" },
  40: { label: "Urgent", color: "text-red-700", bg: "bg-red-50" },
};

const SENTIMENT_MAP: Record<string, { icon: typeof Smile; color: string }> = {
  positive: { icon: Smile, color: "text-green-500" },
  negative: { icon: Frown, color: "text-red-500" },
  neutral: { icon: Meh, color: "text-slate-400" },
};

const CATEGORY_ICONS: Record<string, typeof CreditCard> = {
  billing: CreditCard,
  scheduling: Calendar,
  quality: Star,
  access: Key,
  cancellation: XCircle,
  technical: Wrench,
  feedback: MessageSquare,
  other: HelpCircle,
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

// ── Main Page ──────────────────────────────────────────────────────────

export default function SupportArchitectDashboard() {
  const { user } = useAuthStore();

  // State
  const [stats, setStats] = useState<TicketStats | null>(null);
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTicket, setSelectedTicket] = useState<SupportTicket | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>("open");
  const [filterPriority, setFilterPriority] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // ── Fetch Data ────────────────────────────────────────────────────

  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get<TicketStats>("/support/tickets/stats/");
      setStats(res);
    } catch {
      // Stats are non-critical
    }
  }, []);

  const fetchTickets = useCallback(async () => {
    try {
      setLoading(true);
      let query = "/support/tickets/?";
      if (filterStatus === "open") {
        query += "status=10&status=20";
      } else if (filterStatus !== "all") {
        query += `status=${filterStatus}`;
      }
      if (filterPriority !== "all") {
        query += `&priority=${filterPriority}`;
      }
      const res = await api.get<SupportTicket[] | { results: SupportTicket[] }>(query);
      const list = Array.isArray(res) ? res : res.results ?? [];
      setTickets(list);
      setError(null);
    } catch {
      setError("Failed to load tickets.");
    } finally {
      setLoading(false);
    }
  }, [filterStatus, filterPriority]);

  const fetchTicketDetail = async (uuid: string) => {
    setLoadingDetail(true);
    try {
      const res = await api.get<SupportTicket>(`/support/tickets/${uuid}/`);
      setSelectedTicket(res);
    } catch {
      setError("Failed to load ticket details.");
    } finally {
      setLoadingDetail(false);
    }
  };

  useEffect(() => {
    fetchStats();
    fetchTickets();
  }, [fetchStats, fetchTickets]);

  // ── Actions ───────────────────────────────────────────────────────

  const handleReply = async () => {
    if (!selectedTicket || !replyText.trim()) return;
    setSending(true);
    try {
      await api.post(`/support/tickets/${selectedTicket.uuid}/messages/`, {
        text: replyText,
      });
      setReplyText("");
      setSuccessMsg("Reply sent.");
      setTimeout(() => setSuccessMsg(null), 3000);
      fetchTicketDetail(selectedTicket.uuid);
    } catch {
      setError("Failed to send reply.");
    } finally {
      setSending(false);
    }
  };

  const handleResolve = async () => {
    if (!selectedTicket) return;
    setResolving(true);
    try {
      await api.post(`/support/tickets/${selectedTicket.uuid}/resolve/`, {
        resolution_notes: replyText || "Resolved via dashboard.",
      });
      setSuccessMsg("Ticket resolved.");
      setTimeout(() => setSuccessMsg(null), 3000);
      setSelectedTicket(null);
      fetchTickets();
      fetchStats();
    } catch {
      setError("Failed to resolve ticket.");
    } finally {
      setResolving(false);
    }
  };

  const handleUseSuggested = () => {
    if (selectedTicket?.ai_suggested_response) {
      setReplyText(selectedTicket.ai_suggested_response);
    }
  };

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          Support Architect
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          AI-powered ticket triage, prioritized queues, and one-click resolution.
        </p>
      </div>

      {/* Stats Row */}
      {stats && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <StatCard
            label="Open"
            value={stats.open}
            icon={<Inbox className="h-4 w-4 text-blue-500" />}
            bg="bg-blue-50"
          />
          <StatCard
            label="Unassigned"
            value={stats.unassigned}
            icon={<User className="h-4 w-4 text-amber-500" />}
            bg="bg-amber-50"
          />
          <StatCard
            label="Escalated"
            value={stats.escalated}
            icon={<AlertTriangle className="h-4 w-4 text-red-500" />}
            bg="bg-red-50"
          />
          <StatCard
            label="Resolved Today"
            value={stats.resolved_today}
            icon={<CheckCircle2 className="h-4 w-4 text-green-500" />}
            bg="bg-green-50"
          />
          <StatCard
            label="Avg Sentiment"
            value={
              stats.avg_sentiment_score !== null
                ? `${Math.round(stats.avg_sentiment_score * 100)}%`
                : "—"
            }
            icon={<BarChart3 className="h-4 w-4 text-purple-500" />}
            bg="bg-purple-50"
          />
        </div>
      )}

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

      {/* Main Content — Two-panel layout */}
      <div className="flex gap-6 flex-col lg:flex-row">
        {/* Left: Ticket Queue */}
        <div className="flex-1 min-w-0">
          {/* Filters */}
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <Filter className="h-4 w-4 text-slate-400" />
            <select
              data-testid="select-status-filter"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
            >
              <option value="open">Open</option>
              <option value="all">All</option>
              <option value="10">New</option>
              <option value="20">In Work</option>
              <option value="30">Resolved</option>
              <option value="50">Escalated</option>
            </select>
            <select
              data-testid="select-priority-filter"
              value={filterPriority}
              onChange={(e) => setFilterPriority(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
            >
              <option value="all">All Priorities</option>
              <option value="40">Urgent</option>
              <option value="30">High</option>
              <option value="20">Medium</option>
              <option value="10">Low</option>
            </select>
          </div>

          {/* Ticket List */}
          <div className="space-y-2">
            {loading ? (
              <div className="flex items-center justify-center py-12 text-sm text-slate-400">
                <Loader2 className="h-4 w-4 animate-spin mr-2" /> Loading tickets...
              </div>
            ) : tickets.length === 0 ? (
              <div className="rounded-xl bg-white p-8 text-center shadow-sm ring-1 ring-slate-100">
                <Inbox className="mx-auto h-8 w-8 text-slate-300 mb-2" />
                <p className="text-sm text-slate-500">No tickets found.</p>
              </div>
            ) : (
              tickets.map((ticket) => (
                <TicketRow
                  key={ticket.id}
                  ticket={ticket}
                  isSelected={selectedTicket?.id === ticket.id}
                  onClick={() => fetchTicketDetail(ticket.uuid)}
                />
              ))
            )}
          </div>
        </div>

        {/* Right: Ticket Detail Panel */}
        <div className="lg:w-[480px] shrink-0">
          {loadingDetail ? (
            <div className="rounded-xl bg-white p-8 shadow-sm ring-1 ring-slate-100 text-center">
              <Loader2 className="mx-auto h-6 w-6 animate-spin text-indigo-500" />
              <p className="mt-2 text-sm text-slate-400">Loading...</p>
            </div>
          ) : selectedTicket ? (
            <div className="rounded-xl bg-white shadow-sm ring-1 ring-slate-100 overflow-hidden sticky top-4">
              {/* Detail Header */}
              <div className="border-b border-slate-100 px-5 py-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">
                      #{selectedTicket.id} — {selectedTicket.subject || "No subject"}
                    </h3>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {selectedTicket.user_name} &middot;{" "}
                      {timeAgo(selectedTicket.created)}
                    </p>
                  </div>
                  <div className="flex gap-1.5">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_MAP[selectedTicket.status]?.bg} ${STATUS_MAP[selectedTicket.status]?.color}`}
                    >
                      {STATUS_MAP[selectedTicket.status]?.label}
                    </span>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${PRIORITY_MAP[selectedTicket.priority]?.bg} ${PRIORITY_MAP[selectedTicket.priority]?.color}`}
                    >
                      {PRIORITY_MAP[selectedTicket.priority]?.label}
                    </span>
                  </div>
                </div>
              </div>

              {/* Ticket Body */}
              <div className="px-5 py-4 border-b border-slate-100">
                <p className="text-sm text-slate-700 whitespace-pre-wrap">
                  {selectedTicket.text}
                </p>
              </div>

              {/* AI Insights */}
              {selectedTicket.ai_summary && (
                <div className="px-5 py-4 border-b border-slate-100 bg-indigo-50/50">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="h-4 w-4 text-indigo-500" />
                    <span className="text-xs font-semibold text-indigo-700">
                      AI Insights
                    </span>
                  </div>

                  <div className="space-y-2">
                    {/* Sentiment + Category */}
                    <div className="flex items-center gap-3">
                      {selectedTicket.sentiment && (
                        <span className="flex items-center gap-1">
                          {(() => {
                            const info = SENTIMENT_MAP[selectedTicket.sentiment];
                            if (!info) return null;
                            const Icon = info.icon;
                            return <Icon className={`h-3.5 w-3.5 ${info.color}`} />;
                          })()}
                          <span className="text-xs text-slate-600">
                            {selectedTicket.sentiment}
                            {selectedTicket.sentiment_score !== null &&
                              ` (${Math.round(selectedTicket.sentiment_score * 100)}%)`}
                          </span>
                        </span>
                      )}
                      {selectedTicket.ai_category && (
                        <span className="flex items-center gap-1">
                          {(() => {
                            const CatIcon =
                              CATEGORY_ICONS[selectedTicket.ai_category] ||
                              HelpCircle;
                            return (
                              <CatIcon className="h-3.5 w-3.5 text-slate-400" />
                            );
                          })()}
                          <span className="text-xs text-slate-600 capitalize">
                            {selectedTicket.ai_category}
                          </span>
                        </span>
                      )}
                    </div>

                    {/* Summary */}
                    <p className="text-xs text-slate-600">
                      {selectedTicket.ai_summary}
                    </p>
                  </div>
                </div>
              )}

              {/* Messages Thread */}
              {selectedTicket.messages && selectedTicket.messages.length > 0 && (
                <div className="px-5 py-4 border-b border-slate-100 max-h-48 overflow-y-auto">
                  <p className="text-xs font-semibold text-slate-500 mb-2">
                    Messages ({selectedTicket.messages.length})
                  </p>
                  <div className="space-y-2">
                    {selectedTicket.messages.map((msg) => (
                      <div
                        key={msg.id}
                        className="rounded-lg bg-slate-50 p-3"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-semibold text-slate-700">
                            {msg.user_name}
                          </span>
                          <span className="text-xs text-slate-400">
                            {timeAgo(msg.created)}
                          </span>
                        </div>
                        <p className="text-xs text-slate-600">{msg.text}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Reply / Resolve */}
              <div className="px-5 py-4 space-y-3">
                {/* Suggested response */}
                {selectedTicket.ai_suggested_response && (
                  <button
                    data-testid="button-use-suggested"
                    onClick={handleUseSuggested}
                    className="flex items-center gap-2 w-full rounded-lg bg-indigo-50 px-3 py-2 text-xs font-medium text-indigo-700 transition hover:bg-indigo-100"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    Use AI-suggested response
                  </button>
                )}

                <textarea
                  data-testid="textarea-reply"
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Type a reply..."
                  rows={3}
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-200 resize-none"
                />

                <div className="flex gap-2">
                  <button
                    data-testid="button-send-reply"
                    onClick={handleReply}
                    disabled={sending || !replyText.trim()}
                    className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {sending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                    Reply
                  </button>
                  <button
                    data-testid="button-resolve-ticket"
                    onClick={handleResolve}
                    disabled={resolving}
                    className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {resolving ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4" />
                    )}
                    Resolve
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-xl bg-white p-8 shadow-sm ring-1 ring-slate-100 text-center">
              <MessageSquare className="mx-auto h-8 w-8 text-slate-300 mb-2" />
              <p className="text-sm text-slate-500">
                Select a ticket to view details
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  icon,
  bg,
}: {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  bg: string;
}) {
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
      <div className="flex items-center gap-2 mb-2">
        <span
          className={`flex h-7 w-7 items-center justify-center rounded-lg ${bg}`}
        >
          {icon}
        </span>
        <span className="text-xs font-medium text-slate-500">{label}</span>
      </div>
      <p className="text-xl font-bold text-slate-900">{value}</p>
    </div>
  );
}

function TicketRow({
  ticket,
  isSelected,
  onClick,
}: {
  ticket: SupportTicket;
  isSelected: boolean;
  onClick: () => void;
}) {
  const statusInfo = STATUS_MAP[ticket.status];
  const priorityInfo = PRIORITY_MAP[ticket.priority];
  const sentimentInfo = ticket.sentiment
    ? SENTIMENT_MAP[ticket.sentiment]
    : null;

  return (
    <button
      data-testid={`ticket-row-${ticket.id}`}
      onClick={onClick}
      className={`w-full text-left rounded-xl bg-white p-4 shadow-sm ring-1 transition hover:ring-indigo-200 ${
        isSelected ? "ring-indigo-300 bg-indigo-50/30" : "ring-slate-100"
      }`}
    >
      <div className="flex items-start justify-between mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          {/* Priority indicator */}
          {ticket.priority >= 30 && (
            <ArrowUp
              className={`h-3.5 w-3.5 shrink-0 ${
                ticket.priority === 40 ? "text-red-500" : "text-amber-500"
              }`}
            />
          )}
          <span className="text-sm font-semibold text-slate-800 truncate">
            {ticket.subject || "No subject"}
          </span>
        </div>
        <span className="text-xs text-slate-400 shrink-0 ml-2">
          {timeAgo(ticket.created)}
        </span>
      </div>

      <p className="text-xs text-slate-500 line-clamp-2 mb-2">
        {ticket.ai_summary || ticket.text}
      </p>

      <div className="flex items-center gap-2 flex-wrap">
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${statusInfo?.bg} ${statusInfo?.color}`}
        >
          {statusInfo?.label}
        </span>
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${priorityInfo?.bg} ${priorityInfo?.color}`}
        >
          {priorityInfo?.label}
        </span>
        {ticket.ai_category && (
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500 capitalize">
            {ticket.ai_category}
          </span>
        )}
        {sentimentInfo && (
          <span className="flex items-center gap-0.5">
            {(() => {
              const Icon = sentimentInfo.icon;
              return <Icon className={`h-3 w-3 ${sentimentInfo.color}`} />;
            })()}
          </span>
        )}
        {ticket.ai_triaged_at && (
          <Sparkles className="h-3 w-3 text-indigo-400" />
        )}
        <span className="text-[10px] text-slate-400 ml-auto">
          {ticket.user_name}
        </span>
      </div>
    </button>
  );
}
