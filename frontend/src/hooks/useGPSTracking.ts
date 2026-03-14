/**
 * useGPSTracking Hook
 * ====================
 *
 * React hook that manages the WebSocket connection for real-time
 * GPS tracking of a Service Pro during an active booking.
 *
 * Usage:
 *   const { location, events, status, isConnected } = useGPSTracking(bookingId);
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/lib/auth-store";
import type {
  GeofenceEvent,
  ServiceProLocationStatus,
  WSTrackingMessage,
} from "@/types/iot";

interface GPSTrackingState {
  latitude: number | null;
  longitude: number | null;
  accuracy: number | null;
  heading: number | null;
  speed: number | null;
  eta_minutes: number | null;
  status: ServiceProLocationStatus;
  distance_to_property: number | null;
  is_within_geofence: boolean;
  timestamp: string | null;
}

interface GeofenceEventEntry {
  event: string;
  distance_meters: number;
  device_name: string;
  timestamp: string;
}

export function useGPSTracking(bookingId: string | number | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);

  const [isConnected, setIsConnected] = useState(false);
  const [location, setLocation] = useState<GPSTrackingState>({
    latitude: null,
    longitude: null,
    accuracy: null,
    heading: null,
    speed: null,
    eta_minutes: null,
    status: "en_route",
    distance_to_property: null,
    is_within_geofence: false,
    timestamp: null,
  });
  const [geofenceEvents, setGeofenceEvents] = useState<GeofenceEventEntry[]>(
    [],
  );
  const [error, setError] = useState<string | null>(null);

  const connect = useCallback(() => {
    if (!bookingId) return;

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsHost =
      process.env.NEXT_PUBLIC_WS_URL ||
      `${wsProtocol}//${window.location.host}`;
    const wsUrl = `${wsHost}/ws/gps-tracking/${bookingId}/`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;

        // Authenticate with JWT if available
        const token = useAuthStore.getState().tokens?.access;
        if (token) {
          ws.send(
            JSON.stringify({
              type: "authenticate",
              token,
            }),
          );
        }
      };

      ws.onmessage = (event) => {
        try {
          const data: WSTrackingMessage = JSON.parse(event.data);

          switch (data.type) {
            case "location_update":
              setLocation({
                latitude: data.latitude,
                longitude: data.longitude,
                accuracy: data.accuracy,
                heading: data.heading,
                speed: data.speed,
                eta_minutes: data.eta_minutes,
                status: data.status,
                distance_to_property: data.distance_to_property,
                is_within_geofence: data.is_within_geofence,
                timestamp: data.timestamp,
              });
              break;

            case "geofence_event":
              setGeofenceEvents((prev) => [
                {
                  event: data.event,
                  distance_meters: data.distance_meters,
                  device_name: data.device_name,
                  timestamp: data.timestamp,
                },
                ...prev.slice(0, 19), // Keep last 20
              ]);
              break;

            case "status_update":
              setLocation((prev) => ({
                ...prev,
                status: data.status,
              }));
              break;

            case "connected":
              // Connection confirmed
              break;

            case "error":
              setError(data.message);
              break;
          }
        } catch {
          console.error("Failed to parse GPS tracking message");
        }
      };

      ws.onclose = (event) => {
        setIsConnected(false);
        wsRef.current = null;

        // Auto-reconnect with exponential backoff (max 30s)
        if (event.code !== 4001 && event.code !== 4003) {
          const delay = Math.min(
            1000 * Math.pow(2, reconnectAttempts.current),
            30000,
          );
          reconnectAttempts.current += 1;

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };

      ws.onerror = () => {
        setError("WebSocket connection error.");
      };
    } catch (err) {
      setError("Failed to create WebSocket connection.");
    }
  }, [bookingId]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close(1000, "Component unmounted");
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    location,
    geofenceEvents,
    isConnected,
    error,
    reconnect: connect,
    disconnect,
  };
}
