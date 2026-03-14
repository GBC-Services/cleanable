/**
 * Next.js Edge Middleware — Role-Based Route Protection
 * =====================================================
 *
 * Runs on every navigation request at the edge.  Reads the JWT from
 * the ``cleanable-auth`` localStorage-backed cookie (set via a thin
 * client helper) and enforces:
 *
 *   1. Unauthenticated users hitting protected routes → /login
 *   2. Authenticated users hitting /login or /register → their dashboard
 *   3. Authenticated users hitting a dashboard they don't own → their dashboard
 *
 * Token verification is *decode-only* at the edge (HS256 verification
 * requires the secret, which stays on the API server).  The API layer
 * is the source of truth — this middleware is a UX guardrail.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { decodeJwt } from "jose";

// ── Role → dashboard path mapping (must match auth.ts) ──────────────

const ROLE_PATHS: Record<number, string> = {
  10: "/resident",
  20: "/platform-admin",
  30: "/agency-owner",
  40: "/service-pro",
  50: "/support-architect",
  60: "/qa-inspector",
};

// ── Public paths that never require auth ─────────────────────────────

const PUBLIC_PATHS = new Set(["/login", "/register", "/forgot-password"]);

// ── Protected path prefixes (dashboard route groups) ─────────────────

const PROTECTED_PREFIXES = [
  "/resident",
  "/service-pro",
  "/agency-owner",
  "/qa-inspector",
  "/support-architect",
  "/platform-admin",
];

// ── Helpers ──────────────────────────────────────────────────────────

function getTokenFromRequest(request: NextRequest): string | null {
  // Strategy 1: Read from the cookie set by the client-side auth flow
  const authCookie = request.cookies.get("cleanable-access-token");
  if (authCookie?.value) return authCookie.value;

  // Strategy 2: Read from Authorization header (API calls proxied through Next)
  const authHeader = request.headers.get("authorization");
  if (authHeader?.startsWith("Bearer ")) {
    return authHeader.slice(7);
  }

  return null;
}

interface TokenClaims {
  role: number;
  exp: number;
  email: string;
}

function decodeToken(token: string): TokenClaims | null {
  try {
    const payload = decodeJwt(token);
    if (
      typeof payload.role !== "number" ||
      typeof payload.exp !== "number"
    ) {
      return null;
    }
    return {
      role: payload.role as number,
      exp: payload.exp as number,
      email: (payload.email as string) ?? "",
    };
  } catch {
    return null;
  }
}

function isExpired(claims: TokenClaims): boolean {
  return Date.now() >= claims.exp * 1000;
}

function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

function getDashboardForRole(role: number): string {
  return ROLE_PATHS[role] ?? "/login";
}

/**
 * Check whether a user with `role` is allowed to access `pathname`.
 * Each role is restricted to its own dashboard prefix.
 */
function isAuthorizedForPath(role: number, pathname: string): boolean {
  const allowedPrefix = ROLE_PATHS[role];
  if (!allowedPrefix) return false;
  return pathname.startsWith(allowedPrefix);
}

// ── Middleware ────────────────────────────────────────────────────────

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip static assets and API proxy
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.startsWith("/static") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  const token = getTokenFromRequest(request);
  const claims = token ? decodeToken(token) : null;
  const isAuth = claims !== null && !isExpired(claims);

  // ── Case 1: Unauthenticated user on a protected route ──────────
  if (!isAuth && isProtectedPath(pathname)) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // ── Case 2: Authenticated user on a public auth page ───────────
  if (isAuth && PUBLIC_PATHS.has(pathname)) {
    const dashboard = getDashboardForRole(claims!.role);
    return NextResponse.redirect(new URL(dashboard, request.url));
  }

  // ── Case 3: Authenticated user on wrong dashboard ──────────────
  if (isAuth && isProtectedPath(pathname)) {
    if (!isAuthorizedForPath(claims!.role, pathname)) {
      const correctDashboard = getDashboardForRole(claims!.role);
      return NextResponse.redirect(new URL(correctDashboard, request.url));
    }
  }

  // ── Case 4: Root path → redirect to dashboard or login ─────────
  if (pathname === "/") {
    if (isAuth) {
      const dashboard = getDashboardForRole(claims!.role);
      return NextResponse.redirect(new URL(dashboard, request.url));
    }
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     *  - _next/static (static files)
     *  - _next/image (image optimization)
     *  - favicon.ico (browser favicon)
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
