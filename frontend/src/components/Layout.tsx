import { BookOpen, ChevronRight, FileBarChart2, LogOut, Menu, Moon, Search, Sun, Users, X, type LucideIcon } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";

import { api, auth } from "../lib/api";
import { inrShort } from "../lib/format";
import { applyTheme, getTheme, type Theme } from "../lib/theme";
import type { PortfolioSummary } from "../lib/types";
import { CommandPalette } from "./terminal";
import { Avatar, buttonCls, cx } from "./ui";

export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="8" fill="var(--brand)" />
      {/* a lens over three rising bars */}
      <circle cx="14" cy="14" r="7.6" fill="none" stroke="#fff" strokeWidth="2.4" />
      <path d="M19.6 19.6l5.4 5.4" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
      <rect x="10.2" y="14.2" width="2" height="3.6" rx="1" fill="#fff" />
      <rect x="13" y="12" width="2" height="5.8" rx="1" fill="#fff" />
      <rect x="15.8" y="10.2" width="2" height="7.6" rx="1" fill="#fff" />
    </svg>
  );
}

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2.5 text-[17px] font-bold tracking-tight text-ink">
      <LogoMark />
      <span>
        Folio<span className="text-accent">Lens</span>
      </span>
    </Link>
  );
}

export const DISCLAIMER =
  "FolioLens provides portfolio analytics for information and education only. It is not investment advice. Consult a SEBI-registered investment adviser before making investment decisions.";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>(getTheme);
  const next: Theme = theme === "light" ? "dark" : "light";
  return (
    <button
      type="button"
      onClick={() => {
        applyTheme(next);
        setTheme(next);
      }}
      className={cx("rounded-lg p-2 text-nav-muted hover:bg-surface-2 hover:text-ink", className)}
      title={`Switch to ${next} theme`}
      aria-label={`Switch to ${next} theme`}
    >
      {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
    </button>
  );
}

/* ------------------------------------------------------- Marketing shell */

export function MarketingLayout({ children }: { children: ReactNode }) {
  const signedIn = Boolean(auth.token);
  return (
    <div className="min-h-screen bg-page">
      <CommandPalette />
      <header className="sticky top-0 z-30 border-b border-line bg-surface/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <nav className="flex items-center gap-1 text-[14px]">
            <a href="#how" className="hidden rounded-lg px-3 py-2 text-ink-2 hover:text-ink md:block">How it works</a>
            <Link to="/demo" className="hidden rounded-lg px-3 py-2 text-ink-2 hover:text-ink sm:block">Sample report</Link>
            <Link to="/methodology" className="hidden rounded-lg px-3 py-2 text-ink-2 hover:text-ink md:block">How we calculate</Link>
            <ThemeToggle />
            {signedIn ? (
              <Link to="/app" className={buttonCls("primary", "sm", "ml-2")}>Open my clients</Link>
            ) : (
              <>
                <Link to="/login" className="rounded-lg px-3 py-2 text-ink-2 hover:text-ink">Sign in</Link>
                <Link to="/register" className={buttonCls("primary", "sm", "ml-1")}>Get started</Link>
              </>
            )}
          </nav>
        </div>
      </header>
      {children}
      <footer className="border-t border-line bg-surface">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-[1fr_auto]">
          <div className="max-w-md">
            <Logo />
            <p className="mt-3 text-sm text-muted">Portfolio reviews for Indian financial advisors: checked numbers, clear explanations, a report your client understands.</p>
          </div>
          <div className="flex gap-12 text-sm">
            <div className="space-y-2">
              <div className="label">Product</div>
              <Link to="/demo" className="block text-ink-2 hover:text-ink">Sample report</Link>
              <Link to="/methodology" className="block text-ink-2 hover:text-ink">How we calculate</Link>
            </div>
            <div className="space-y-2">
              <div className="label">Account</div>
              <Link to="/login" className="block text-ink-2 hover:text-ink">Sign in</Link>
              <Link to="/register" className="block text-ink-2 hover:text-ink">Create account</Link>
            </div>
          </div>
          <p className="text-xs leading-relaxed text-faint md:col-span-2">{DISCLAIMER}</p>
        </div>
      </footer>
    </div>
  );
}

/* -------------------------------------------------------------- App shell */

