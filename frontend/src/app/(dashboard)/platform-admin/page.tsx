"use client";

import Link from "next/link";

interface AdminCard {
  title: string;
  description: string;
  href: string;
  iconColor: string;
  iconBg: string;
  icon: React.ReactNode;
  active: boolean;
}

const ADMIN_CARDS: AdminCard[] = [
  {
    title: "Platform Governance",
    description:
      "Global kill switches, privacy audit trail, and break-glass session management.",
    href: "/platform-admin/governance",
    iconColor: "text-red-600 dark:text-red-400",
    iconBg: "bg-red-50 dark:bg-red-900/20",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
      </svg>
    ),
    active: true,
  },
  {
    title: "Secret Vault",
    description:
      "Manage 3rd-party API keys with scoped permissions, auto-rotation, and environment toggles.",
    href: "/platform-admin/vault",
    iconColor: "text-amber-600 dark:text-amber-400",
    iconBg: "bg-amber-50 dark:bg-amber-900/20",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" />
      </svg>
    ),
    active: true,
  },
  {
    title: "Permissions Matrix",
    description:
      "Provision and revoke role-level access across all platform features in a single grid.",
    href: "/platform-admin/permissions",
    iconColor: "text-violet-600 dark:text-violet-400",
    iconBg: "bg-violet-50 dark:bg-violet-900/20",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25a2.25 2.25 0 01-2.25-2.25v-2.25z" />
      </svg>
    ),
    active: true,
  },
  {
    title: "User Security",
    description:
      "Force password resets, manage MFA enrollment, and lock/unlock accounts across all roles.",
    href: "/platform-admin/user-security",
    iconColor: "text-emerald-600 dark:text-emerald-400",
    iconBg: "bg-emerald-50 dark:bg-emerald-900/20",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-1.997M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
      </svg>
    ),
    active: true,
  },
  {
    title: "IoT Integrations",
    description: "Manage OAuth2 smart-home provider connections.",
    href: "#",
    iconColor: "text-blue-600 dark:text-blue-400",
    iconBg: "bg-blue-50 dark:bg-blue-900/20",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 16.875h3.375m0 0h3.375m-3.375 0V13.5m0 3.375v3.375M6 10.5h2.25a2.25 2.25 0 002.25-2.25V6a2.25 2.25 0 00-2.25-2.25H6A2.25 2.25 0 003.75 6v2.25A2.25 2.25 0 006 10.5zm0 9.75h2.25A2.25 2.25 0 0010.5 18v-2.25a2.25 2.25 0 00-2.25-2.25H6a2.25 2.25 0 00-2.25 2.25V18A2.25 2.25 0 006 20.25zm9.75-9.75H18a2.25 2.25 0 002.25-2.25V6A2.25 2.25 0 0018 3.75h-2.25A2.25 2.25 0 0013.5 6v2.25a2.25 2.25 0 002.25 2.25z" />
      </svg>
    ),
    active: false,
  },
];

export default function PlatformAdminDashboard() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[hsl(var(--foreground))]">
            Platform Admin Dashboard
          </h1>
          <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
            System administration, governance controls, and platform oversight.
          </p>
        </div>

        {/* Cmd+K hint */}
        <button
          onClick={() => document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))}
          className="hidden items-center gap-2 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-3 py-1.5 text-xs text-[hsl(var(--muted-foreground))] transition-colors hover:bg-[hsl(var(--muted))] sm:flex"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          Search
          <kbd className="rounded border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-1 py-0.5 text-[10px] font-medium">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Quick Actions Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {ADMIN_CARDS.map((card) =>
          card.active ? (
            <Link
              key={card.title}
              href={card.href}
              className="group rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 transition-all hover:border-brand-500/30 hover:shadow-sm"
            >
              <div
                className={`mb-3 flex h-10 w-10 items-center justify-center rounded-lg ${card.iconBg} ${card.iconColor}`}
              >
                {card.icon}
              </div>
              <h3 className="text-sm font-semibold text-[hsl(var(--foreground))] group-hover:text-brand-500">
                {card.title}
              </h3>
              <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
                {card.description}
              </p>
            </Link>
          ) : (
            <div
              key={card.title}
              className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 opacity-60"
            >
              <div
                className={`mb-3 flex h-10 w-10 items-center justify-center rounded-lg ${card.iconBg} ${card.iconColor}`}
              >
                {card.icon}
              </div>
              <h3 className="text-sm font-semibold text-[hsl(var(--foreground))]">
                {card.title}
              </h3>
              <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
                {card.description}
              </p>
            </div>
          ),
        )}
      </div>
    </div>
  );
}
