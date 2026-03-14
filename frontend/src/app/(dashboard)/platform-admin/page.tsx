"use client";

import Link from "next/link";

export default function PlatformAdminDashboard() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-[hsl(var(--foreground))]">
          Platform Admin Dashboard
        </h1>
        <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
          System administration, governance controls, and platform oversight.
        </p>
      </div>

      {/* Quick Actions Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Link
          href="/platform-admin/governance"
          className="group rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 transition-all hover:border-brand-500/30 hover:shadow-sm"
        >
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-[hsl(var(--foreground))] group-hover:text-brand-500">
            Platform Governance
          </h3>
          <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
            Global kill switches, privacy audit trail, and break-glass session management.
          </p>
        </Link>

        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 opacity-60">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-1.997M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-[hsl(var(--foreground))]">
            User Management
          </h3>
          <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
            Manage users, assign roles, and handle verifications.
          </p>
        </div>

        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 opacity-60">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-purple-50 text-purple-600 dark:bg-purple-900/20 dark:text-purple-400">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 16.875h3.375m0 0h3.375m-3.375 0V13.5m0 3.375v3.375M6 10.5h2.25a2.25 2.25 0 002.25-2.25V6a2.25 2.25 0 00-2.25-2.25H6A2.25 2.25 0 003.75 6v2.25A2.25 2.25 0 006 10.5zm0 9.75h2.25A2.25 2.25 0 0010.5 18v-2.25a2.25 2.25 0 00-2.25-2.25H6a2.25 2.25 0 00-2.25 2.25V18A2.25 2.25 0 006 20.25zm9.75-9.75H18a2.25 2.25 0 002.25-2.25V6A2.25 2.25 0 0018 3.75h-2.25A2.25 2.25 0 0013.5 6v2.25a2.25 2.25 0 002.25 2.25z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-[hsl(var(--foreground))]">
            IoT Integrations
          </h3>
          <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
            Manage OAuth2 smart-home provider connections.
          </p>
        </div>
      </div>
    </div>
  );
}
