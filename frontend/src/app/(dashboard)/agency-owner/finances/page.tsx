"use client";

import { useState, useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";
import {
  DollarSign,
  TrendingUp,
  CalendarDays,
  Percent,
  Receipt,
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  Star,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ArrowLeft,
} from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import { api } from "@/lib/api";
import {
  mockFinancialSummary,
  mockMonthlyRevenue,
  mockRevenueByRegion,
  mockCleanerPerformance,
} from "@/lib/mock-finance-data";
import type { CleaningPerformance } from "@/types/finance";

// ── Helpers ──────────────────────────────────────────────────────────

function fmt(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(n);
}

function fmtDecimal(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

function Stars({ score }: { score: number }) {
  const full  = Math.floor(score);
  const frac  = score - full;
  const empty = 5 - Math.ceil(score);
  return (
    <span className="flex items-center gap-0.5">
      {Array.from({ length: full }).map((_, i) => (
        <Star key={`f${i}`} className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
      ))}
      {frac >= 0.5 && (
        <Star key="half" className="h-3.5 w-3.5 fill-amber-200 text-amber-400" />
      )}
      {Array.from({ length: empty }).map((_, i) => (
        <Star key={`e${i}`} className="h-3.5 w-3.5 fill-none text-slate-300" />
      ))}
      <span className="ml-1 text-xs text-slate-500">{score.toFixed(1)}</span>
    </span>
  );
}

type SortKey = keyof CleaningPerformance;
type SortDir = "asc" | "desc";

// ── KPI Card ─────────────────────────────────────────────────────────

interface KpiCardProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  sub?: string;
  accent?: string;
}

function KpiCard({ label, value, icon, sub, accent = "blue" }: KpiCardProps) {
  const accentMap: Record<string, string> = {
    blue:   "bg-blue-50 text-blue-600",
    green:  "bg-green-50 text-green-600",
    purple: "bg-purple-50 text-purple-600",
    amber:  "bg-amber-50 text-amber-600",
    teal:   "bg-teal-50 text-teal-600",
  };
  const iconCls = accentMap[accent] ?? accentMap["blue"];

  return (
    <div className="flex flex-col gap-3 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
          {label}
        </span>
        <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${iconCls}`}>
          {icon}
        </span>
      </div>
      <p className="text-2xl font-bold text-slate-900">{value}</p>
      {sub && <p className="text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

// ── Custom Tooltip ────────────────────────────────────────────────────

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-100 bg-white px-3 py-2 shadow-lg">
      <p className="mb-1 text-xs font-semibold text-slate-600">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="text-xs" style={{ color: p.color }}>
          {p.name}: {fmt(p.value)}
        </p>
      ))}
    </div>
  );
}

// ── Stripe Connect Section ────────────────────────────────────────────

function StripeSection({ stripeAccountId }: { stripeAccountId: string | null }) {
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  async function handleConnect() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.post<{ url: string }>("/stripe/connect/");
      if (res?.url) window.location.href = res.url;
    } catch {
      setError("Could not initiate Stripe Connect. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-100">
      <h3 className="mb-4 text-sm font-semibold text-slate-800">Stripe Connect</h3>
      {stripeAccountId ? (
        <div className="flex items-start gap-3">
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-green-500" />
          <div>
            <p className="text-sm font-medium text-slate-800">Account linked</p>
            <p className="mt-0.5 text-xs text-slate-500 font-mono">{stripeAccountId}</p>
            <p className="mt-1 text-xs text-slate-400">
              Payouts and payments are processing normally.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
          <div className="flex-1">
            <p className="text-sm font-medium text-slate-800">No Stripe account connected</p>
            <p className="mt-0.5 text-xs text-slate-500">
              Connect your Stripe account to receive payouts and manage payments.
            </p>
            {error && (
              <p className="mt-2 text-xs text-red-500">{error}</p>
            )}
            <button
              onClick={handleConnect}
              disabled={loading}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:opacity-60"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              {loading ? "Redirecting…" : "Connect with Stripe"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────

type Tab = "overview" | "revenue" | "team" | "settings";

export default function FinancesPage() {
  const { user } = useAuthStore();
  const [tab, setTab]   = useState<Tab>("overview");

  // Cleaner table sort state
  const [sortKey, setSortKey] = useState<SortKey>("revenue_generated");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const summary = mockFinancialSummary;

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const sortedCleaners = useMemo(() => {
    return [...mockCleanerPerformance].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc"
          ? av.localeCompare(bv)
          : bv.localeCompare(av);
      }
      return sortDir === "asc"
        ? (av as number) - (bv as number)
        : (bv as number) - (av as number);
    });
  }, [sortKey, sortDir]);

  function SortIcon({ k }: { k: SortKey }) {
    if (sortKey !== k) return <ChevronsUpDown className="inline h-3.5 w-3.5 text-slate-300" />;
    return sortDir === "asc"
      ? <ChevronUp className="inline h-3.5 w-3.5 text-blue-600" />
      : <ChevronDown className="inline h-3.5 w-3.5 text-blue-600" />;
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "revenue",  label: "Revenue"  },
    { key: "team",     label: "Team"     },
    { key: "settings", label: "Settings" },
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Page Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <a
            href="/agency-owner"
            className="mb-1 inline-flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Dashboard
          </a>
          <h1 className="text-xl font-bold text-slate-900">Financial Dashboard</h1>
          {user && (
            <p className="mt-0.5 text-sm text-slate-500">
              Welcome back, {user.first_name} — here's your agency performance overview.
            </p>
          )}
        </div>
        <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
          Last 6 months
        </span>
      </div>

      {/* Tab Navigation */}
      <div className="mb-6 flex gap-1 rounded-xl bg-white p-1 shadow-sm ring-1 ring-slate-100 w-fit">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
              tab === t.key
                ? "bg-blue-600 text-white shadow-sm"
                : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW TAB ────────────────────────────────────────────── */}
      {tab === "overview" && (
        <div className="space-y-6">
          {/* KPI Cards */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <KpiCard
              label="Total Revenue"
              value={fmt(summary.total_revenue)}
              icon={<DollarSign className="h-4 w-4" />}
              sub="Past 6 months"
              accent="blue"
            />
            <KpiCard
              label="Total Profit"
              value={fmt(summary.total_profit)}
              icon={<TrendingUp className="h-4 w-4" />}
              sub={`Costs: ${fmt(summary.total_costs)}`}
              accent="green"
            />
            <KpiCard
              label="Total Bookings"
              value={summary.total_bookings.toLocaleString()}
              icon={<CalendarDays className="h-4 w-4" />}
              sub="Across all regions"
              accent="purple"
            />
            <KpiCard
              label="Profit Margin"
              value={`${summary.profit_margin.toFixed(1)}%`}
              icon={<Percent className="h-4 w-4" />}
              sub="Revenue − Costs"
              accent="teal"
            />
            <KpiCard
              label="Avg Booking Value"
              value={fmtDecimal(summary.avg_booking_value)}
              icon={<Receipt className="h-4 w-4" />}
              sub="Per completed booking"
              accent="amber"
            />
          </div>

          {/* Charts row */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Revenue by Region */}
            <div className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-100">
              <h3 className="mb-4 text-sm font-semibold text-slate-800">Revenue by Region</h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart
                  data={mockRevenueByRegion}
                  layout="vertical"
                  margin={{ top: 0, right: 16, left: 8, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                  <XAxis
                    type="number"
                    tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="region"
                    width={110}
                    tick={{ fontSize: 11, fill: "#64748b" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Legend
                    wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                    iconType="circle"
                    iconSize={8}
                  />
                  <Bar dataKey="revenue" name="Revenue" fill="#2563eb" radius={[0, 4, 4, 0]} />
                  <Bar dataKey="profit"  name="Profit"  fill="#22c55e" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Monthly Trend */}
            <div className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-100">
              <h3 className="mb-4 text-sm font-semibold text-slate-800">Monthly Revenue Trend</h3>
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart
                  data={mockMonthlyRevenue}
                  margin={{ top: 4, right: 16, left: 0, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="gradRevenue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#2563eb" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#2563eb" stopOpacity={0}    />
                    </linearGradient>
                    <linearGradient id="gradCosts" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.12} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0}    />
                    </linearGradient>
                    <linearGradient id="gradProfit" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#22c55e" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0}    />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="month"
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                    tick={{ fontSize: 11, fill: "#94a3b8" }}
                    axisLine={false}
                    tickLine={false}
                    width={44}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Legend
                    wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                    iconType="circle"
                    iconSize={8}
                  />
                  <Area
                    type="monotone"
                    dataKey="revenue"
                    name="Revenue"
                    stroke="#2563eb"
                    strokeWidth={2}
                    fill="url(#gradRevenue)"
                  />
                  <Area
                    type="monotone"
                    dataKey="costs"
                    name="Costs"
                    stroke="#ef4444"
                    strokeWidth={2}
                    fill="url(#gradCosts)"
                  />
                  <Area
                    type="monotone"
                    dataKey="profit"
                    name="Profit"
                    stroke="#22c55e"
                    strokeWidth={2}
                    fill="url(#gradProfit)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Stripe Connect */}
          <StripeSection stripeAccountId={null} />
        </div>
      )}

      {/* ── REVENUE TAB ─────────────────────────────────────────────── */}
      {tab === "revenue" && (
        <div className="space-y-6">
          {/* Summary row */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <KpiCard
              label="Total Revenue"
              value={fmt(summary.total_revenue)}
              icon={<DollarSign className="h-4 w-4" />}
              accent="blue"
            />
            <KpiCard
              label="Total Costs"
              value={fmt(summary.total_costs)}
              icon={<Receipt className="h-4 w-4" />}
              accent="amber"
            />
            <KpiCard
              label="Net Profit"
              value={fmt(summary.total_profit)}
              icon={<TrendingUp className="h-4 w-4" />}
              sub={`${summary.profit_margin.toFixed(1)}% margin`}
              accent="green"
            />
          </div>

          {/* Full-width monthly area chart */}
          <div className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-100">
            <h3 className="mb-4 text-sm font-semibold text-slate-800">
              Monthly Revenue vs Costs vs Profit
            </h3>
            <ResponsiveContainer width="100%" height={320}>
              <AreaChart
                data={mockMonthlyRevenue}
                margin={{ top: 4, right: 16, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="gr2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#2563eb" stopOpacity={0.18} />
                    <stop offset="95%" stopColor="#2563eb" stopOpacity={0}    />
                  </linearGradient>
                  <linearGradient id="gc2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.14} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0}    />
                  </linearGradient>
                  <linearGradient id="gp2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#22c55e" stopOpacity={0.18} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0}    />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 11, fill: "#94a3b8" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                  tick={{ fontSize: 11, fill: "#94a3b8" }}
                  axisLine={false}
                  tickLine={false}
                  width={44}
                />
                <Tooltip content={<ChartTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: 12, paddingTop: 12 }}
                  iconType="circle"
                  iconSize={8}
                />
                <Area type="monotone" dataKey="revenue" name="Revenue" stroke="#2563eb" strokeWidth={2} fill="url(#gr2)" />
                <Area type="monotone" dataKey="costs"   name="Costs"   stroke="#ef4444" strokeWidth={2} fill="url(#gc2)" />
                <Area type="monotone" dataKey="profit"  name="Profit"  stroke="#22c55e" strokeWidth={2} fill="url(#gp2)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Region bar chart full-width */}
          <div className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-100">
            <h3 className="mb-4 text-sm font-semibold text-slate-800">Revenue & Profit by Region</h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart
                data={mockRevenueByRegion}
                layout="vertical"
                margin={{ top: 0, right: 16, left: 8, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                <XAxis
                  type="number"
                  tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                  tick={{ fontSize: 11, fill: "#94a3b8" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="region"
                  width={120}
                  tick={{ fontSize: 11, fill: "#64748b" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} iconType="circle" iconSize={8} />
                <Bar dataKey="revenue" name="Revenue" fill="#2563eb" radius={[0, 4, 4, 0]} />
                <Bar dataKey="profit"  name="Profit"  fill="#22c55e" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── TEAM TAB ────────────────────────────────────────────────── */}
      {tab === "team" && (
        <div className="space-y-4">
          <div className="rounded-xl bg-white shadow-sm ring-1 ring-slate-100 overflow-hidden">
            <div className="border-b border-slate-100 px-6 py-4">
              <h3 className="text-sm font-semibold text-slate-800">Cleaner Performance</h3>
              <p className="mt-0.5 text-xs text-slate-400">
                Click a column header to sort. Showing last 6 months.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50">
                    {(
                      [
                        { key: "cleaner_name",      label: "Cleaner"          },
                        { key: "completed",          label: "Completed"        },
                        { key: "avg_score",          label: "Avg Score"        },
                        { key: "revenue_generated",  label: "Revenue Generated"},
                      ] as { key: SortKey; label: string }[]
                    ).map(({ key, label }) => (
                      <th
                        key={key}
                        onClick={() => handleSort(key)}
                        className="cursor-pointer px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-700 select-none"
                      >
                        {label} <SortIcon k={key} />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {sortedCleaners.map((c, i) => (
                    <tr
                      key={c.cleaner_name}
                      className="transition hover:bg-slate-50"
                    >
                      <td className="px-6 py-3.5 font-medium text-slate-800">
                        <span className="mr-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-blue-50 text-xs font-bold text-blue-600">
                          {i + 1}
                        </span>
                        {c.cleaner_name}
                      </td>
                      <td className="px-6 py-3.5 text-slate-600">{c.completed}</td>
                      <td className="px-6 py-3.5">
                        <Stars score={c.avg_score} />
                      </td>
                      <td className="px-6 py-3.5 font-medium text-slate-800">
                        {fmt(c.revenue_generated)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Team summary KPIs */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <KpiCard
              label="Active Cleaners"
              value={mockCleanerPerformance.length.toString()}
              icon={<CalendarDays className="h-4 w-4" />}
              accent="purple"
            />
            <KpiCard
              label="Total Cleanings"
              value={mockCleanerPerformance.reduce((s, c) => s + c.completed, 0).toString()}
              icon={<CheckCircle2 className="h-4 w-4" />}
              accent="green"
            />
            <KpiCard
              label="Avg Team Score"
              value={(
                mockCleanerPerformance.reduce((s, c) => s + c.avg_score, 0) /
                mockCleanerPerformance.length
              ).toFixed(2)}
              icon={<Star className="h-4 w-4" />}
              accent="amber"
            />
          </div>
        </div>
      )}

      {/* ── SETTINGS TAB ────────────────────────────────────────────── */}
      {tab === "settings" && (
        <div className="space-y-6">
          <StripeSection stripeAccountId={null} />

          <div className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-100">
            <h3 className="mb-4 text-sm font-semibold text-slate-800">Payout Settings</h3>
            <p className="text-sm text-slate-500">
              Configure your payout schedule and bank account details through the Stripe dashboard
              after connecting your account.
            </p>
          </div>

          <div className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-100">
            <h3 className="mb-4 text-sm font-semibold text-slate-800">Notification Preferences</h3>
            <div className="space-y-3">
              {[
                "Weekly revenue summary email",
                "Payout confirmation alerts",
                "Low-balance warnings",
              ].map((label) => (
                <label key={label} className="flex items-center gap-3 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    defaultChecked
                    className="h-4 w-4 rounded border-slate-300 accent-blue-600"
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
