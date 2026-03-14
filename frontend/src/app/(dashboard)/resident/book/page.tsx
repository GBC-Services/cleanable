"use client";

import "mapbox-gl/dist/mapbox-gl.css";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  MapPin,
  Calendar,
  CreditCard,
  CheckCircle,
  ClipboardList,
  Home,
  Plus,
  Loader2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  X,
  Bed,
  Bath,
  Ruler,
  Tag,
  Clock,
  RotateCcw,
} from "lucide-react";
import { loadStripe } from "@stripe/stripe-js";
import {
  Elements,
  CardElement,
  useStripe,
  useElements,
} from "@stripe/react-stripe-js";

import { api } from "@/lib/api";
import { useBookingStore } from "@/lib/booking-store";
import type { Place, ServiceFee, BookingDetail } from "@/types/booking";

// ── Stripe setup ──────────────────────────────────────────────────────────────
const stripePromise = loadStripe(
  process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY ?? "",
);

// ── Stepper component ─────────────────────────────────────────────────────────
const STEPS = [
  { label: "Place", icon: MapPin },
  { label: "Services", icon: ClipboardList },
  { label: "Schedule", icon: Calendar },
  { label: "Review", icon: CheckCircle },
  { label: "Payment", icon: CreditCard },
];

function Stepper({ current }: { current: number }) {
  return (
    <div className="mb-8">
      <div className="flex items-center justify-between">
        {STEPS.map((step, index) => {
          const stepNum = index + 1;
          const done = stepNum < current;
          const active = stepNum === current;
          const Icon = step.icon;

          return (
            <div key={step.label} className="flex flex-1 items-center">
              <div className="flex flex-col items-center">
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all ${
                    done
                      ? "border-blue-600 bg-blue-600 text-white"
                      : active
                        ? "border-blue-600 bg-white text-blue-600"
                        : "border-gray-300 bg-white text-gray-400"
                  }`}
                >
                  {done ? (
                    <CheckCircle className="h-5 w-5" />
                  ) : (
                    <Icon className="h-5 w-5" />
                  )}
                </div>
                <span
                  className={`mt-1 hidden text-xs font-medium sm:block ${
                    active
                      ? "text-blue-600"
                      : done
                        ? "text-blue-500"
                        : "text-gray-400"
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {index < STEPS.length - 1 && (
                <div
                  className={`mx-1 h-0.5 flex-1 transition-all ${
                    stepNum < current ? "bg-blue-600" : "bg-gray-200"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Nav buttons ───────────────────────────────────────────────────────────────
function NavButtons({
  onPrev,
  onNext,
  nextLabel = "Continue",
  prevDisabled = false,
  nextDisabled = false,
  loading = false,
}: {
  onPrev?: () => void;
  onNext?: () => void;
  nextLabel?: string;
  prevDisabled?: boolean;
  nextDisabled?: boolean;
  loading?: boolean;
}) {
  return (
    <div className="mt-8 flex justify-between gap-3 border-t border-gray-100 pt-6">
      {onPrev ? (
        <button
          onClick={onPrev}
          disabled={prevDisabled}
          className="flex items-center gap-2 rounded-lg border border-gray-300 px-5 py-2.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
        >
          <ChevronLeft className="h-4 w-4" />
          Back
        </button>
      ) : (
        <div />
      )}
      {onNext && (
        <button
          onClick={onNext}
          disabled={nextDisabled || loading}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          {nextLabel}
          {!loading && <ChevronRight className="h-4 w-4" />}
        </button>
      )}
    </div>
  );
}

// ── Error banner ──────────────────────────────────────────────────────────────
function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

// ── STEP 1: Select Place ──────────────────────────────────────────────────────
function PlaceCard({
  place,
  selected,
  onSelect,
}: {
  place: Place;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`w-full rounded-xl border-2 p-4 text-left transition-all ${
        selected
          ? "border-blue-600 bg-blue-50"
          : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div
            className={`mt-0.5 rounded-lg p-2 ${selected ? "bg-blue-100" : "bg-gray-100"}`}
          >
            <Home
              className={`h-4 w-4 ${selected ? "text-blue-600" : "text-gray-500"}`}
            />
          </div>
          <div className="min-w-0">
            <p className="font-medium text-gray-900">{place.full_address}</p>
            <p className="mt-0.5 text-sm text-gray-500">{place.type_display}</p>
            <div className="mt-2 flex flex-wrap gap-3 text-xs text-gray-500">
              {place.bedrooms_nmb !== null && (
                <span className="flex items-center gap-1">
                  <Bed className="h-3.5 w-3.5" />
                  {place.bedrooms_nmb} bed{place.bedrooms_nmb !== 1 ? "s" : ""}
                </span>
              )}
              {place.bathrooms_nmb !== null && (
                <span className="flex items-center gap-1">
                  <Bath className="h-3.5 w-3.5" />
                  {place.bathrooms_nmb} bath
                  {place.bathrooms_nmb !== 1 ? "s" : ""}
                </span>
              )}
              {place.area_size !== null && (
                <span className="flex items-center gap-1">
                  <Ruler className="h-3.5 w-3.5" />
                  {place.area_size} sq ft
                </span>
              )}
            </div>
          </div>
        </div>
        {selected && (
          <CheckCircle className="h-5 w-5 shrink-0 text-blue-600" />
        )}
      </div>
    </button>
  );
}

// Inline AddPlace form with Mapbox Geocoder
function AddPlaceForm({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: (place: Place) => void;
}) {
  const geocoderRef = useRef<HTMLDivElement>(null);
  const [address, setAddress] = useState("");
  const [aptNmb, setAptNmb] = useState("");
  const [placeType, setPlaceType] = useState<number>(10);
  const [bedrooms, setBedrooms] = useState("");
  const [bathrooms, setBathrooms] = useState("");
  const [areaSize, setAreaSize] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!geocoderRef.current) return;

    const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
    if (!token) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let geocoder: any;

    const load = async () => {
      const mapboxgl = (await import("mapbox-gl")).default;
      const MapboxGeocoder = (await import("@mapbox/mapbox-gl-geocoder"))
        .default;

      mapboxgl.accessToken = token;

      geocoder = new MapboxGeocoder({
        accessToken: token,
        types: "address",
        countries: "us",
        placeholder: "Search for an address…",
      });

      if (geocoderRef.current) {
        geocoder.addTo(geocoderRef.current);
      }

      geocoder.on("result", (e: { result: { place_name: string } }) => {
        setAddress(e.result.place_name);
      });

      geocoder.on("clear", () => {
        setAddress("");
      });
    };

    load();

    return () => {
      try {
        geocoder?.onRemove?.();
      } catch (_) {
        // ignore cleanup errors
      }
    };
  }, []);

  const handleSubmit = async () => {
    if (!address) {
      setError("Please select an address using the search box.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, unknown> = {
        address,
        apartment_nmb: aptNmb,
        type: placeType,
      };
      if (bedrooms) payload.bedrooms_nmb = parseInt(bedrooms, 10);
      if (bathrooms) payload.bathrooms_nmb = parseInt(bathrooms, 10);
      if (areaSize) payload.area_size = parseFloat(areaSize);

      const created = await api.post<Place>("/places/", payload);
      onCreated(created);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to create place.";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Add a new property</h3>
        <button
          onClick={onCancel}
          className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-gray-700">
            Address *
          </label>
          <div ref={geocoderRef} className="mapbox-geocoder-wrapper" />
          {address && (
            <p className="mt-1 text-xs text-gray-500">Selected: {address}</p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">
              Unit / Apt #
            </label>
            <input
              type="text"
              value={aptNmb}
              onChange={(e) => setAptNmb(e.target.value)}
              placeholder="e.g. Apt 2B"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">
              Property type
            </label>
            <select
              value={placeType}
              onChange={(e) => setPlaceType(Number(e.target.value))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value={10}>Apartment</option>
              <option value={20}>House</option>
              <option value={30}>Condo</option>
              <option value={40}>Studio</option>
              <option value={50}>Office</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">
              Bedrooms
            </label>
            <input
              type="number"
              min="0"
              value={bedrooms}
              onChange={(e) => setBedrooms(e.target.value)}
              placeholder="0"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">
              Bathrooms
            </label>
            <input
              type="number"
              min="0"
              value={bathrooms}
              onChange={(e) => setBathrooms(e.target.value)}
              placeholder="0"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">
              Area (sq ft)
            </label>
            <input
              type="number"
              min="0"
              value={areaSize}
              onChange={(e) => setAreaSize(e.target.value)}
              placeholder="0"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      <div className="mt-5 flex justify-end gap-3">
        <button
          onClick={onCancel}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={saving}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {saving && <Loader2 className="h-4 w-4 animate-spin" />}
          Save Property
        </button>
      </div>
    </div>
  );
}

function Step1Place() {
  const { selectedPlace, setPlace, nextStep } = useBookingStore();
  const [places, setPlaces] = useState<Place[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);

  const fetchPlaces = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get<Place[] | { results: Place[] }>("/places/");
      setPlaces(Array.isArray(data) ? data : data.results);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load places.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPlaces();
  }, [fetchPlaces]);

  return (
    <div>
      <h2 className="mb-1 text-xl font-semibold text-gray-900">
        Select your property
      </h2>
      <p className="mb-6 text-sm text-gray-500">
        Choose the property you want cleaned, or add a new one.
      </p>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
        </div>
      )}

      {!loading && error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}

      {!loading && !error && (
        <div className="space-y-3">
          {places.map((place) => (
            <PlaceCard
              key={place.id}
              place={place}
              selected={selectedPlace?.id === place.id}
              onSelect={() => setPlace(place)}
            />
          ))}

          {places.length === 0 && !showAddForm && (
            <p className="py-8 text-center text-sm text-gray-400">
              No properties found. Add one below.
            </p>
          )}

          {!showAddForm && (
            <button
              onClick={() => setShowAddForm(true)}
              className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-gray-300 py-4 text-sm font-medium text-gray-500 transition hover:border-blue-400 hover:text-blue-600"
            >
              <Plus className="h-4 w-4" />
              Add New Property
            </button>
          )}

          {showAddForm && (
            <AddPlaceForm
              onCancel={() => setShowAddForm(false)}
              onCreated={(place) => {
                setPlaces((prev) => [...prev, place]);
                setPlace(place);
                setShowAddForm(false);
              }}
            />
          )}
        </div>
      )}

      <NavButtons
        onNext={nextStep}
        nextDisabled={!selectedPlace}
      />
    </div>
  );
}

// ── STEP 2: Select Services ───────────────────────────────────────────────────
function ServiceFeeCard({
  fee,
  selected,
  onToggle,
  areaSize,
}: {
  fee: ServiceFee;
  selected: boolean;
  onToggle: () => void;
  areaSize: number | null;
}) {
  const baseFee = parseFloat(fee.client_fee) || 0;
  const displayFee =
    fee.is_area_based && areaSize
      ? `$${(baseFee * areaSize).toFixed(2)}`
      : `$${baseFee.toFixed(2)}`;

  return (
    <button
      onClick={onToggle}
      className={`w-full rounded-xl border-2 p-4 text-left transition-all ${
        selected
          ? "border-blue-600 bg-blue-50"
          : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div
            className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border-2 transition ${
              selected ? "border-blue-600 bg-blue-600" : "border-gray-300"
            }`}
          >
            {selected && (
              <CheckCircle className="h-3.5 w-3.5 text-white" />
            )}
          </div>
          <div className="min-w-0">
            <p className="font-medium text-gray-900">{fee.service_name}</p>
            {fee.is_area_based && (
              <p className="mt-0.5 flex items-center gap-1 text-xs text-gray-500">
                <Ruler className="h-3 w-3" />
                Area-based pricing
                {areaSize ? ` (${areaSize} sq ft)` : ""}
              </p>
            )}
          </div>
        </div>
        <span className="shrink-0 font-semibold text-gray-900">
          {displayFee}
          {fee.is_area_based && (
            <span className="text-xs font-normal text-gray-500">
              {areaSize ? "" : "/sq ft"}
            </span>
          )}
        </span>
      </div>
    </button>
  );
}

function Step2Services() {
  const {
    selectedPlace,
    selectedServiceFees,
    toggleServiceFee,
    nextStep,
    prevStep,
    computeTotalFee,
  } = useBookingStore();
  const [fees, setFees] = useState<ServiceFee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const regionParam = selectedPlace?.region
      ? `?region=${selectedPlace.region}`
      : "";
    api
      .get<ServiceFee[] | { results: ServiceFee[] }>(`/services/fees/${regionParam}`)
      .then((data) => {
        setFees(Array.isArray(data) ? data : data.results);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load services.",
        );
      })
      .finally(() => setLoading(false));
  }, [selectedPlace?.region]);

  const total = computeTotalFee();

  return (
    <div>
      <h2 className="mb-1 text-xl font-semibold text-gray-900">
        Choose services
      </h2>
      <p className="mb-6 text-sm text-gray-500">
        Select all cleaning services you need.
      </p>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
        </div>
      )}

      {!loading && error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}

      {!loading && !error && (
        <div className="space-y-3">
          {fees.length === 0 && (
            <p className="py-8 text-center text-sm text-gray-400">
              No services available for this region.
            </p>
          )}
          {fees.map((fee) => (
            <ServiceFeeCard
              key={fee.id}
              fee={fee}
              selected={selectedServiceFees.some((f) => f.id === fee.id)}
              onToggle={() => toggleServiceFee(fee)}
              areaSize={selectedPlace?.area_size ?? null}
            />
          ))}
        </div>
      )}

      {selectedServiceFees.length > 0 && (
        <div className="mt-4 flex items-center justify-between rounded-lg bg-blue-50 px-4 py-3">
          <span className="text-sm font-medium text-blue-900">
            {selectedServiceFees.length} service
            {selectedServiceFees.length !== 1 ? "s" : ""} selected
          </span>
          <span className="font-semibold text-blue-900">
            ${total.toFixed(2)}
          </span>
        </div>
      )}

      <NavButtons
        onPrev={prevStep}
        onNext={nextStep}
        nextDisabled={selectedServiceFees.length === 0}
      />
    </div>
  );
}

// ── STEP 3: Schedule ──────────────────────────────────────────────────────────
function Step3Schedule() {
  const {
    scheduledDate,
    scheduledStartTime,
    scheduledEndTime,
    regularityType,
    regularityOption,
    setSchedule,
    nextStep,
    prevStep,
  } = useBookingStore();

  const today = new Date().toISOString().split("T")[0];

  const isValid =
    scheduledDate &&
    scheduledStartTime &&
    scheduledEndTime &&
    scheduledStartTime < scheduledEndTime;

  return (
    <div>
      <h2 className="mb-1 text-xl font-semibold text-gray-900">
        Schedule your cleaning
      </h2>
      <p className="mb-6 text-sm text-gray-500">
        Pick a date, time window, and cleaning frequency.
      </p>

      <div className="space-y-5">
        {/* Date */}
        <div>
          <label className="mb-1.5 flex items-center gap-2 text-sm font-medium text-gray-700">
            <Calendar className="h-4 w-4 text-gray-400" />
            Date
          </label>
          <input
            type="date"
            min={today}
            value={scheduledDate}
            onChange={(e) => setSchedule({ date: e.target.value })}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 sm:max-w-xs"
          />
        </div>

        {/* Time range */}
        <div>
          <label className="mb-1.5 flex items-center gap-2 text-sm font-medium text-gray-700">
            <Clock className="h-4 w-4 text-gray-400" />
            Time window
          </label>
          <div className="flex items-center gap-3">
            <input
              type="time"
              value={scheduledStartTime}
              onChange={(e) => setSchedule({ startTime: e.target.value })}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <span className="text-gray-400">—</span>
            <input
              type="time"
              value={scheduledEndTime}
              onChange={(e) => setSchedule({ endTime: e.target.value })}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          {scheduledStartTime &&
            scheduledEndTime &&
            scheduledStartTime >= scheduledEndTime && (
              <p className="mt-1 text-xs text-red-500">
                End time must be after start time.
              </p>
            )}
        </div>

        {/* Regularity */}
        <div>
          <label className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-700">
            <RotateCcw className="h-4 w-4 text-gray-400" />
            Frequency
          </label>
          <div className="flex gap-3">
            {[
              { value: 10, label: "One-time" },
              { value: 20, label: "Regular" },
            ].map((opt) => (
              <button
                key={opt.value}
                onClick={() =>
                  setSchedule({ regularityType: opt.value, regularityOption: null })
                }
                className={`flex-1 rounded-lg border-2 py-3 text-sm font-medium transition ${
                  regularityType === opt.value
                    ? "border-blue-600 bg-blue-50 text-blue-700"
                    : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Regular options */}
        {regularityType === 20 && (
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Repeat every
            </label>
            <div className="flex gap-3">
              {[
                { value: 10, label: "Weekly" },
                { value: 20, label: "Bi-weekly" },
                { value: 30, label: "Monthly" },
              ].map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setSchedule({ regularityOption: opt.value })}
                  className={`flex-1 rounded-lg border-2 py-2.5 text-sm font-medium transition ${
                    regularityOption === opt.value
                      ? "border-blue-600 bg-blue-50 text-blue-700"
                      : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {!regularityOption && (
              <p className="mt-1.5 text-xs text-amber-600">
                Please select a repeat interval.
              </p>
            )}
          </div>
        )}
      </div>

      <NavButtons
        onPrev={prevStep}
        onNext={nextStep}
        nextDisabled={
          !isValid ||
          (regularityType === 20 && !regularityOption)
        }
      />
    </div>
  );
}

// ── STEP 4: Review & Details ──────────────────────────────────────────────────
function SummaryRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-2.5 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="text-right font-medium text-gray-900">{value}</span>
    </div>
  );
}

function Step4Review() {
  const {
    selectedPlace,
    selectedServiceFees,
    scheduledDate,
    scheduledStartTime,
    scheduledEndTime,
    regularityType,
    regularityOption,
    comments,
    specialRequest,
    discountCode,
    setDetails,
    nextStep,
    prevStep,
    computeTotalFee,
  } = useBookingStore();

  const total = computeTotalFee();

  const regularityLabel =
    regularityType === 10
      ? "One-time"
      : regularityOption === 10
        ? "Weekly"
        : regularityOption === 20
          ? "Bi-weekly"
          : regularityOption === 30
            ? "Monthly"
            : "Regular";

  return (
    <div>
      <h2 className="mb-1 text-xl font-semibold text-gray-900">
        Review your booking
      </h2>
      <p className="mb-6 text-sm text-gray-500">
        Confirm the details and add any special instructions.
      </p>

      {/* Summary card */}
      <div className="mb-6 rounded-xl border border-gray-200 bg-white p-5">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">
          Booking Summary
        </h3>
        <div className="divide-y divide-gray-100">
          <SummaryRow
            label="Property"
            value={selectedPlace?.full_address ?? "—"}
          />
          <SummaryRow
            label="Services"
            value={
              <ul className="space-y-0.5 text-right">
                {selectedServiceFees.map((f) => (
                  <li key={f.id}>{f.service_name}</li>
                ))}
              </ul>
            }
          />
          <SummaryRow
            label="Date"
            value={scheduledDate
              ? new Date(scheduledDate + "T00:00:00").toLocaleDateString(
                  "en-US",
                  { weekday: "short", month: "short", day: "numeric", year: "numeric" },
                )
              : "—"}
          />
          <SummaryRow
            label="Time"
            value={
              scheduledStartTime && scheduledEndTime
                ? `${scheduledStartTime} – ${scheduledEndTime}`
                : "—"
            }
          />
          <SummaryRow label="Frequency" value={regularityLabel} />
          <div className="flex items-center justify-between py-3 text-sm font-semibold">
            <span className="text-gray-900">Total</span>
            <span className="text-lg text-blue-600">${total.toFixed(2)}</span>
          </div>
        </div>
      </div>

      {/* Details form */}
      <div className="space-y-4">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-gray-700">
            Comments
          </label>
          <textarea
            rows={3}
            value={comments}
            onChange={(e) => setDetails({ comments: e.target.value })}
            placeholder="Anything the cleaner should know…"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-medium text-gray-700">
            Special requests
          </label>
          <textarea
            rows={3}
            value={specialRequest}
            onChange={(e) => setDetails({ specialRequest: e.target.value })}
            placeholder="e.g. Use fragrance-free products, focus on kitchen…"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="mb-1.5 flex items-center gap-2 text-sm font-medium text-gray-700">
            <Tag className="h-4 w-4 text-gray-400" />
            Discount code
          </label>
          <input
            type="text"
            value={discountCode}
            onChange={(e) =>
              setDetails({ discountCode: e.target.value.toUpperCase() })
            }
            placeholder="PROMO10"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm uppercase focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 sm:max-w-xs"
          />
        </div>
      </div>

      <NavButtons onPrev={prevStep} onNext={nextStep} nextLabel="Proceed to Payment" />
    </div>
  );
}

// ── STEP 5: Payment ───────────────────────────────────────────────────────────
function PaymentForm({
  clientSecret,
  bookingId,
  onSuccess,
}: {
  clientSecret: string;
  bookingId: number;
  onSuccess: () => void;
}) {
  const stripe = useStripe();
  const elements = useElements();
  const [paying, setPaying] = useState(false);
  const [error, setError] = useState("");

  const handlePay = async () => {
    if (!stripe || !elements) return;
    setPaying(true);
    setError("");

    const cardElement = elements.getElement(CardElement);
    if (!cardElement) {
      setError("Card element not found.");
      setPaying(false);
      return;
    }

    const { error: stripeError, paymentIntent } =
      await stripe.confirmCardPayment(clientSecret, {
        payment_method: { card: cardElement },
      });

    if (stripeError) {
      setError(stripeError.message ?? "Payment failed.");
      setPaying(false);
      return;
    }

    if (paymentIntent?.status === "succeeded") {
      onSuccess();
    } else {
      setError("Payment was not completed. Please try again.");
      setPaying(false);
    }
  };

  return (
    <div>
      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}

      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <label className="mb-3 block text-sm font-medium text-gray-700">
          Card details
        </label>
        <div className="rounded-lg border border-gray-300 px-3 py-3">
          <CardElement
            options={{
              style: {
                base: {
                  fontSize: "14px",
                  color: "#111827",
                  "::placeholder": { color: "#9CA3AF" },
                },
              },
            }}
          />
        </div>
      </div>

      <div className="mt-6">
        <button
          onClick={handlePay}
          disabled={paying || !stripe}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
        >
          {paying && <Loader2 className="h-4 w-4 animate-spin" />}
          {paying ? "Processing…" : "Confirm & Pay"}
        </button>
      </div>
    </div>
  );
}

function Step5Payment() {
  const {
    clientSecret,
    bookingId,
    setPaymentInfo,
    getPayload,
    prevStep,
    computeTotalFee,
  } = useBookingStore();
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [success, setSuccess] = useState(false);
  const hasFetched = useRef(false);

  useEffect(() => {
    if (clientSecret || hasFetched.current) return;
    hasFetched.current = true;

    const payload = getPayload();
    setCreating(true);
    setCreateError("");

    api
      .post<BookingDetail>("/bookings/", payload)
      .then((booking) => {
        if (booking.client_secret && booking.id) {
          setPaymentInfo(booking.client_secret, booking.id);
        } else {
          setCreateError(
            "Booking created but no payment intent was returned. Contact support.",
          );
        }
      })
      .catch((err: unknown) => {
        setCreateError(
          err instanceof Error ? err.message : "Failed to create booking.",
        );
      })
      .finally(() => setCreating(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const total = computeTotalFee();

  if (success) {
    return (
      <div className="py-12 text-center">
        <CheckCircle className="mx-auto h-16 w-16 text-green-500" />
        <h2 className="mt-4 text-2xl font-semibold text-gray-900">
          Booking Confirmed!
        </h2>
        <p className="mt-2 text-sm text-gray-500">
          Your cleaning has been scheduled. You will receive a confirmation
          email shortly.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <a
            href="/resident/bookings"
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
          >
            View My Bookings
          </a>
          <a
            href="/resident"
            className="rounded-lg border border-gray-300 px-5 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Dashboard
          </a>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="mb-1 text-xl font-semibold text-gray-900">
        Payment
      </h2>
      <p className="mb-6 text-sm text-gray-500">
        Your total is{" "}
        <span className="font-semibold text-blue-600">
          ${total.toFixed(2)}
        </span>
        . Enter your card details to confirm.
      </p>

      {creating && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
          <span className="ml-3 text-sm text-gray-500">
            Preparing your booking…
          </span>
        </div>
      )}

      {!creating && createError && (
        <div className="mb-4">
          <ErrorBanner message={createError} />
          <button
            onClick={() => {
              hasFetched.current = false;
              setCreateError("");
            }}
            className="mt-3 text-sm text-blue-600 hover:underline"
          >
            Try again
          </button>
        </div>
      )}

      {!creating && !createError && clientSecret && (
        <Elements stripe={stripePromise} options={{ clientSecret }}>
          <PaymentForm
            clientSecret={clientSecret}
            bookingId={bookingId!}
            onSuccess={() => setSuccess(true)}
          />
        </Elements>
      )}

      {!success && (
        <div className="mt-4 border-t border-gray-100 pt-4">
          <button
            onClick={prevStep}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700"
          >
            <ChevronLeft className="h-4 w-4" />
            Back to Review
          </button>
        </div>
      )}
    </div>
  );
}

// ── Main Wizard Page ──────────────────────────────────────────────────────────
export default function BookPage() {
  const { currentStep, reset } = useBookingStore();

  // Reset store when page unmounts
  useEffect(() => {
    return () => reset();
  }, [reset]);

  const renderStep = () => {
    switch (currentStep) {
      case 1:
        return <Step1Place />;
      case 2:
        return <Step2Services />;
      case 3:
        return <Step3Schedule />;
      case 4:
        return <Step4Review />;
      case 5:
        return <Step5Payment />;
      default:
        return <Step1Place />;
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Book a Cleaning</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Step {currentStep} of 5
          </p>
        </div>
        {currentStep < 5 && (
          <button
            onClick={() => {
              if (
                window.confirm(
                  "Cancel booking? Your progress will be lost.",
                )
              ) {
                reset();
                window.location.href = "/resident";
              }
            }}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          >
            <X className="h-4 w-4" />
            Cancel
          </button>
        )}
      </div>

      {/* Progress stepper */}
      <Stepper current={currentStep} />

      {/* Step content card */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        {renderStep()}
      </div>
    </div>
  );
}
