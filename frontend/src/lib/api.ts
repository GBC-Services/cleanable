/**
 * API Client
 * ==========
 *
 * Thin fetch wrapper with automatic JWT injection and token refresh.
 * Server components call Django directly; client components go
 * through Next.js rewrites to avoid CORS.
 */

import type { TokenPair } from "@/types/auth";
import { useAuthStore } from "@/lib/auth-store";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

interface FetchOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Skip the Authorization header (for public endpoints). */
  noAuth?: boolean;
}

/**
 * Core fetch function.  Automatically:
 *   1. Sets Authorization: Bearer <access>
 *   2. Retries once on 401 after refreshing the token
 *   3. Throws on non‑2xx responses with parsed error body
 */
export async function apiFetch<T = unknown>(
  endpoint: string,
  options: FetchOptions = {},
): Promise<T> {
  const { body, noAuth, ...init } = options;
  const headers = new Headers(init.headers);

  if (!noAuth) {
    const token = useAuthStore.getState().tokens?.access;
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const url = endpoint.startsWith("http")
    ? endpoint
    : `${API_BASE}/api/v1${endpoint}`;

  let response = await fetch(url, {
    ...init,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // ── Transparent token refresh on 401 ─────────────────────────────
  if (response.status === 401 && !noAuth) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      headers.set(
        "Authorization",
        `Bearer ${useAuthStore.getState().tokens!.access}`,
      );
      response = await fetch(url, {
        ...init,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    }
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, error);
  }

  // 204 No Content
  if (response.status === 204) return undefined as T;

  return response.json() as Promise<T>;
}

/**
 * Attempt to refresh the access token using the stored refresh token.
 * Returns true if successful.
 */
async function refreshAccessToken(): Promise<boolean> {
  const store = useAuthStore.getState();
  const refresh = store.tokens?.refresh;
  if (!refresh) return false;

  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) {
      store.logout();
      return false;
    }
    const data: TokenPair = await res.json();
    store.setTokens(data);
    return true;
  } catch {
    store.logout();
    return false;
  }
}

/**
 * Structured API error with status code and parsed body.
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    public body: Record<string, unknown>,
  ) {
    super(`API ${status}: ${JSON.stringify(body)}`);
    this.name = "ApiError";
  }
}

// ── Convenience methods ────────────────────────────────────────────

/**
 * Fetch with FormData (for file uploads). Skips JSON content-type
 * so the browser sets multipart/form-data with the correct boundary.
 */
export async function apiFormData<T = unknown>(
  endpoint: string,
  formData: FormData,
): Promise<T> {
  const headers = new Headers();
  const token = useAuthStore.getState().tokens?.access;
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  // Do NOT set Content-Type — browser will set multipart/form-data

  const url = endpoint.startsWith("http")
    ? endpoint
    : `${API_BASE}/api/v1${endpoint}`;

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, error);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(endpoint: string, opts?: FetchOptions) =>
    apiFetch<T>(endpoint, { ...opts, method: "GET" }),

  post: <T>(endpoint: string, body?: unknown, opts?: FetchOptions) =>
    apiFetch<T>(endpoint, { ...opts, method: "POST", body }),

  patch: <T>(endpoint: string, body?: unknown, opts?: FetchOptions) =>
    apiFetch<T>(endpoint, { ...opts, method: "PATCH", body }),

  put: <T>(endpoint: string, body?: unknown, opts?: FetchOptions) =>
    apiFetch<T>(endpoint, { ...opts, method: "PUT", body }),

  delete: <T>(endpoint: string, opts?: FetchOptions) =>
    apiFetch<T>(endpoint, { ...opts, method: "DELETE" }),

  postFormData: <T>(endpoint: string, formData: FormData) =>
    apiFormData<T>(endpoint, formData),
};
