"use client";

/**
 * Smart Home & IoT Management — Resident Dashboard
 * ==================================================
 *
 * Full-page interface for:
 *   1. Connecting / managing smart-lock devices (August, Yale)
 *   2. Toggling Smart Access auto-unlocking per device
 *   3. Viewing time-bound access tokens issued for bookings
 *   4. Linking / unlinking voice assistants (Alexa, Siri)
 *
 * All API calls go through the shared apiFetch client.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type {
  ConnectedDevice,
  SmartLockAccessToken,
  VoiceAssistantLink,
  OAuthURLResponse,
  DeviceProvider,
  VoicePlatform,
  EmergencyLockoutResponse,
  PROVIDER_INFO as ProviderInfoType,
} from "@/types/iot";
import { PROVIDER_INFO, VOICE_PLATFORM_INFO } from "@/types/iot";

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Main Page Component
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

export default function SmartHomePage() {
  const [devices, setDevices] = useState<ConnectedDevice[]>([]);
  const [accessTokens, setAccessTokens] = useState<SmartLockAccessToken[]>([]);
  const [voiceLinks, setVoiceLinks] = useState<VoiceAssistantLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"devices" | "access" | "voice">(
    "devices"
  );

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [devicesRes, tokensRes, linksRes] = await Promise.all([
        api.get<ConnectedDevice[]>("/iot/devices/"),
        api.get<SmartLockAccessToken[]>("/iot/access-tokens/"),
        api.get<VoiceAssistantLink[]>("/iot/voice-links/"),
      ]);
      setDevices(devicesRes);
      setAccessTokens(tokensRes);
      setVoiceLinks(linksRes);
    } catch (err: any) {
      setError(err?.message ?? "Failed to load IoT data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-[hsl(var(--foreground))]">
          Smart Home & IoT
        </h1>
        <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
          Connect smart locks, manage access codes, and link voice assistants.
        </p>
      </div>

      {/* Emergency Lockout Banner */}
      {devices.length > 0 && (
        <EmergencyLockoutBanner onLockout={fetchData} />
      )}

      {/* Tab Navigation */}
      <div className="flex gap-1 rounded-lg bg-[hsl(var(--muted))] p-1">
        {(
          [
            { key: "devices", label: "Smart Locks", count: devices.length },
            { key: "access", label: "Access Codes", count: accessTokens.length },
            { key: "voice", label: "Voice Assistants", count: voiceLinks.length },
          ] as const
        ).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "bg-[hsl(var(--background))] text-[hsl(var(--foreground))] shadow-sm"
                : "text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
            }`}
          >
            {tab.label}
            {tab.count > 0 && (
              <span className="ml-1.5 inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-[hsl(var(--primary))] px-1.5 text-xs text-[hsl(var(--primary-foreground))]">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Error State */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
          {error}
          <button
            onClick={fetchData}
            className="ml-2 underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-[hsl(var(--primary))] border-t-transparent" />
        </div>
      )}

      {/* Tab Content */}
      {!loading && (
        <>
          {activeTab === "devices" && (
            <DevicesPanel devices={devices} onRefresh={fetchData} />
          )}
          {activeTab === "access" && (
            <AccessTokensPanel tokens={accessTokens} onRefresh={fetchData} />
          )}
          {activeTab === "voice" && (
            <VoiceLinksPanel links={voiceLinks} onRefresh={fetchData} />
          )}
        </>
      )}
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Devices Panel
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function DevicesPanel({
  devices,
  onRefresh,
}: {
  devices: ConnectedDevice[];
  onRefresh: () => void;
}) {
  const [connectingProvider, setConnectingProvider] =
    useState<DeviceProvider | null>(null);

  const handleConnect = async (provider: DeviceProvider) => {
    setConnectingProvider(provider);
    try {
      const redirectUri = `${window.location.origin}/resident/smart-home/callback`;
      const res = await api.post<OAuthURLResponse>("/iot/devices/oauth-url/", {
        provider,
        redirect_uri: redirectUri,
      });
      // Store the state for CSRF verification
      sessionStorage.setItem("iot_oauth_state", res.state);
      sessionStorage.setItem("iot_oauth_provider", provider);
      window.location.href = res.authorize_url;
    } catch (err: any) {
      alert(`Failed to start OAuth: ${err?.message ?? "Unknown error"}`);
    } finally {
      setConnectingProvider(null);
    }
  };

  const handleToggleSmartAccess = async (
    device: ConnectedDevice,
    enabled: boolean
  ) => {
    try {
      await api.post(`/iot/devices/${device.uuid}/toggle-smart-access/`, {
        enabled,
      });
      onRefresh();
    } catch (err: any) {
      alert(`Failed to toggle: ${err?.message ?? "Unknown error"}`);
    }
  };

  const handleDisconnect = async (device: ConnectedDevice) => {
    if (
      !confirm(
        `Disconnect ${device.device_name}? This will revoke all access tokens.`
      )
    )
      return;
    try {
      await api.delete(`/iot/devices/${device.uuid}/`);
      onRefresh();
    } catch (err: any) {
      alert(`Failed to disconnect: ${err?.message ?? "Unknown error"}`);
    }
  };

  const handleSync = async (device: ConnectedDevice) => {
    try {
      await api.post(`/iot/devices/${device.uuid}/sync/`);
      onRefresh();
    } catch (err: any) {
      alert(`Sync failed: ${err?.message ?? "Unknown error"}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Add Device Section */}
      <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
        <h2 className="text-base font-semibold text-[hsl(var(--card-foreground))]">
          Connect a Smart Lock
        </h2>
        <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
          Link your smart lock to enable automatic access codes for Service Pros
          during bookings.
        </p>
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {(Object.keys(PROVIDER_INFO) as DeviceProvider[]).map((provider) => {
            const info = PROVIDER_INFO[provider];
            const isConnected = devices.some(
              (d) => d.provider === provider && d.status === "active"
            );
            return (
              <button
                key={provider}
                onClick={() => !isConnected && handleConnect(provider)}
                disabled={!!connectingProvider || isConnected}
                className={`flex items-center gap-3 rounded-lg border p-4 text-left transition-all ${
                  isConnected
                    ? "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-900/20"
                    : "border-[hsl(var(--border))] hover:border-[hsl(var(--primary))] hover:bg-[hsl(var(--accent))]"
                } disabled:cursor-not-allowed disabled:opacity-60`}
              >
                <span className="text-2xl">{info.icon}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-[hsl(var(--foreground))]">
                    {info.name}
                  </div>
                  <div className="text-xs text-[hsl(var(--muted-foreground))]">
                    {isConnected
                      ? "Connected"
                      : connectingProvider === provider
                        ? "Connecting..."
                        : "Click to connect"}
                  </div>
                </div>
                {isConnected && (
                  <span className="text-green-600 dark:text-green-400">✓</span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Devices List */}
      {devices.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[hsl(var(--border))] p-8 text-center">
          <div className="text-3xl">🔒</div>
          <p className="mt-2 text-sm font-medium text-[hsl(var(--foreground))]">
            No devices connected
          </p>
          <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
            Connect a smart lock above to get started with Smart Access.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {devices.map((device) => (
            <DeviceCard
              key={device.uuid}
              device={device}
              onToggleSmartAccess={handleToggleSmartAccess}
              onDisconnect={handleDisconnect}
              onSync={handleSync}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Device Card ─────────────────────────────────────────────────────

function DeviceCard({
  device,
  onToggleSmartAccess,
  onDisconnect,
  onSync,
}: {
  device: ConnectedDevice;
  onToggleSmartAccess: (device: ConnectedDevice, enabled: boolean) => void;
  onDisconnect: (device: ConnectedDevice) => void;
  onSync: (device: ConnectedDevice) => void;
}) {
  const providerInfo = PROVIDER_INFO[device.provider] ?? {
    name: device.provider,
    icon: "🔒",
    color: "#666",
  };

  const statusColors: Record<string, string> = {
    active:
      "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    disconnected:
      "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    pending:
      "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  };

  return (
    <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{providerInfo.icon}</span>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-[hsl(var(--card-foreground))]">
                {device.device_name}
              </h3>
              <span
                className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${statusColors[device.status] ?? statusColors.pending}`}
              >
                {device.status}
              </span>
            </div>
            <p className="text-xs text-[hsl(var(--muted-foreground))]">
              {providerInfo.name}
              {device.device_model && ` · ${device.device_model}`}
              {device.place_name && ` · ${device.place_name}`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => onSync(device)}
            className="rounded-md p-2 text-[hsl(var(--muted-foreground))] transition-colors hover:bg-[hsl(var(--accent))] hover:text-[hsl(var(--foreground))]"
            title="Sync device"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          </button>
          <button
            onClick={() => onDisconnect(device)}
            className="rounded-md p-2 text-red-500 transition-colors hover:bg-red-50 dark:hover:bg-red-900/20"
            title="Disconnect device"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Smart Access Toggle */}
      <div className="mt-4 flex items-center justify-between rounded-lg bg-[hsl(var(--accent))] px-4 py-3">
        <div>
          <div className="text-sm font-medium text-[hsl(var(--foreground))]">
            Smart Access
          </div>
          <div className="text-xs text-[hsl(var(--muted-foreground))]">
            Auto-generate temporary access codes for booked Service Pros
          </div>
        </div>
        <button
          onClick={() =>
            onToggleSmartAccess(device, !device.smart_access_enabled)
          }
          className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary))] focus:ring-offset-2 ${
            device.smart_access_enabled
              ? "bg-[hsl(var(--primary))]"
              : "bg-[hsl(var(--muted-foreground)/.3)]"
          }`}
          role="switch"
          aria-checked={device.smart_access_enabled}
        >
          <span
            className={`pointer-events-none inline-block h-5 w-5 translate-y-0.5 rounded-full bg-white shadow ring-0 transition-transform duration-200 ease-in-out ${
              device.smart_access_enabled
                ? "translate-x-[22px]"
                : "translate-x-0.5"
            }`}
          />
        </button>
      </div>

      {/* Metadata footer */}
      {device.last_synced_at && (
        <div className="mt-3 text-xs text-[hsl(var(--muted-foreground))]">
          Last synced: {new Date(device.last_synced_at).toLocaleString()}
        </div>
      )}
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Access Tokens Panel
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function AccessTokensPanel({
  tokens,
  onRefresh,
}: {
  tokens: SmartLockAccessToken[];
  onRefresh: () => void;
}) {
  const handleRevoke = async (token: SmartLockAccessToken) => {
    if (!confirm("Revoke this access code? The Service Pro will lose access."))
      return;
    try {
      await api.post(`/iot/access-tokens/${token.uuid}/revoke/`);
      onRefresh();
    } catch (err: any) {
      alert(`Failed to revoke: ${err?.message ?? "Unknown error"}`);
    }
  };

  const statusColors: Record<string, string> = {
    active:
      "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    used: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    expired:
      "bg-gray-100 text-gray-600 dark:bg-gray-800/30 dark:text-gray-400",
    revoked:
      "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  };

  if (tokens.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-[hsl(var(--border))] p-8 text-center">
        <div className="text-3xl">🔑</div>
        <p className="mt-2 text-sm font-medium text-[hsl(var(--foreground))]">
          No access codes yet
        </p>
        <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
          When Smart Access is enabled, temporary codes are auto-generated for
          bookings.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {tokens.map((token) => (
        <div
          key={token.uuid}
          className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4"
        >
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-medium text-[hsl(var(--card-foreground))]">
                  Booking #{token.booking}
                </h3>
                <span
                  className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${statusColors[token.status] ?? statusColors.expired}`}
                >
                  {token.status}
                </span>
              </div>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                {token.device_name} ({token.device_provider}) · Service Pro:{" "}
                {token.service_pro_name}
              </p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                Valid: {new Date(token.valid_from).toLocaleString()} →{" "}
                {new Date(token.valid_until).toLocaleString()}
              </p>
            </div>

            {token.status === "active" && (
              <button
                onClick={() => handleRevoke(token)}
                className="rounded-md border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/20"
              >
                Revoke
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Voice Assistant Links Panel
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Emergency Lockout Banner
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function EmergencyLockoutBanner({ onLockout }: { onLockout: () => void }) {
  const [showConfirm, setShowConfirm] = useState(false);
  const [activating, setActivating] = useState(false);
  const [result, setResult] = useState<EmergencyLockoutResponse | null>(null);
  const [lockoutError, setLockoutError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // ── WebSocket for real-time lockout confirmation ─────────────
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/alerts/`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "emergency_lockout" && data.priority === "critical") {
            // Another lockout event arrived (possibly from Support Architect)
            onLockout();
          }
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onerror = () => {
        // WebSocket is optional — lockout works without it
      };

      return () => {
        ws.close();
      };
    } catch {
      // WebSocket not available — fine, lockout still works via REST
      return undefined;
    }
  }, [onLockout]);

  const handleLockout = async () => {
    setActivating(true);
    setLockoutError(null);
    setResult(null);

    try {
      const res = await api.post<EmergencyLockoutResponse>(
        "/iot/emergency-lockout/",
        { reason: "Resident-initiated emergency lockout via dashboard" }
      );
      setResult(res);
      setShowConfirm(false);
      onLockout(); // refresh device/token lists
    } catch (err: any) {
      setLockoutError(
        err?.body?.detail ?? err?.message ?? "Lockout failed. Please try again."
      );
    } finally {
      setActivating(false);
    }
  };

  return (
    <div className="rounded-lg border-2 border-red-300 bg-red-50 p-5 dark:border-red-700 dark:bg-red-950/30">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/40">
            <svg
              className="h-5 w-5 text-red-600 dark:text-red-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
              />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-red-800 dark:text-red-300">
              Emergency Lockout
            </h2>
            <p className="mt-0.5 text-xs text-red-600 dark:text-red-400">
              Instantly revoke all active Service Pro access codes across all
              your devices. This cannot be undone — new codes must be
              regenerated.
            </p>
          </div>
        </div>

        {!showConfirm && !result && (
          <button
            onClick={() => setShowConfirm(true)}
            className="shrink-0 rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 dark:bg-red-700 dark:hover:bg-red-600"
          >
            Activate Lockout
          </button>
        )}
      </div>

      {/* Confirmation step */}
      {showConfirm && !result && (
        <div className="mt-4 rounded-md border border-red-200 bg-white p-4 dark:border-red-800 dark:bg-red-950/50">
          <p className="text-sm font-medium text-red-800 dark:text-red-300">
            Are you sure? This will:
          </p>
          <ul className="mt-2 space-y-1 text-xs text-red-700 dark:text-red-400">
            <li className="flex items-center gap-1.5">
              <span className="text-red-500">•</span>
              Revoke all active access codes immediately
            </li>
            <li className="flex items-center gap-1.5">
              <span className="text-red-500">•</span>
              Disable Smart Access on all your devices
            </li>
            <li className="flex items-center gap-1.5">
              <span className="text-red-500">•</span>
              Alert Support Architects for immediate follow-up
            </li>
          </ul>
          <div className="mt-3 flex gap-2">
            <button
              onClick={handleLockout}
              disabled={activating}
              className="rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-red-700 dark:hover:bg-red-600"
            >
              {activating ? (
                <span className="flex items-center gap-2">
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Activating...
                </span>
              ) : (
                "Confirm Emergency Lockout"
              )}
            </button>
            <button
              onClick={() => setShowConfirm(false)}
              disabled={activating}
              className="rounded-md border border-red-200 px-4 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/20"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Success result */}
      {result && (
        <div className="mt-4 rounded-md border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-900/20">
          <div className="flex items-center gap-2">
            <svg
              className="h-5 w-5 text-green-600 dark:text-green-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
            <p className="text-sm font-semibold text-green-800 dark:text-green-300">
              Lockout Activated
            </p>
          </div>
          <p className="mt-1 text-xs text-green-700 dark:text-green-400">
            {result.revoked_count} access code(s) revoked across{" "}
            {result.devices_locked} device(s). Support Architects have been
            alerted.
          </p>
          {result.failed_provider_revocations.length > 0 && (
            <p className="mt-1 text-xs text-yellow-700 dark:text-yellow-400">
              Note: {result.failed_provider_revocations.length} code(s) could
              not be revoked at the lock provider. They have been marked as
              revoked locally.
            </p>
          )}
          <button
            onClick={() => setResult(null)}
            className="mt-2 text-xs text-green-600 underline hover:no-underline dark:text-green-400"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Error state */}
      {lockoutError && (
        <div className="mt-3 rounded-md border border-red-200 bg-red-100 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/40 dark:text-red-300">
          {lockoutError}
          <button
            onClick={() => setLockoutError(null)}
            className="ml-2 underline hover:no-underline"
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Voice Assistant Links Panel
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function VoiceLinksPanel({
  links,
  onRefresh,
}: {
  links: VoiceAssistantLink[];
  onRefresh: () => void;
}) {
  const [linking, setLinking] = useState<VoicePlatform | null>(null);

  const handleLink = async (platform: VoicePlatform) => {
    if (platform === "google") {
      alert("Google Assistant integration is coming soon.");
      return;
    }

    setLinking(platform);
    try {
      await api.post("/iot/voice-links/", { platform });
      onRefresh();
    } catch (err: any) {
      alert(`Failed to link: ${err?.message ?? "Unknown error"}`);
    } finally {
      setLinking(null);
    }
  };

  const handleUnlink = async (link: VoiceAssistantLink) => {
    if (
      !confirm(
        `Unlink ${link.platform_display}? You'll no longer be able to use voice commands.`
      )
    )
      return;
    try {
      await api.delete(`/iot/voice-links/${link.uuid}/`);
      onRefresh();
    } catch (err: any) {
      alert(`Failed to unlink: ${err?.message ?? "Unknown error"}`);
    }
  };

  const linkedPlatforms = new Set(links.map((l) => l.platform));

  return (
    <div className="space-y-6">
      {/* Available Platforms */}
      <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
        <h2 className="text-base font-semibold text-[hsl(var(--card-foreground))]">
          Voice Assistants
        </h2>
        <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
          Link a voice assistant to manage bookings and check locks with
          voice commands.
        </p>
        <div className="mt-4 space-y-3">
          {(Object.keys(VOICE_PLATFORM_INFO) as VoicePlatform[]).map(
            (platform) => {
              const info = VOICE_PLATFORM_INFO[platform];
              const isLinked = linkedPlatforms.has(platform);
              const matchedLink = links.find((l) => l.platform === platform);
              const isUnavailable = platform === "google";

              return (
                <div
                  key={platform}
                  className={`flex items-center justify-between rounded-lg border p-4 ${
                    isLinked
                      ? "border-green-200 bg-green-50/50 dark:border-green-800 dark:bg-green-900/10"
                      : "border-[hsl(var(--border))]"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{info.icon}</span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-[hsl(var(--foreground))]">
                          {info.name}
                        </span>
                        {isLinked && (
                          <span className="inline-flex rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
                            Linked
                          </span>
                        )}
                        {isUnavailable && !isLinked && (
                          <span className="inline-flex rounded-full bg-[hsl(var(--muted))] px-2 py-0.5 text-xs font-medium text-[hsl(var(--muted-foreground))]">
                            Coming Soon
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">
                        {info.description}
                      </p>
                      {isLinked && matchedLink && (
                        <p className="mt-0.5 text-xs text-[hsl(var(--muted-foreground))]">
                          Linked{" "}
                          {new Date(matchedLink.linked_at).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  </div>

                  <div>
                    {isLinked && matchedLink ? (
                      <button
                        onClick={() => handleUnlink(matchedLink)}
                        className="rounded-md border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/20"
                      >
                        Unlink
                      </button>
                    ) : (
                      <button
                        onClick={() => handleLink(platform)}
                        disabled={!!linking || isUnavailable}
                        className="rounded-md bg-[hsl(var(--primary))] px-3 py-1.5 text-xs font-medium text-[hsl(var(--primary-foreground))] transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {linking === platform ? "Linking..." : "Link"}
                      </button>
                    )}
                  </div>
                </div>
              );
            }
          )}
        </div>
      </div>

      {/* Voice Command Examples */}
      <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5">
        <h2 className="text-base font-semibold text-[hsl(var(--card-foreground))]">
          Voice Commands
        </h2>
        <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
          Once linked, try these commands with your voice assistant:
        </p>
        <div className="mt-3 space-y-2">
          {[
            {
              command: '"Book my usual Service Pro"',
              description: "Rebook with the same pro, place, and services",
            },
            {
              command: '"When is my next cleaning?"',
              description: "Get your next booking date, time, and place",
            },
            {
              command: '"Cancel my next booking"',
              description: "Begin cancellation (confirm in-app for security)",
            },
            {
              command: '"Is my front door locked?"',
              description: "Check the status of your connected smart lock",
            },
            {
              command: '"List my upcoming cleanings"',
              description: "Hear a summary of your next 5 bookings",
            },
          ].map((example, idx) => (
            <div
              key={idx}
              className="flex items-start gap-3 rounded-md bg-[hsl(var(--accent))] px-3 py-2.5"
            >
              <span className="mt-0.5 text-sm">🗣️</span>
              <div>
                <div className="text-sm font-medium text-[hsl(var(--foreground))]">
                  {example.command}
                </div>
                <div className="text-xs text-[hsl(var(--muted-foreground))]">
                  {example.description}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
