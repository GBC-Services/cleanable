"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import { ROLES } from "@/types/auth";
import type { CommandPaletteResult, SearchResultType } from "@/types/admin-backend";
import { RESULT_TYPE_META } from "@/types/admin-backend";

// ── Helpers ──────────────────────────────────────────────────────────

function cn(...classes: (string | false | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

// ── Type Icons ───────────────────────────────────────────────────────

function ResultIcon({ type }: { type: SearchResultType }) {
  const common = "h-4 w-4";
  switch (type) {
    case "user":
      return (
        <svg className={common} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
        </svg>
      );
    case "vault":
      return (
        <svg className={common} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" />
        </svg>
      );
    case "feature":
      return (
        <svg className={common} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      );
    case "integration":
      return (
        <svg className={common} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 16.875h3.375m0 0h3.375m-3.375 0V13.5m0 3.375v3.375M6 10.5h2.25a2.25 2.25 0 002.25-2.25V6a2.25 2.25 0 00-2.25-2.25H6A2.25 2.25 0 003.75 6v2.25A2.25 2.25 0 006 10.5zm0 9.75h2.25A2.25 2.25 0 0010.5 18v-2.25a2.25 2.25 0 00-2.25-2.25H6a2.25 2.25 0 00-2.25 2.25V18A2.25 2.25 0 006 20.25zm9.75-9.75H18a2.25 2.25 0 002.25-2.25V6A2.25 2.25 0 0018 3.75h-2.25A2.25 2.25 0 0013.5 6v2.25a2.25 2.25 0 002.25 2.25z" />
        </svg>
      );
    case "navigation":
    default:
      return (
        <svg className={common} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
        </svg>
      );
  }
}

// ── Type colors ──────────────────────────────────────────────────────

const TYPE_COLORS: Record<SearchResultType, string> = {
  user: "bg-blue-500/10 text-blue-600",
  vault: "bg-amber-500/10 text-amber-600",
  feature: "bg-violet-500/10 text-violet-600",
  integration: "bg-emerald-500/10 text-emerald-600",
  navigation: "bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]",
};

// ── Command Palette Component ────────────────────────────────────────

export default function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CommandPaletteResult[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  // Only Platform Admins get the command palette
  const isAdmin = user?.role === ROLES.PLATFORM_ADMIN;

  // ── Keyboard shortcut: Cmd+K / Ctrl+K ────────────────────────────
  useEffect(() => {
    if (!isAdmin) return;

    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };

    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isAdmin]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery("");
      setResults([]);
      setSelectedIndex(0);
    }
  }, [isOpen]);

  // ── Search with debounce ──────────────────────────────────────────
  useEffect(() => {
    if (!isOpen || query.length < 2) {
      setResults([]);
      return;
    }

    setIsSearching(true);
    const timer = setTimeout(async () => {
      try {
        const data = await api.get<{ results: CommandPaletteResult[] }>(
          `/governance/command-palette/search/?q=${encodeURIComponent(query)}`,
        );
        setResults(data.results);
        setSelectedIndex(0);
      } catch (err) {
        console.error("Command palette search failed:", err);
        setResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [query, isOpen]);

  // ── Keyboard navigation ───────────────────────────────────────────
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, results.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter" && results[selectedIndex]) {
        e.preventDefault();
        handleSelect(results[selectedIndex]);
      }
    },
    [results, selectedIndex],
  );

  // Scroll selected item into view
  useEffect(() => {
    if (resultsRef.current) {
      const selected = resultsRef.current.children[selectedIndex] as HTMLElement;
      selected?.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  const handleSelect = (result: CommandPaletteResult) => {
    setIsOpen(false);
    router.push(result.url);
  };

  if (!isAdmin) return null;

  return (
    <>
      {/* Trigger hint (optional — subtle keyboard shortcut indicator) */}

      {/* Modal overlay */}
      {isOpen && (
        <div className="fixed inset-0 z-[100]">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setIsOpen(false)}
          />

          {/* Palette */}
          <div className="relative mx-auto mt-[15vh] w-full max-w-xl">
            <div className="overflow-hidden rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] shadow-2xl">
              {/* Search input */}
              <div className="flex items-center gap-3 border-b border-[hsl(var(--border))] px-4">
                <svg className="h-5 w-5 shrink-0 text-[hsl(var(--muted-foreground))]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                </svg>
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Search users, secrets, settings, or type a command..."
                  className="w-full bg-transparent py-3.5 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:outline-none"
                />
                <kbd className="hidden shrink-0 rounded border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-1.5 py-0.5 text-[10px] font-medium text-[hsl(var(--muted-foreground))] sm:inline-block">
                  ESC
                </kbd>
              </div>

              {/* Results */}
              <div ref={resultsRef} className="max-h-[50vh] overflow-y-auto">
                {query.length < 2 ? (
                  <div className="px-4 py-8 text-center text-xs text-[hsl(var(--muted-foreground))]">
                    Type to search users, secrets, features, and more...
                  </div>
                ) : isSearching ? (
                  <div className="px-4 py-8 text-center text-xs text-[hsl(var(--muted-foreground))]">
                    Searching...
                  </div>
                ) : results.length === 0 ? (
                  <div className="px-4 py-8 text-center text-xs text-[hsl(var(--muted-foreground))]">
                    No results for "{query}"
                  </div>
                ) : (
                  <div className="py-2">
                    {results.map((result, idx) => (
                      <button
                        key={`${result.type}-${result.id}`}
                        onClick={() => handleSelect(result)}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        className={cn(
                          "flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors",
                          idx === selectedIndex
                            ? "bg-[hsl(var(--muted))]"
                            : "hover:bg-[hsl(var(--muted))]/50",
                        )}
                      >
                        {/* Type icon */}
                        <div
                          className={cn(
                            "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                            TYPE_COLORS[result.type],
                          )}
                        >
                          <ResultIcon type={result.type} />
                        </div>

                        {/* Text */}
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-[hsl(var(--foreground))] truncate">
                            {result.title}
                          </p>
                          <p className="text-[11px] text-[hsl(var(--muted-foreground))] truncate">
                            {result.subtitle}
                          </p>
                        </div>

                        {/* Type badge */}
                        <span className="shrink-0 rounded-full bg-[hsl(var(--muted))] px-2 py-0.5 text-[10px] font-medium text-[hsl(var(--muted-foreground))]">
                          {RESULT_TYPE_META[result.type].label}
                        </span>

                        {/* Enter hint for selected */}
                        {idx === selectedIndex && (
                          <kbd className="hidden shrink-0 rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-1.5 py-0.5 text-[10px] font-medium text-[hsl(var(--muted-foreground))] sm:inline-block">
                            Enter
                          </kbd>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between border-t border-[hsl(var(--border))] px-4 py-2">
                <div className="flex items-center gap-3 text-[10px] text-[hsl(var(--muted-foreground))]">
                  <span className="flex items-center gap-1">
                    <kbd className="rounded border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-1 py-0.5 text-[9px]">↑↓</kbd>
                    Navigate
                  </span>
                  <span className="flex items-center gap-1">
                    <kbd className="rounded border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-1 py-0.5 text-[9px]">↵</kbd>
                    Select
                  </span>
                  <span className="flex items-center gap-1">
                    <kbd className="rounded border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-1 py-0.5 text-[9px]">esc</kbd>
                    Close
                  </span>
                </div>
                <span className="text-[10px] text-[hsl(var(--muted-foreground))]">
                  Admin Command Palette
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
