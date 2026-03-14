"use client";

import { useState, type FormEvent } from "react";
import { useAuthStore } from "@/lib/auth-store";
import type { AuthResponse, LoginPayload } from "@/types/auth";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { setAuth, getDashboardPath } = useAuthStore();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await fetch("/api/v1/auth/login/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password } satisfies LoginPayload),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(
          data.non_field_errors?.[0] ?? data.detail ?? "Login failed.",
        );
      }

      const data: AuthResponse = await res.json();
      setAuth(data.user, data.tokens);

      // Set cookie for middleware
      document.cookie = `cleanable-access-token=${data.tokens.access}; path=/; max-age=${15 * 60}; SameSite=Lax`;

      // Redirect to role-appropriate dashboard
      window.location.href = getDashboardPath();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-[hsl(var(--border))] bg-white p-8 shadow-sm dark:bg-[hsl(var(--card))]">
      <h2 className="mb-6 text-xl font-semibold">Sign in</h2>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="email" className="mb-1 block text-sm font-medium">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-[hsl(var(--border))] bg-white px-3 py-2 text-sm outline-none transition focus:ring-2 focus:ring-brand-500/30 dark:bg-[hsl(var(--muted))]"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label htmlFor="password" className="mb-1 block text-sm font-medium">
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-[hsl(var(--border))] bg-white px-3 py-2 text-sm outline-none transition focus:ring-2 focus:ring-brand-500/30 dark:bg-[hsl(var(--muted))]"
            placeholder="••••••••"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-50"
        >
          {loading ? "Signing in..." : "Sign in"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-[hsl(var(--muted-foreground))]">
        Don&apos;t have an account?{" "}
        <a href="/register" className="text-brand-500 hover:underline">
          Sign up
        </a>
      </p>
    </div>
  );
}