function NavItem({ to, icon: Icon, label, end, onClick }: { to: string; icon: LucideIcon; label: string; end?: boolean; onClick?: () => void }) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) =>
        cx(
          "flex items-center gap-3 rounded-lg px-3 py-2 text-[14px] font-medium transition-colors",
          isActive ? "bg-accent-soft text-accent" : "text-nav-muted hover:bg-surface-2 hover:text-ink",
        )
      }
    >
      <Icon size={17} />
      <span className="flex-1">{label}</span>
    </NavLink>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const navigate = useNavigate();
  const location = useLocation();
  const signedIn = Boolean(auth.token);
  const [email, setEmail] = useState<string | null>(null);
  const [clients, setClients] = useState<PortfolioSummary[]>([]);

  useEffect(() => {
    if (!signedIn) return;
    api.me().then((m) => setEmail(m.email)).catch(() => undefined);
    const load = () => api.portfolios().then(setClients).catch(() => undefined);
    load();
    window.addEventListener("foliolens:portfolios", load);
    return () => window.removeEventListener("foliolens:portfolios", load);
  }, [signedIn]);

  return (
    <div className="flex h-full flex-col border-r border-line bg-nav px-3 py-4">
      <div className="flex items-center justify-between px-2 pb-5 pt-0.5">
        <Logo />
        <ThemeToggle />
      </div>

      <button
        onClick={() => window.dispatchEvent(new Event("foliolens:palette"))}
        className="mb-5 flex items-center gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2 text-left text-[13px] text-muted hover:border-line-strong hover:text-ink-2"
      >
        <Search size={15} />
        <span className="flex-1">Find a client…</span>
        <kbd className="rounded border border-line-strong bg-surface px-1 text-[10.5px]">⌘K</kbd>
      </button>

      <nav className="space-y-0.5">
        {signedIn && <NavItem to="/app" end icon={Users} label="My clients" onClick={onNavigate} />}
        <NavItem to="/demo" icon={FileBarChart2} label="Sample report" onClick={onNavigate} />
        <NavItem to="/methodology" icon={BookOpen} label="How we calculate" onClick={onNavigate} />
      </nav>

      {signedIn && clients.length > 0 && (
        <>
          <div className="label mt-7 flex items-center justify-between px-3 pb-2">
            <span>Recent clients</span>
            <span className="text-faint">{clients.length}</span>
          </div>
          <div className="scroll-thin -mr-1 space-y-px overflow-y-auto pr-1">
            {clients.slice(0, 8).map((c) => {
              const active = location.pathname.startsWith(`/app/p/${c.id}`);
              return (
                <Link
                  key={c.id}
                  to={`/app/p/${c.id}`}
                  onClick={onNavigate}
                  className={cx(
                    "flex items-center gap-2.5 rounded-lg px-3 py-1.5 text-[13px] transition-colors",
                    active ? "bg-surface-2 font-medium text-ink" : "text-nav-muted hover:bg-surface-2 hover:text-ink",
                  )}
                >
                  <span
                    className={cx("h-2 w-2 shrink-0 rounded-full", c.last_upload_status === "needs_review" ? "bg-warn" : c.current_value != null ? "bg-good" : "bg-faint")}
                    title={c.last_upload_status === "needs_review" ? "Import needs review" : c.current_value != null ? "Report ready" : "No report yet"}
                  />
                  <span className="flex-1 truncate">{c.client_name}</span>
                  <span className="tabular shrink-0 text-[12px] text-muted">{c.current_value != null ? inrShort(c.current_value) : "—"}</span>
                </Link>
              );
            })}
          </div>
        </>
      )}

      <div className="mt-auto pt-6">
        {signedIn ? (
          <div className="flex items-center gap-3 rounded-xl border border-line bg-surface-2 p-2.5">
            <Avatar name={email ?? "You"} size={32} className="!rounded-lg" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium text-ink">{email ?? "Signed in"}</div>
              <div className="text-[11.5px] text-muted">Advisor</div>
            </div>
            <button
              className="rounded-lg p-1.5 text-muted hover:bg-surface-3 hover:text-ink"
              title="Sign out"
              aria-label="Sign out"
              onClick={() => {
                auth.set(null);
                navigate("/");
              }}
            >
              <LogOut size={15} />
            </button>
          </div>
        ) : (
          <div className="rounded-xl border border-accent/20 bg-accent-soft p-4">
            <div className="text-sm font-semibold text-ink">Try it on a real statement</div>
            <p className="mt-1 text-xs leading-relaxed text-ink-2">Upload a CAS or broker export and get this review in about a minute.</p>
            <Link to="/register" onClick={onNavigate} className={buttonCls("primary", "sm", "mt-3 w-full")}>Create free account</Link>
            <Link to="/login" onClick={onNavigate} className="mt-2 block text-center text-xs text-muted hover:text-ink">Sign in</Link>
          </div>
        )}
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);
  // Braces matter: newer Chrome returns a Promise from scrollTo, and React would call it as a cleanup.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-page">
      <CommandPalette />
      <aside className="no-print fixed inset-y-0 left-0 z-30 hidden w-[256px] lg:block">
        <Sidebar />
      </aside>

      <div className="no-print sticky top-0 z-20 lg:hidden">
        <div className="flex h-14 items-center justify-between border-b border-line bg-nav px-4">
          <Logo />
          <button className="rounded-lg p-2 text-ink-2 hover:bg-surface-2" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu size={20} />
          </button>
        </div>
      </div>

      {open && (
        <div className="no-print fixed inset-0 z-40 lg:hidden">
          <div className="fade-in absolute inset-0 bg-[var(--overlay)]" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-[284px] shadow-float">
            <Sidebar onNavigate={() => setOpen(false)} />
            <button className="absolute right-3 top-16 rounded-lg p-1.5 text-muted hover:bg-surface-2" onClick={() => setOpen(false)} aria-label="Close menu">
              <X size={18} />
            </button>
          </div>
        </div>
      )}

      <div className="lg:pl-[256px]">
        <main className="print-full mx-auto max-w-[1240px] px-4 py-7 sm:px-6 lg:px-10">{children}</main>
        <footer className="no-print mx-auto max-w-[1240px] px-4 pb-8 text-[11.5px] leading-relaxed text-faint sm:px-6 lg:px-10">{DISCLAIMER}</footer>
      </div>
    </div>
  );
}

export function Breadcrumbs({ items }: { items: { label: string; to?: string }[] }) {
  return (
    <nav className="no-print mb-3 flex items-center gap-1.5 text-[13px] text-muted" aria-label="Breadcrumb">
      {items.map((it, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <ChevronRight size={13} className="text-faint" />}
          {it.to ? <Link to={it.to} className="hover:text-accent">{it.label}</Link> : <span className="text-ink-2">{it.label}</span>}
        </span>
      ))}
    </nav>
  );
}
