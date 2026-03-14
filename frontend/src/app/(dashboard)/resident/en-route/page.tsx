/**
 * Resident En Route — Live Service Pro Tracking
 * ===============================================
 *
 * Full-screen Mapbox map showing the assigned Service Pro's real-time
 * GPS position as they travel to the Resident's property.
 *
 * Features:
 *   • Live GPS marker updated via WebSocket every ~3 seconds
 *   • Property geofence circle overlay (50 m radius)
 *   • ETA countdown + distance indicator
 *   • Geofence event timeline (enter, auto-unlock)
 *   • Status badges (En Route → Arrived → In Progress → Completed)
 *   • Auto-unlock notification banner
 */

"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useGPSTracking } from "@/hooks/useGPSTracking";
import type {
  ServiceProLocation,
  GeofenceEvent as GeofenceEventType,
  PropertyGeofence,
} from "@/types/iot";
import { LOCATION_STATUS_INFO } from "@/types/iot";

// ── Mapbox GL types (loaded via CDN script) ─────────────────────────
declare global {
  interface Window {
    mapboxgl: any;
  }
}

// ── Constants ───────────────────────────────────────────────────────

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || "";
const MAPBOX_STYLE = "mapbox://styles/mapbox/dark-v11";

export default function EnRoutePage() {
  const searchParams = useSearchParams();
  const bookingId = searchParams.get("booking");

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markerRef = useRef<mapboxgl.Marker | null>(null);
  const propertyMarkerRef = useRef<mapboxgl.Marker | null>(null);

  const [mapLoaded, setMapLoaded] = useState(false);
  const [initialLocation, setInitialLocation] = useState<ServiceProLocation | null>(null);
  const [geofence, setGeofence] = useState<PropertyGeofence | null>(null);
  const [geofenceEvents, setGeofenceEvents] = useState<GeofenceEventType[]>([]);
  const [showUnlockBanner, setShowUnlockBanner] = useState(false);
  const [scriptLoaded, setScriptLoaded] = useState(false);

  // WebSocket GPS tracking
  const {
    location: liveLocation,
    geofenceEvents: wsGeofenceEvents,
    isConnected,
    error: wsError,
  } = useGPSTracking(bookingId);

  // ── Load Mapbox GL JS via CDN ─────────────────────────────────────
  useEffect(() => {
    if (window.mapboxgl) {
      setScriptLoaded(true);
      return;
    }

    // Load CSS
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://api.mapbox.com/mapbox-gl-js/v3.3.0/mapbox-gl.css";
    document.head.appendChild(link);

    // Load JS
    const script = document.createElement("script");
    script.src = "https://api.mapbox.com/mapbox-gl-js/v3.3.0/mapbox-gl.js";
    script.onload = () => setScriptLoaded(true);
    document.head.appendChild(script);

    return () => {
      document.head.removeChild(link);
      document.head.removeChild(script);
    };
  }, []);

  // ── Fetch initial data (location + geofence) ─────────────────────
  useEffect(() => {
    if (!bookingId) return;

    // Fetch current location via REST
    api
      .get<{ location: ServiceProLocation; geofence_events: GeofenceEventType[] }>(
        `/iot/gps/location/${bookingId}/`,
      )
      .then((data) => {
        setInitialLocation(data.location);
        setGeofenceEvents(data.geofence_events || []);
      })
      .catch(() => {
        // No location yet — will get via WebSocket
      });
  }, [bookingId]);

  // ── Initialize Mapbox map ─────────────────────────────────────────
  useEffect(() => {
    if (!scriptLoaded || !mapContainerRef.current || mapRef.current) return;
    if (!window.mapboxgl) return;

    window.mapboxgl.accessToken = MAPBOX_TOKEN;

    const map = new window.mapboxgl.Map({
      container: mapContainerRef.current,
      style: MAPBOX_STYLE,
      center: [-98.5795, 39.8283], // US center
      zoom: 14,
      attributionControl: false,
    });

    map.addControl(
      new window.mapboxgl.NavigationControl({ showCompass: false }),
      "top-right",
    );

    map.on("load", () => {
      setMapLoaded(true);
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [scriptLoaded]);

  // ── Update map with live location ─────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || !mapLoaded || !window.mapboxgl) return;

    const lat = liveLocation.latitude ?? initialLocation?.latitude;
    const lng = liveLocation.longitude ?? initialLocation?.longitude;

    if (lat == null || lng == null) return;

    const map = mapRef.current;

    // Create or update Service Pro marker
    if (!markerRef.current) {
      // Custom marker element
      const el = document.createElement("div");
      el.className = "gps-marker";
      el.innerHTML = `
        <div style="
          width: 40px;
          height: 40px;
          border-radius: 50%;
          background: #3B82F6;
          border: 3px solid #fff;
          box-shadow: 0 2px 8px rgba(0,0,0,0.4);
          display: flex;
          align-items: center;
          justify-content: center;
          color: #fff;
          font-size: 18px;
          position: relative;
        ">
          <span style="font-size: 20px;">🧹</span>
          <div style="
            position: absolute;
            bottom: -6px;
            left: 50%;
            transform: translateX(-50%);
            width: 0;
            height: 0;
            border-left: 6px solid transparent;
            border-right: 6px solid transparent;
            border-top: 8px solid #3B82F6;
          "></div>
        </div>
      `;

      markerRef.current = new window.mapboxgl.Marker({ element: el })
        .setLngLat([lng, lat])
        .addTo(map);

      // Center map on first location
      map.flyTo({ center: [lng, lat], zoom: 15 });
    } else {
      // Smooth marker transition
      markerRef.current.setLngLat([lng, lat]);
    }
  }, [
    mapLoaded,
    liveLocation.latitude,
    liveLocation.longitude,
    initialLocation,
  ]);

  // ── Add geofence circle to map ────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || !mapLoaded || !geofence) return;

    const map = mapRef.current;

    // Property marker
    if (!propertyMarkerRef.current && window.mapboxgl) {
      const el = document.createElement("div");
      el.innerHTML = `
        <div style="
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: #10B981;
          border: 3px solid #fff;
          box-shadow: 0 2px 8px rgba(0,0,0,0.4);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 16px;
        ">🏠</div>
      `;
      propertyMarkerRef.current = new window.mapboxgl.Marker({ element: el })
        .setLngLat([geofence.longitude, geofence.latitude])
        .addTo(map);
    }

    // Geofence radius circle (using a GeoJSON circle approximation)
    const sourceId = "geofence-circle";
    if (!map.getSource(sourceId)) {
      const center = [geofence.longitude, geofence.latitude];
      const radius = geofence.radius_meters / 1000; // km
      const points = 64;
      const coords: [number, number][] = [];

      for (let i = 0; i < points; i++) {
        const angle = (i / points) * 2 * Math.PI;
        const dx = radius * Math.cos(angle);
        const dy = radius * Math.sin(angle);
        const lat = center[1] + (dy / 111.32);
        const lng =
          center[0] +
          (dx / (111.32 * Math.cos((center[1] * Math.PI) / 180)));
        coords.push([lng, lat]);
      }
      coords.push(coords[0]); // close the ring

      map.addSource(sourceId, {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: {
            type: "Polygon",
            coordinates: [coords],
          },
        },
      });

      map.addLayer({
        id: "geofence-fill",
        type: "fill",
        source: sourceId,
        paint: {
          "fill-color": "#10B981",
          "fill-opacity": 0.15,
        },
      });

      map.addLayer({
        id: "geofence-border",
        type: "line",
        source: sourceId,
        paint: {
          "line-color": "#10B981",
          "line-width": 2,
          "line-dasharray": [3, 2],
        },
      });
    }
  }, [mapLoaded, geofence]);

  // ── Show auto-unlock banner ───────────────────────────────────────
  useEffect(() => {
    const hasUnlock = wsGeofenceEvents.some((e) => e.event === "auto_unlock");
    if (hasUnlock) {
      setShowUnlockBanner(true);
      const timeout = setTimeout(() => setShowUnlockBanner(false), 15000);
      return () => clearTimeout(timeout);
    }
  }, [wsGeofenceEvents]);

  // ── Derive display values ─────────────────────────────────────────
  const currentStatus = liveLocation.status || initialLocation?.status || "en_route";
  const statusInfo = LOCATION_STATUS_INFO[currentStatus];
  const eta = liveLocation.eta_minutes ?? initialLocation?.eta_minutes;
  const distance = liveLocation.distance_to_property ?? initialLocation?.distance_to_property_meters;
  const proName = initialLocation?.service_pro_name || "Your cleaner";

  if (!bookingId) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center text-gray-500">
          <p className="text-lg font-medium">No booking selected</p>
          <p className="text-sm mt-1">
            Open this page from an active booking to track your Service Pro.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-[calc(100vh-4rem)] w-full overflow-hidden rounded-lg border border-gray-200 dark:border-gray-800">
      {/* ── Auto-Unlock Banner ──────────────────────────────────────── */}
      {showUnlockBanner && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 animate-in slide-in-from-top">
          <div className="bg-emerald-500 text-white px-6 py-3 rounded-lg shadow-lg flex items-center gap-3">
            <span className="text-xl">🔓</span>
            <div>
              <p className="font-semibold text-sm">Door Auto-Unlocked</p>
              <p className="text-xs opacity-90">
                Your cleaner arrived — the smart lock was unlocked automatically.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Status Bar ─────────────────────────────────────────────── */}
      <div className="absolute top-4 left-4 z-40">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 p-4 min-w-[280px]">
          {/* Connection indicator */}
          <div className="flex items-center gap-2 mb-3">
            <div
              className={`w-2 h-2 rounded-full ${
                isConnected ? "bg-emerald-500 animate-pulse" : "bg-red-400"
              }`}
            />
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {isConnected ? "Live tracking" : "Reconnecting..."}
            </span>
          </div>

          {/* Service Pro name + status */}
          <h3 className="font-semibold text-gray-900 dark:text-white text-sm">
            {proName}
          </h3>
          <div className="flex items-center gap-2 mt-1">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: statusInfo.color }}
            />
            <span className="text-sm font-medium" style={{ color: statusInfo.color }}>
              {statusInfo.label}
            </span>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            {statusInfo.description}
          </p>

          {/* ETA + Distance */}
          <div className="grid grid-cols-2 gap-3 mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wider">ETA</p>
              <p className="text-lg font-bold text-gray-900 dark:text-white">
                {eta != null ? `${eta} min` : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wider">Distance</p>
              <p className="text-lg font-bold text-gray-900 dark:text-white">
                {distance != null
                  ? distance > 1000
                    ? `${(distance / 1000).toFixed(1)} km`
                    : `${Math.round(distance)} m`
                  : "—"}
              </p>
            </div>
          </div>

          {/* Geofence status */}
          {liveLocation.is_within_geofence && (
            <div className="mt-3 p-2 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg border border-emerald-200 dark:border-emerald-800">
              <p className="text-xs font-medium text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5">
                <span>📍</span> Within property radius
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Geofence Event Timeline ────────────────────────────────── */}
      {(wsGeofenceEvents.length > 0 || geofenceEvents.length > 0) && (
        <div className="absolute bottom-4 left-4 z-40">
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 p-3 max-w-[280px] max-h-[200px] overflow-y-auto">
            <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
              Activity
            </p>
            <div className="space-y-2">
              {wsGeofenceEvents.map((evt, i) => (
                <div
                  key={`ws-${i}`}
                  className="flex items-start gap-2 text-xs"
                >
                  <span className="mt-0.5">
                    {evt.event === "auto_unlock" ? "🔓" : "📍"}
                  </span>
                  <div>
                    <p className="font-medium text-gray-700 dark:text-gray-300">
                      {evt.event === "auto_unlock"
                        ? `${evt.device_name} unlocked`
                        : `Entered geofence (${Math.round(evt.distance_meters)}m)`}
                    </p>
                    <p className="text-gray-400">
                      {new Date(evt.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Error Banner ───────────────────────────────────────────── */}
      {wsError && (
        <div className="absolute bottom-4 right-4 z-40">
          <div className="bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 px-4 py-2 rounded-lg border border-red-200 dark:border-red-800 text-xs">
            {wsError}
          </div>
        </div>
      )}

      {/* ── Map Container ──────────────────────────────────────────── */}
      <div ref={mapContainerRef} className="w-full h-full" />

      {/* ── Loading State ──────────────────────────────────────────── */}
      {!mapLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 dark:bg-gray-950">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm text-gray-500 mt-3">Loading map...</p>
          </div>
        </div>
      )}
    </div>
  );
}
