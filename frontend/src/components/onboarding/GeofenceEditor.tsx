/**
 * GeofenceEditor — Mapbox Service Area Drawing Tool
 * ====================================================
 *
 * Agency Owners draw MultiPolygon service areas on a Mapbox map.
 * Features:
 *   - Draw polygons using Mapbox GL Draw
 *   - Name and color each service area
 *   - CRUD via REST API
 *   - Visual overlay of existing service areas
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  MapPin,
  Plus,
  Trash2,
  Save,
  Loader2,
  Layers,
  Pencil,
  X,
  Check,
} from "lucide-react";
import { api } from "@/lib/api";
import type { AgencyServiceArea, GeoJSONFeature } from "@/types/onboarding";

declare const mapboxgl: any;
declare const MapboxDraw: any;

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || "";

const AREA_COLORS = [
  "#01696F", "#A84B2F", "#6B4FBB", "#2563EB",
  "#059669", "#D97706", "#DC2626", "#7C3AED",
];

interface GeofenceEditorProps {
  agencyId?: number;
}

export default function GeofenceEditor({ agencyId }: GeofenceEditorProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const drawRef = useRef<any>(null);

  const [areas, setAreas] = useState<AgencyServiceArea[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingName, setEditingName] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [drawMode, setDrawMode] = useState(false);
  const [pendingName, setPendingName] = useState("");

  // ── Load existing service areas ────────────────────────────────────

  const loadAreas = useCallback(async () => {
    try {
      const data = await api.get<AgencyServiceArea[]>("/onboarding/service-areas/");
      setAreas(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load service areas");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAreas();
  }, [loadAreas]);

  // ── Initialize Mapbox ──────────────────────────────────────────────

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    // Load Mapbox GL JS + Draw from CDN
    const loadScript = (src: string) =>
      new Promise<void>((resolve) => {
        if (document.querySelector(`script[src="${src}"]`)) {
          resolve();
          return;
        }
        const s = document.createElement("script");
        s.src = src;
        s.onload = () => resolve();
        document.head.appendChild(s);
      });

    const loadCSS = (href: string) => {
      if (document.querySelector(`link[href="${href}"]`)) return;
      const l = document.createElement("link");
      l.rel = "stylesheet";
      l.href = href;
      document.head.appendChild(l);
    };

    const init = async () => {
      loadCSS("https://api.mapbox.com/mapbox-gl-js/v3.6.0/mapbox-gl.css");
      loadCSS("https://api.mapbox.com/mapbox-gl-js/plugins/mapbox-gl-draw/v1.4.3/mapbox-gl-draw.css");
      await loadScript("https://api.mapbox.com/mapbox-gl-js/v3.6.0/mapbox-gl.js");
      await loadScript("https://api.mapbox.com/mapbox-gl-js/plugins/mapbox-gl-draw/v1.4.3/mapbox-gl-draw.js");

      mapboxgl.accessToken = MAPBOX_TOKEN;

      const map = new mapboxgl.Map({
        container: mapContainer.current!,
        style: "mapbox://styles/mapbox/light-v11",
        center: [-95.3698, 29.7604], // Houston default
        zoom: 10,
      });

      map.addControl(new mapboxgl.NavigationControl(), "top-right");

      const draw = new MapboxDraw({
        displayControlsDefault: false,
        controls: { polygon: true, trash: true },
        defaultMode: "simple_select",
      });
      map.addControl(draw, "top-left");
      drawRef.current = draw;

      map.on("load", () => {
        mapRef.current = map;
        renderExistingAreas(map);
      });

      map.on("draw.create", handleDrawCreate);
      map.on("draw.update", handleDrawUpdate);
    };

    init();

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  // ── Render existing areas on map ───────────────────────────────────

  const renderExistingAreas = useCallback(
    (map: any) => {
      if (!map || !map.isStyleLoaded()) return;

      // Remove old layers
      areas.forEach((_, i) => {
        const id = `area-${i}`;
        if (map.getLayer(`${id}-fill`)) map.removeLayer(`${id}-fill`);
        if (map.getLayer(`${id}-border`)) map.removeLayer(`${id}-border`);
        if (map.getSource(id)) map.removeSource(id);
      });

      // Add each area as a source + layers
      areas.forEach((area, i) => {
        if (!area.is_active) return;
        const id = `area-${i}`;
        const geom = area.geojson.geometry || area.geojson;

        map.addSource(id, {
          type: "geojson",
          data: {
            type: "Feature",
            geometry: geom,
            properties: { name: area.name },
          },
        });

        map.addLayer({
          id: `${id}-fill`,
          type: "fill",
          source: id,
          paint: {
            "fill-color": area.color,
            "fill-opacity": 0.15,
          },
        });

        map.addLayer({
          id: `${id}-border`,
          type: "line",
          source: id,
          paint: {
            "line-color": area.color,
            "line-width": 2,
            "line-dasharray": [2, 1],
          },
        });
      });
    },
    [areas]
  );

  useEffect(() => {
    if (mapRef.current && mapRef.current.isStyleLoaded()) {
      renderExistingAreas(mapRef.current);
    }
  }, [areas, renderExistingAreas]);

  // ── Handle draw events ─────────────────────────────────────────────

  const handleDrawCreate = async (e: any) => {
    const feature = e.features[0];
    if (!feature) return;

    // Prompt for area name
    const name = pendingName || `Service Area ${areas.length + 1}`;
    const color = AREA_COLORS[areas.length % AREA_COLORS.length];

    const geojson: GeoJSONFeature = {
      type: "Feature",
      geometry: feature.geometry,
      properties: {},
    };

    setSaving(true);
    try {
      await api.post<AgencyServiceArea>("/onboarding/service-areas/", {
        name,
        geojson,
        color,
      });
      await loadAreas();
      drawRef.current?.deleteAll();
      setPendingName("");
      setDrawMode(false);
    } catch (err: any) {
      setError(err?.message || "Failed to save area");
    } finally {
      setSaving(false);
    }
  };

  const handleDrawUpdate = () => {
    // Could handle polygon editing here
  };

  // ── Delete service area ────────────────────────────────────────────

  const deleteArea = async (uuid: string) => {
    if (!confirm("Deactivate this service area?")) return;
    try {
      await api.delete(`/onboarding/service-areas/${uuid}/`);
      await loadAreas();
    } catch (err: any) {
      setError(err?.message || "Failed to delete");
    }
  };

  // ── Rename service area ────────────────────────────────────────────

  const renameArea = async (uuid: string) => {
    if (!newName.trim()) return;
    try {
      await api.patch(`/onboarding/service-areas/${uuid}/`, { name: newName });
      setEditingName(null);
      setNewName("");
      await loadAreas();
    } catch (err: any) {
      setError(err?.message || "Failed to rename");
    }
  };

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <Layers className="h-5 w-5 text-brand-500" />
          Service Areas
        </h3>
        <div className="flex items-center gap-2">
          {drawMode ? (
            <>
              <input
                type="text"
                value={pendingName}
                onChange={(e) => setPendingName(e.target.value)}
                placeholder="Area name..."
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm
                           focus:border-brand-500 focus:outline-none"
              />
              <button
                onClick={() => {
                  setDrawMode(false);
                  drawRef.current?.changeMode("simple_select");
                }}
                className="rounded-md bg-gray-100 p-1.5 text-gray-500 hover:bg-gray-200"
              >
                <X className="h-4 w-4" />
              </button>
            </>
          ) : (
            <button
              onClick={() => {
                setDrawMode(true);
                drawRef.current?.changeMode("draw_polygon");
              }}
              className="flex items-center gap-1.5 rounded-lg bg-brand-500 px-3 py-1.5
                         text-sm font-medium text-white hover:bg-brand-600"
            >
              <Plus className="h-4 w-4" />
              Draw Area
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      {/* Map */}
      <div
        ref={mapContainer}
        className="h-[400px] w-full rounded-xl border border-gray-200 overflow-hidden"
      />

      {saving && (
        <div className="flex items-center gap-2 text-sm text-brand-600">
          <Loader2 className="h-4 w-4 animate-spin" />
          Saving service area...
        </div>
      )}

      {/* Area List */}
      {areas.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Active Areas ({areas.filter((a) => a.is_active).length})
          </p>
          {areas.filter((a) => a.is_active).map((area) => (
            <div
              key={area.uuid}
              className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-3"
            >
              <div className="flex items-center gap-3">
                <div
                  className="h-3 w-3 rounded-full"
                  style={{ backgroundColor: area.color }}
                />
                {editingName === area.uuid ? (
                  <div className="flex items-center gap-1">
                    <input
                      type="text"
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      className="rounded border border-gray-300 px-2 py-1 text-sm"
                      autoFocus
                    />
                    <button
                      onClick={() => renameArea(area.uuid)}
                      className="p-1 text-green-600 hover:text-green-700"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => setEditingName(null)}
                      className="p-1 text-gray-400 hover:text-gray-500"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ) : (
                  <span className="text-sm font-medium text-gray-900">
                    {area.name}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => {
                    setEditingName(area.uuid);
                    setNewName(area.name);
                  }}
                  className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                >
                  <Pencil className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => deleteArea(area.uuid)}
                  className="rounded-md p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && areas.filter((a) => a.is_active).length === 0 && (
        <p className="text-sm text-gray-500">
          No service areas defined. Click "Draw Area" to define your coverage zone on the map.
        </p>
      )}
    </div>
  );
}
