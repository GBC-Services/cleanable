"use client";

import { useAuthStore } from "@/lib/auth-store";
import { useEffect, useState } from "react";
import { ROLES } from "@/types/auth";
import CommandPalette from "@/components/CommandPalette";

/**
 * Dashboard layout — shared across all role route groups.
 * Provides the sidebar shell; role-specific content is rendered
 * by the nested layout in each route group.
 */

interface NavItem {
  label: string;
  href: string;
}

function getNavItems(role: number): NavItem[] {
  const base = (() => {
    switch (role) {
      case ROLES.PLATFORM_ADMIN:
        return "/platform-admin";
      case ROLES.RESIDENT:
        return "/resident";
      case ROLES.SERVICE_PRO:
        return "/service-pro";
      case ROLES.AGENCY_OWNER:
        return "/agency-owner";
      case ROLES.QA_INSPECTOR:
        return "/qa-inspector";
      case ROLES.SUPPORT_ARCHITECT:
        return "/support-architect";
      default:
        return "/";
    }
  })();

  const items: NavItem[] = [{ label: "Dashboard", href: base }];

  if (role === ROLES.PLATFORM_ADMIN) {
    items.push({ label: "Governance", href: `${base}/governance` });
    items.push({ label: "Vault", href: `${base}/vault` });
    items.push({ label: "Permissions", href: `${base}/permissions` });
    items.push({ label: "User Security", href: `${base}/user-security` });
  }

  if (role === ROLES.AGENCY_OWNER) {
    items.push({ label: "Finances", href: `${base}/finances` });
  }

  if (role === ROLES.SUPPORT_ARCHITECT) {
    items.push({ label: "Break-Glass", href: `${base}/break-glass` });
  }

  if (role === ROLES.RESIDENT) {
    items.push({ label: "Book a Cleaning", href: `${base}/book` });
    items.push({ label: "My Bookings", href: `${base}/bookings` });
  }

  return items;
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isAuthenticated, logout } = useAuthStore();
  const [hydrated, setHydrated] = useState(false);

  // Wait for Zustand to rehydrate from localStorage before acting on auth state
  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated && !isAuthenticated) {
      window.location.href = "/login";
    }
  }, [hydrated, isAuthenticated]);

  if (!hydrated || !isAuthenticated || !user) {
    return null;
  }

  const navItems = getNavItems(user.role);

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="hidden w-64 shrink-0 border-r border-[hsl(var(--border))] bg-white p-6 dark:bg-[hsl(var(--card))] lg:block">
        <div className="mb-8">
          <h1 className="text-lg font-bold text-brand-500">Cleanable</h1>
          <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">
            {user.role_display}
          </p>
        </div>

        <nav className="space-y-1">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="block rounded-lg px-3 py-2 text-sm font-medium text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))]"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="absolute bottom-6 left-6 right-6">
          <div className="mb-3 truncate text-sm font-medium">
            {user.first_name} {user.last_name}
          </div>
          <div className="mb-3 truncate text-xs text-[hsl(var(--muted-foreground))]">
            {user.email}
          </div>
          <button
            onClick={() => {
              document.cookie =
                "cleanable-access-token=; path=/; max-age=0";
              logout();
              window.location.href = "/login";
            }}
            className="text-sm text-red-500 hover:underline"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-6 lg:p-8">{children}</main>

      {/* Global Command Palette (Cmd+K) — only renders for Platform Admins */}
      <CommandPalette />
    </div>
  );
}
