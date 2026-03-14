"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Calendar,
  MapPin,
  ChevronDown,
  ChevronUp,
  Loader2,
  AlertCircle,
  XCircle,
  CheckCircle2,
  Clock,
  ClipboardList,
  Plus,
  RefreshCw,
} from "lucide-react";

import { api } from "@/lib/api";
import type { Booking, BookingDetail } from "@/types/booking";

// ── Status helpers ────────────────────────────────────────────────────────────
const STATUS_META: Record<
  number,
  { label: string; bg: string; text: string; dot: string }
> = {
  10: {
    label: "New",
    bg: "bg-blue-50",
    text: "text-blue-700",
    dot: "bg-blue-500",
  },
  20: {
    label: "In Work",
    bg: "bg-yellow-50",
    text: "text-yellow-700",
    dot: "bg-yellow-500",
  },
  30: {
    label: "Completed",
    bg: "bg-green-50",
    text: "text-green-700",
    dot: "bg-green-500",
  },
  40: {
    label: "Cancelled",
    bg: "bg-red-50",
    text: "text-red-700",
    dot: "bg-red-400",
  },
};

const PAYMENT_META: Record<
  number,
  { label: string; bg: string; text: string }
> = {
  10: { label: "Pending", bg: "bg-gray-100", text: "text-gray-600" },
  20: { label: "Paid", bg: "bg-green-50", text: "text-green-700" },
  30: { label: "Failed", bg: "bg-red-50", text: "text-red-700" },
  40: { label: "Refunded", bg: "bg-purple-50", text: "text-purple-700" },
};

