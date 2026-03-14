"use client";

import { useEffect, useState } from "react";
import {
  DollarSign,
  CalendarDays,
  TrendingUp,
  ArrowRight,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import { api } from "@/lib/api";
import { mockFinancialSummary } from "@/lib/mock-finance-data";

// ── Types ────────────────────────────────────────────────────────────

interface Booking {
  id: number;
  uuid: string;
  status: string;
  status_display: string;
  scheduled_date: string;
  scheduled_time: string;
  address?: string;
  service_type?: string;
  total_amount?: number;
  created: string;
}

interface BookingsResponse {
  results: Booking[];
  count: number;
}

// ── Helpers ──────────────────────────────────────────────────────────

function fmt(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(n);
}

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed:  "bg-green-50 text-green-700",
    confirmed:  "bg-blue-50 text-blue-700",
    pending:    "bg-amber-50 text-amber-700",
    cancelled:  "bg-red-50 text-red-700",
    in_progress:"bg-purple-50 text-purple-700",
  };
  const cls = map[status.toLowerCase()] ?? "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

function StatusIcon({ status }: { status: string }) {
  switch (status.toLowerCase()) {
    case "completed":
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case "cancelled":
      return <XCircle className="h-4 w-4 text-red-400" />;
    case "in_progress":
      return <Loader2 className="h-4 w-4 animate-spin text-purple-500" />;
    default:
      return <Clock className="h-4 w-4 text-amber-400" />;
  }
}

// ── Quick KPI Card ────────────────────────────────────────────────────

interface QuickKpiProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  iconBg: string;
}

function QuickKpi({ label, value, icon, iconBg }: QuickKpiProps) {
  return (
    <div className="flex items-center gap-4 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100">
      <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${iconBg}`}>
        {icon}
      </span>
      <div>
        <p className="text-xs font-medium text-slate-500">{label}</p>
        <p className="mt-0.5 text-xl font-bold text-slate-900">{value}</p>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────

export default function AgencyOwnerDashboard() {
  const { user } = useAuthStore();

  const [bookings, setBookings]     = useState<Booking[]>([]);
  const [loadingBk, setLoadingBk]   = useState(true);
  const [bookingError, setBookingError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchBookings() {
      try {
        const res = await api.get<BookingsResponse>("/bookings/?page_size=8&ordering=-created");
        setBookings(res?.results ?? []);
      } catch {
        setBookingError("Could not load recent bookings.");
      } finally {
        setLoadingBk(false);
      }
    }
    fetchBookings();
  }, []);

  const summary = mockFinancialSummary;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Welcome Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">
          Welcome back{user?.first_name ? `, ${user.first_name}` : ""}!
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Here's a quick glance at your agency performance.
        </p>
      </div>

      {/* Key Metrics */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <QuickKpi
          label="6-Month Revenue"
          value={fmt(summary.total_revenue)}
          icon={<DollarSign className="h-5 w-5 text-blue-600" />}
          iconBg="bg-blue-50"
        />
        <QuickKpi
          label="Net Profit"
          value={fmt(summary.total_profit)}
          icon={<TrendingUp className="h-5 w-5 text-green-600" />}
          iconBg="bg-green-50"
        />
        <QuickKpi
          label="Total Bookings"
          value={summary.total_bookings.toLocaleString()}
          icon={<CalendarDays className="h-5 w-5 text-purple-600" />}
          iconBg="bg-purple-50"
        />
      </div>

      {/* CTA → Full Dashboard */}
      <a
        href="/agency-owner/finances"
        className="mb-8 flex w-full items-center justify-between rounded-xl bg-blue-600 px-6 py-4 text-white shadow-sm transition hover:bg-blue-700"
      >
        <div>
          <p className="font-semibold">View Financial Dashboard</p>
          <p className="mt-0.5 text-xs text-blue-200">
            Revenue charts, regional breakdown, team performance &amp; Stripe settings
          </p>
        </div>
        <ArrowRight className="h-5 w-5 shrink-0" />
      </a>

      {/* Recent Bookings */}
      <div className="rounded-xl bg-white shadow-sm ring-1 ring-slate-100 overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <h2 className="text-sm font-semibold text-slate-800">Recent Bookings</h2>
          {!loadingBk && bookings.length > 0 && (
            <span className="text-xs text-slate-400">{bookings.length} shown</span>
          )}
        </div>

        {loadingBk && (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading bookings…
          </div>
        )}

        {!loadingBk && bookingError && (
          <div className="flex items-center gap-2 px-6 py-8 text-sm text-slate-500">
            <XCircle className="h-4 w-4 text-red-400 shrink-0" />
            {bookingError}
          </div>
        )}

        {!loadingBk && !bookingError && bookings.length === 0 && (
          <div className="px-6 py-10 text-center text-sm text-slate-400">
            No bookings found yet.
          </div>
        )}

        {!loadingBk && !bookingError && bookings.length > 0 && (
          <ul className="divide-y divide-slate-50">
            {bookings.map((b) => (
              <li
                key={b.id}
                className="flex items-center gap-4 px-6 py-3.5 transition hover:bg-slate-50"
              >
                <StatusIcon status={b.status} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-800">
                    {b.service_type ?? `Booking #${b.id}`}
                  </p>
                  <p className="text-xs text-slate-400">
                    {b.scheduled_date
                      ? formatDate(b.scheduled_date)
                      : formatDate(b.created)}
                    {b.address ? ` · ${b.address}` : ""}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  {b.total_amount != null && (
                    <span className="text-sm font-semibold text-slate-800">
                      {fmt(b.total_amount)}
                    </span>
                  )}
                  <StatusBadge status={b.status_display ?? b.status} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
