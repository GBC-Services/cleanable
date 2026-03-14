"use client";

import { useState, type FormEvent } from "react";
import { useAuthStore } from "@/lib/auth-store";
import { ROLES, type AuthResponse, type RegisterPayload, type RoleValue } from "@/types/auth";

const PUBLIC_ROLES: { value: RoleValue; label: string; description: string }[] = [
  {
    value: ROLES.RESIDENT,
    label: "Resident",
    description: "Book cleaning services for your home",
  },
  {
    value: ROLES.SERVICE_PRO,
    label: "Service Pro",
    description: "Join as a cleaning professional",
  },
  {
    value: ROLES.AGENCY_OWNER,
    label: "Agency Owner",
    description: "Register your cleaning company",
  },
];

export default function RegisterPage() {
  const [form, setForm] = useState<RegisterPayload>({
    email: "",
    password: "",
    password_confirm: "",
    first_name: "",
    last_name: "",
    role: ROLES.RESIDENT,
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { setAuth, getDashboardPath } = useAuthStore();

  function update(field: keyof RegisterPayload, value: string | number) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await fetch("/api/v1/auth/register/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const firstError =
          Object.values(data).flat()[0] ?? "Registration failed.";
        throw new Error(String(firstError));
      }

      const data: AuthResponse = await res.json();
      setAuth(data.user, data.tokens);

      document.cookie = `cleanable-access-token=${data.tokens.access}; path=/; max-age=${15 * 60}; SameSite=Lax`;
      window.location.href = getDashboardPath();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-[hsl(var(--border))] bg-white p-8 shadow-sm dark:bg-[hsl(var(--card))]">
      <h2 className="mb-6 text-xl font-semibold">Create your account</h2>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Role selector */}
        <fieldset>
          <legend className="mb-2 text-sm font-medium">I am a...</legend>
          <div className="grid grid-cols-1 gap-2">
            {PUBLIC_ROLES.map((r) => (
              <label
                key={r.value}
                className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition ${
                  form.role === r.value
                    ? "border-brand-500 bg-brand-50 dark:bg-brand-500/10"
                    : "border-[hsl(var(--border))] hover:border-brand-300"
                }`}
              >
                <input
                  type="radio"
                  name="role"
                  value={r.value}
                  checked={form.role === r.value}
                  onChange={() => update("role", r.value)}
                  className="accent-brand-500"
                />
                <div>
                  <span className="text-sm font-medium">{r.label}</span>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">
                    {r.description}
                  </p>
                </div>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="first_name" className="mb-1 block text-sm font-medium">
              First name
            </label>
            <input
              id="first_name"
              type="text"
              value={form.first_name}
              onChange={(e) => update("first_name", e.target.value)}
              className="w-full rounded-lg border border-[hsl(var(--border))] bg-white px-3 py-2 text-sm outline-none transition focus:ring-2 focus:ring-brand-500/30 dark:bg-[hsl(var(--muted))]"
            />
          </div>
          <div>
            <label htmlFor="last_name" className="mb-1 block text-sm font-medium">
              Last name
            </label>
            <input
              id="last_name"
              type="text"
              value={form.last_name}
              onChange={(e) => update("last_name", e.target.value)}
              className="w-full rounded-lg border border-[hsl(var(--border))] bg-white px-3 py-2 text-sm outline-none transition focus:ring-2 focus:ring-brand-500/30 dark:bg-[hsl(var(--muted))]"
            />
          </div>
        </div>

        <div>
          <label htmlFor="reg-email" className="mb-1 block text-sm font-medium">
            Email
          </label>
          <input
            id="reg-email"
            type="email"
            required
            value={form.email}
            onChange={(e) => update("email", e.target.value)}
            className="w-full rounded-lg border border-[hsl(var(--border))] bg-white px-3 py-2 text-sm outline-none transition focus:ring-2 focus:ring-brand-500/30 dark:bg-[hsl(var(--muted))]"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label htmlFor="reg-password" className="mb-1 block text-sm font-medium">
            Password
          </label>
          <input
            id="reg-password"
            type="password"
            required
            value={form.password}
            onChange={(e) => update("password", e.target.value)}
            className="w-full rounded-lg border border-[hsl(var(--border))] bg-white px-3 py-2 text-sm outline-none transition focus:ring-2 focus:ring-brand-500/30 dark:bg-[hsl(var(--muted))]"
            placeholder="••••••••"
          />
        </div>

        <div>
          <label htmlFor="reg-confirm" className="mb-1 block text-sm font-medium">
            Confirm password
          </label>
          <input
            id="reg-confirm"
            type="password"
            required
            value={form.password_confirm}
            onChange={(e) => update("password_confirm", e.target.value)}
            className="w-full rounded-lg border border-[hsl(var(--border))] bg-white px-3 py-2 text-sm outline-none transition focus:ring-2 focus:ring-brand-500/30 dark:bg-[hsl(var(--muted))]"
            placeholder="••••••••"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-50"
        >
          {loading ? "Creating account..." : "Create account"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-[hsl(var(--muted-foreground))]">
        Already have an account?{" "}
        <a href="/login" className="text-brand-500 hover:underline">
          Sign in
        </a>
      </p>
    </div>
  );
}