function StatusBadge({ status }: { status: number }) {
  const meta = STATUS_META[status] ?? {
    label: "Unknown",
    bg: "bg-gray-100",
    text: "text-gray-600",
    dot: "bg-gray-400",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${meta.bg} ${meta.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
      {meta.label}
    </span>
  );
}

function PaymentBadge({ status }: { status: number }) {
  const meta = PAYMENT_META[status] ?? {
    label: "Unknown",
    bg: "bg-gray-100",
    text: "text-gray-600",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${meta.bg} ${meta.text}`}
    >
      {meta.label}
    </span>
  );
}

// ── Booking row ───────────────────────────────────────────────────────────────
function BookingRow({ booking }: { booking: Booking }) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<BookingDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState("");
  const [cancelled, setCancelled] = useState(false);

  const currentStatus = cancelled ? 40 : booking.status;

  const handleExpand = async () => {
    if (!expanded && !detail) {
      setLoadingDetail(true);
      try {
        const d = await api.get<BookingDetail>(`/bookings/${booking.id}/`);
        setDetail(d);
      } catch {
        // swallow; detail stays null
      } finally {
        setLoadingDetail(false);
      }
    }
    setExpanded((prev) => !prev);
  };

  const handleCancel = async () => {
    if (
      !window.confirm(
        `Cancel booking #${booking.short_id}? This action cannot be undone.`,
      )
    )
      return;

    setCancelling(true);
    setCancelError("");
    try {
      await api.post(`/bookings/${booking.id}/cancel/`);
      setCancelled(true);
    } catch (err: unknown) {
      setCancelError(
        err instanceof Error ? err.message : "Failed to cancel booking.",
      );
    } finally {
      setCancelling(false);
    }
  };

  const formattedDate = booking.scheduled_date
    ? new Date(booking.scheduled_date + "T00:00:00").toLocaleDateString(
        "en-US",
        { weekday: "short", month: "short", day: "numeric", year: "numeric" },
      )
    : "—";

  const canCancel = currentStatus === 10 || currentStatus === 20;

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm transition-shadow hover:shadow">
      {/* Row header */}
      <button
        onClick={handleExpand}
        className="flex w-full items-start gap-4 p-4 text-left sm:items-center"
      >
        {/* Date */}
        <div className="flex w-28 shrink-0 flex-col items-center rounded-lg bg-blue-50 py-2 text-center">
          <Calendar className="mb-1 h-4 w-4 text-blue-500" />
          <span className="text-xs font-semibold text-blue-700">
            {formattedDate}
          </span>
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-gray-900">
              #{booking.short_id}
            </span>
            <StatusBadge status={currentStatus} />
            <PaymentBadge status={booking.payment_status} />
          </div>
          <p className="mt-1 flex items-center gap-1 truncate text-sm text-gray-500">
            <MapPin className="h-3.5 w-3.5 shrink-0" />
            {booking.place_address}
          </p>
          <p className="mt-0.5 flex items-center gap-1 text-xs text-gray-400">
            <ClipboardList className="h-3.5 w-3.5 shrink-0" />
            {booking.service_names}
          </p>
        </div>

        {/* Total + expand */}
        <div className="flex shrink-0 flex-col items-end gap-2">
          <span className="text-sm font-semibold text-gray-900">
            ${parseFloat(booking.total_fee_final).toFixed(2)}
          </span>
          <span className="text-gray-400">
            {expanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </span>
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-gray-100 bg-gray-50 px-4 pb-4 pt-3">
          {loadingDetail && (
            <div className="flex items-center gap-2 py-4 text-sm text-gray-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading details…
            </div>
          )}

          {!loadingDetail && detail && (
            <div className="space-y-4">
              {/* Details grid */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <DetailCell
                  icon={<Clock className="h-3.5 w-3.5" />}
                  label="Time"
                  value={booking.scheduled_range || "—"}
                />
                <DetailCell
                  icon={<RefreshCw className="h-3.5 w-3.5" />}
                  label="Frequency"
                  value={detail.regularity_type === 10 ? "One-time" : "Regular"}
                />
                <DetailCell
                  icon={<Calendar className="h-3.5 w-3.5" />}
                  label="Booked on"
                  value={new Date(detail.created).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                />
              </div>

              {/* Services */}
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
                  Services
                </p>
                <div className="space-y-1">
                  {detail.services.map((s) => (
                    <div
                      key={s.id}
                      className="flex items-center justify-between text-sm"
                    >
                      <span className="text-gray-700">{s.service_name}</span>
                      <span className="font-medium text-gray-900">
                        ${parseFloat(s.fee).toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Totals */}
              <div className="rounded-lg border border-gray-200 bg-white p-3">
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Subtotal</span>
                    <span>${parseFloat(detail.total_fee).toFixed(2)}</span>
                  </div>
                  {parseFloat(detail.discount_amount) > 0 && (
                    <div className="flex justify-between text-green-600">
                      <span>Discount</span>
                      <span>
                        −${parseFloat(detail.discount_amount).toFixed(2)}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between border-t border-gray-100 pt-1 font-semibold">
                    <span>Total</span>
                    <span>
                      ${parseFloat(detail.total_fee_final).toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Comments */}
              {(detail.comments || detail.special_request) && (
                <div className="space-y-2 text-sm text-gray-600">
                  {detail.comments && (
                    <p>
                      <span className="font-medium text-gray-700">
                        Comments:{" "}
                      </span>
                      {detail.comments}
                    </p>
                  )}
                  {detail.special_request && (
                    <p>
                      <span className="font-medium text-gray-700">
                        Special requests:{" "}
                      </span>
                      {detail.special_request}
                    </p>
                  )}
                </div>
              )}

              {/* Next cleaning */}
              {detail.next_cleaning && (
                <div className="flex items-center gap-2 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-blue-700">
                  <RefreshCw className="h-4 w-4 shrink-0" />
                  Next cleaning:{" "}
                  {new Date(
                    detail.next_cleaning.scheduled_date + "T00:00:00",
                  ).toLocaleDateString("en-US", {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                  })}{" "}
                  — {detail.next_cleaning.status_display}
                </div>
              )}

              {/* Cancel */}
              {canCancel && (
                <div>
                  {cancelError && (
                    <p className="mb-2 flex items-center gap-1.5 text-xs text-red-600">
                      <AlertCircle className="h-3.5 w-3.5" />
                      {cancelError}
                    </p>
                  )}
                  <button
                    onClick={handleCancel}
                    disabled={cancelling}
                    className="flex items-center gap-2 rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-600 transition hover:bg-red-50 disabled:opacity-50"
                  >
                    {cancelling ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <XCircle className="h-4 w-4" />
                    )}
                    {cancelling ? "Cancelling…" : "Cancel Booking"}
                  </button>
                </div>
              )}

              {cancelled && (
                <div className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                  <XCircle className="h-4 w-4" />
                  Booking cancelled.
                </div>
              )}
            </div>
          )}

          {!loadingDetail && !detail && (
            <p className="py-3 text-sm text-gray-400">
              Could not load booking details.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function DetailCell({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg bg-white p-2.5 text-sm">
      <p className="mb-0.5 flex items-center gap-1 text-xs text-gray-400">
        {icon}
        {label}
      </p>
      <p className="font-medium text-gray-900">{value}</p>
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────
function EmptyState() {
  return (
    <div className="py-16 text-center">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50">
        <ClipboardList className="h-8 w-8 text-blue-500" />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-gray-900">
        No bookings yet
      </h3>
      <p className="mt-1 text-sm text-gray-500">
        Your upcoming and past cleanings will appear here.
      </p>
      <a
        href="/resident/book"
        className="mt-6 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
      >
        <Plus className="h-4 w-4" />
        Book Your First Cleaning
      </a>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function BookingsPage() {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchBookings = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get<Booking[] | { results: Booking[] }>(
        "/bookings/",
      );
      setBookings(Array.isArray(data) ? data : data.results);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to load bookings.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBookings();
  }, [fetchBookings]);

  // Status filter
  const [filterStatus, setFilterStatus] = useState<number | null>(null);
  const filtered =
    filterStatus === null
      ? bookings
      : bookings.filter((b) => b.status === filterStatus);

  return (
    <div className="mx-auto max-w-3xl">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">My Bookings</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            {bookings.length} booking{bookings.length !== 1 ? "s" : ""} total
          </p>
        </div>
        <a
          href="/resident/book"
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          New Booking
        </a>
      </div>

      {/* Filters */}
      {!loading && !error && bookings.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          <button
            onClick={() => setFilterStatus(null)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
              filterStatus === null
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            All
          </button>
          {Object.entries(STATUS_META).map(([statusKey, meta]) => (
            <button
              key={statusKey}
              onClick={() => setFilterStatus(Number(statusKey))}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                filterStatus === Number(statusKey)
                  ? `${meta.bg} ${meta.text} ring-1 ring-current`
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${meta.dot}`}
              />
              {meta.label}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      )}

      {!loading && error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
            <div>
              <p className="text-sm font-medium text-red-700">{error}</p>
              <button
                onClick={fetchBookings}
                className="mt-2 text-sm text-red-600 hover:underline"
              >
                Try again
              </button>
            </div>
          </div>
        </div>
      )}

      {!loading && !error && bookings.length === 0 && <EmptyState />}

      {!loading && !error && filtered.length === 0 && bookings.length > 0 && (
        <div className="py-12 text-center">
          <CheckCircle2 className="mx-auto h-10 w-10 text-gray-300" />
          <p className="mt-3 text-sm text-gray-400">
            No bookings match this filter.
          </p>
          <button
            onClick={() => setFilterStatus(null)}
            className="mt-2 text-sm text-blue-600 hover:underline"
          >
            Show all
          </button>
        </div>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="space-y-3">
          {filtered.map((booking) => (
            <BookingRow key={booking.id} booking={booking} />
          ))}
        </div>
      )}
    </div>
  );
}
