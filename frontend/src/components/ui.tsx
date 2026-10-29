import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Circle,
  Info,
  Loader2,
  X,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

import { avatarHue, initials } from "../lib/format";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
export { cx };

/* ------------------------------------------------------------------ Card */

export function Card({
  title,
  subtitle,
  action,
  icon: Icon,
  children,
  className = "",
  padded = true,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  icon?: LucideIcon;
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <section className={cx("min-w-0 rounded-2xl border border-line bg-surface shadow-card", className)}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 px-5 pb-1 pt-4">
          <div className="flex min-w-0 items-start gap-2.5">
            {Icon && <Icon size={17} className="mt-0.5 shrink-0 text-accent" />}
            <div className="min-w-0">
              {title && <h2 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h2>}
              {subtitle && <p className="mt-0.5 text-[12.5px] leading-snug text-muted">{subtitle}</p>}
            </div>
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      <div className={padded ? "p-5 pt-3" : "pt-2"}>{children}</div>
    </section>
  );
}

/* ---------------------------------------------------------------- Button */

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "subtle";
export function Button({
  variant = "primary",
  size = "md",
  icon: Icon,
  loading,
  className = "",
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "md" | "lg";
  icon?: LucideIcon;
  loading?: boolean;
}) {
  return (
    <button className={buttonCls(variant, size, className)} disabled={disabled || loading} {...props}>
      {loading ? <Loader2 size={size === "sm" ? 14 : 16} className="animate-spin" /> : Icon && <Icon size={size === "sm" ? 14 : 16} />}
      {children}
    </button>
  );
}

export function buttonCls(variant: ButtonVariant = "primary", size: "sm" | "md" | "lg" = "md", extra = "") {
  const styles: Record<ButtonVariant, string> = {
    primary: "bg-accent text-accent-ink font-semibold hover:bg-accent-hover shadow-sm",
    secondary: "border border-line-strong bg-surface text-ink hover:border-faint hover:bg-surface-2",
    danger: "bg-bad text-white hover:brightness-95",
    ghost: "text-ink-2 hover:bg-surface-2 hover:text-ink",
    subtle: "bg-surface-3 text-ink hover:bg-surface-3/70",
  };
  const sizes = { sm: "h-8 px-3 text-[13px] rounded-lg", md: "h-9 px-4 text-sm rounded-lg", lg: "h-11 px-5 text-[15px] rounded-xl" };
  return cx(
    "inline-flex select-none items-center justify-center gap-2 whitespace-nowrap font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
    styles[variant],
    sizes[size],
    extra,
  );
}

/* ----------------------------------------------------------------- Badge */

type Tone = "neutral" | "good" | "bad" | "warn" | "info" | "accent";
const TONES: Record<Tone, string> = {
  neutral: "bg-surface-3 text-ink-2 ring-line-strong",
  good: "bg-good-soft text-good ring-good/15",
  bad: "bg-bad-soft text-bad ring-bad/15",
  warn: "bg-warn-soft text-warn ring-warn/15",
  info: "bg-info/10 text-info ring-info/20",
  accent: "bg-accent text-accent-ink ring-transparent",
};

export function Badge({ tone = "neutral", icon: Icon, children, className = "" }: {
  tone?: Tone;
  icon?: LucideIcon;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", TONES[tone], className)}>
      {Icon && <Icon size={12} strokeWidth={2.4} />}
      {children}
    </span>
  );
}

const SEVERITY: Record<string, { label: string; tone: Tone; icon: LucideIcon }> = {
  high: { label: "High", tone: "bad", icon: AlertTriangle },
  medium: { label: "Medium", tone: "warn", icon: AlertCircle },
  low: { label: "Low", tone: "neutral", icon: Info },
};
/** Severity is always icon + label, never colour alone. */
export function SeverityBadge({ severity }: { severity: string }) {
  const s = SEVERITY[severity] ?? SEVERITY.low!;
  return <Badge tone={s.tone} icon={s.icon}>{s.label}</Badge>;
}
export const severityMeta = (s: string) => SEVERITY[s] ?? SEVERITY.low!;

const STATUS: Record<string, { label: string; tone: Tone; icon: LucideIcon; spin?: boolean }> = {
  queued: { label: "Queued", tone: "neutral", icon: Circle },
  processing: { label: "Processing", tone: "info", icon: Loader2, spin: true },
  needs_review: { label: "Needs review", tone: "warn", icon: AlertCircle },
  completed: { label: "Completed", tone: "good", icon: CheckCircle2 },
  failed: { label: "Failed", tone: "bad", icon: XCircle },
};
export function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? STATUS.queued!;
  const Icon = s.icon;
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", TONES[s.tone])}>
      <Icon size={12} strokeWidth={2.4} className={s.spin ? "animate-spin" : undefined} />
      {s.label}
    </span>
  );
}

/* ---------------------------------------------------------------- Notice */

export function Notice({ level = "info", title, children, action }: {
  level?: "info" | "warning" | "error" | "success";
  title?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
}) {
  const m = {
    info: { icon: Info, cls: "border-info/15 bg-info/[0.05]", ic: "text-info" },
    warning: { icon: AlertTriangle, cls: "border-warn/20 bg-warn-soft", ic: "text-warn" },
    error: { icon: XCircle, cls: "border-bad/20 bg-bad-soft", ic: "text-bad" },
    success: { icon: CheckCircle2, cls: "border-good/20 bg-good-soft", ic: "text-good" },
  }[level];
  const Icon = m.icon;
  return (
    <div className={cx("flex items-start gap-3 rounded-xl border px-4 py-3 text-[13px] text-ink-2", m.cls)} role={level === "error" ? "alert" : undefined}>
      <Icon size={16} className={cx("mt-0.5 shrink-0", m.ic)} />
      <div className="min-w-0 flex-1">
        {title && <div className="font-semibold text-ink">{title}</div>}
        {children && <div className={title ? "mt-0.5" : undefined}>{children}</div>}
      </div>
      {action}
    </div>
  );
}

/* --------------------------------------------------------- Loading states */

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted" role="status">
      <Loader2 size={16} className="animate-spin text-accent" />
      {label}…
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={cx("skeleton", className)} aria-hidden />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading">
      <div className="flex items-center gap-4">
        <Skeleton className="h-12 w-12 rounded-xl" />
        <div className="space-y-2">
          <Skeleton className="h-5 w-56" />
          <Skeleton className="h-4 w-40" />
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-72 lg:col-span-2 rounded-2xl" />
        <Skeleton className="h-72 rounded-2xl" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-56 rounded-2xl" />
        <Skeleton className="h-56 rounded-2xl" />
        <Skeleton className="h-56 rounded-2xl" />
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- Forms */

export function Field({ label, children, hint, error }: { label: string; children: ReactNode; hint?: ReactNode; error?: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-ink">{label}</span>
      {children}
      {error ? <span className="mt-1.5 block text-xs text-bad">{error}</span> : hint && <span className="mt-1.5 block text-xs text-muted">{hint}</span>}
    </label>
  );
}

export const inputCls =
  "h-10 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm text-ink outline-none transition placeholder:text-faint focus:border-accent focus:ring-2 focus:ring-accent/20";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(inputCls, props.className)} />;
}

export function Checkbox({ checked, onChange, children }: { checked: boolean; onChange: (v: boolean) => void; children: ReactNode }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 text-[13px] leading-relaxed text-ink-2">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded border-line-strong accent-[var(--accent)]"
      />
      <span>{children}</span>
    </label>
  );
}

/* ---------------------------------------------------------------- Avatar */

export function Avatar({ name, size = 40, className = "" }: { name: string; size?: number; className?: string }) {
  const h = avatarHue(name);
  return (
    <span
      className={cx("grid shrink-0 place-items-center rounded-xl font-semibold", className)}
      style={{
        width: size,
        height: size,
        fontSize: size * 0.36,
        background: `color-mix(in srgb, hsl(${h} 70% 55%) 14%, var(--surface))`,
        color: `color-mix(in srgb, hsl(${h} 60% 38%) 85%, var(--ink))`,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, hsl(${h} 60% 50%) 22%, transparent)`,
      }}
      aria-hidden
    >
      {initials(name)}
    </span>
  );
}

/* ------------------------------------------------------------------ Tabs */

export function Tabs<T extends string>({ tabs, value, onChange, className = "" }: {
  tabs: { id: T; label: string; icon?: LucideIcon; count?: number; dot?: boolean }[];
  value: T;
  onChange: (t: T) => void;
  className?: string;
}) {
  return (
    <div className={cx("no-scrollbar -mx-1 flex gap-1 overflow-x-auto border-b border-line px-1", className)} role="tablist">
      {tabs.map((t) => {
        const active = t.id === value;
        const Icon = t.icon;
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(t.id)}
            className={cx(
              "relative -mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3 pb-3 pt-2 text-[14px] font-medium transition-colors",
              active ? "border-accent text-ink" : "border-transparent text-muted hover:text-ink",
            )}
          >
            {Icon && <Icon size={15} className={active ? "text-accent" : undefined} />}
            {t.label}
            {t.count != null && t.count > 0 && (
              <span className={cx("rounded-full px-1.5 text-[11px] font-semibold tabular", active ? "bg-accent-soft text-accent" : "bg-surface-3 text-ink-2")}>
                {t.count}
              </span>
            )}
            {t.dot && <span className="h-1.5 w-1.5 rounded-full bg-warn" aria-label="needs attention" />}
          </button>
        );
      })}
    </div>
  );
}

export function Segmented<T extends string>({ options, value, onChange }: {
  options: { id: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex flex-wrap rounded-lg border border-line bg-surface-2 p-0.5" role="radiogroup">
      {options.map((o) => (
        <button
          key={o.id}
          role="radio"
          aria-checked={o.id === value}
          onClick={() => onChange(o.id)}
          className={cx(
            "rounded-md px-2.5 py-1 text-xs font-medium transition",
            o.id === value ? "bg-surface text-ink shadow-sm ring-1 ring-line" : "text-muted hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------- Progress */

export function Meter({ value, max = 1, color = "var(--accent)", marker, className = "h-1.5" }: {
  value: number;
  max?: number;
  color?: string;
  marker?: number;
  className?: string;
}) {
  const w = Math.max(0, Math.min(1, value / max)) * 100;
  return (
    <div className={cx("relative w-full rounded-full bg-surface-3", className)}>
      <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${w}%`, background: color }} />
      {marker != null && (
        <div className="absolute -top-1.5 -bottom-1.5 w-[3px] -translate-x-1/2 rounded bg-ink ring-2 ring-surface" style={{ left: `${Math.min(1, marker / max) * 100}%` }} title="Review limit" />
      )}
    </div>
  );
}

/* ------------------------------------------------------------ Empty state */

export function EmptyState({ icon: Icon, title, children, action }: {
  icon: LucideIcon;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-line-strong bg-surface px-6 py-14 text-center">
      <span className="grid h-12 w-12 place-items-center rounded-xl bg-accent-soft text-accent">
        <Icon size={22} />
      </span>
      <h3 className="mt-4 text-base font-semibold text-ink">{title}</h3>
      {children && <div className="mt-1.5 max-w-md text-sm text-muted">{children}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/* ----------------------------------------------------------------- Modal */

export function Modal({ open, onClose, title, description, children, footer, width = "max-w-lg" }: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    setTimeout(() => ref.current?.querySelector<HTMLElement>("input, button:not([data-close])")?.focus(), 30);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center" role="dialog" aria-modal aria-label={title}>
      <div className="fade-in absolute inset-0 bg-[var(--overlay)] backdrop-blur-[2px]" onClick={onClose} />
      <div ref={ref} className={cx("pop-in relative w-full rounded-2xl border border-line-strong bg-surface shadow-float", width)}>
        <div className="flex items-start justify-between gap-4 px-6 pt-6">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-ink">{title}</h2>
            {description && <p className="mt-1 text-sm text-muted">{description}</p>}
          </div>
          <button data-close className="rounded-lg p-1 text-muted hover:bg-surface-2 hover:text-ink" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        {children && <div className="px-6 pt-5">{children}</div>}
        <div className="mt-6 flex justify-end gap-2 rounded-b-2xl border-t border-line bg-surface-2 px-6 py-4">{footer}</div>
      </div>
    </div>,
    document.body,
  );
}

/* ----------------------------------------------------------------- Toast */

type ToastItem = { id: number; tone: "success" | "error" | "info"; text: string };
const ToastCtx = createContext<(tone: ToastItem["tone"], text: string) => void>(() => undefined);
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((tone: ToastItem["tone"], text: string) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, tone, text }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 4200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      {createPortal(
        <div className="no-print pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
          {items.map((t) => {
            const Icon = t.tone === "success" ? CheckCircle2 : t.tone === "error" ? XCircle : Info;
            const c = t.tone === "success" ? "text-good" : t.tone === "error" ? "text-bad" : "text-accent";
            return (
              <div key={t.id} className="pop-in pointer-events-auto flex items-start gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-sm text-ink shadow-float">
                <Icon size={18} className={cx("mt-px shrink-0", c)} />
                <span className="flex-1">{t.text}</span>
                <button className="text-faint hover:text-ink" onClick={() => setItems((x) => x.filter((i) => i.id !== t.id))} aria-label="Dismiss">
                  <X size={16} />
                </button>
              </div>
            );
          })}
        </div>,
        document.body,
      )}
    </ToastCtx.Provider>
  );
}

/* --------------------------------------------------------- Page heading */

export function PageHeader({ title, subtitle, leading, actions, meta }: {
  title: ReactNode;
  subtitle?: ReactNode;
  leading?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex min-w-0 items-center gap-4">
        {leading}
        <div className="min-w-0">
          <h1 className="text-[22px] font-semibold tracking-tight text-ink sm:text-[26px]">{title}</h1>
          {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
          {meta && <div className="mt-2 flex flex-wrap items-center gap-2">{meta}</div>}
        </div>
      </div>
      {actions && <div className="no-print flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function useDocumentTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} · FolioLens` : "FolioLens";
  }, [title]);
}

/* ------------------------------------------------------------------ Help */

/** A small "?" that explains a term in plain words, on hover or keyboard focus. */
export function Help({ children, label = "What does this mean?" }: { children: ReactNode; label?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex align-middle" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        aria-label={label}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((o) => !o)}
        className="no-print grid h-4 w-4 place-items-center rounded-full bg-surface-3 text-[10px] font-bold text-muted hover:bg-accent-soft hover:text-accent"
      >
        ?
      </button>
      {open && (
        <span role="tooltip" className="pop-in absolute left-1/2 top-6 z-40 w-64 -translate-x-1/2 rounded-xl border border-line bg-surface p-3 text-left text-[12.5px] font-normal normal-case leading-relaxed tracking-normal text-ink-2 shadow-float">
          {children}
        </span>
      )}
    </span>
  );
}

/* --------------------------------------------------------------- Stepper */

export type StepState = "done" | "current" | "todo";
/** The few steps of a job, so the advisor always knows where they are and what comes next. */
export function Stepper({ steps }: { steps: { label: string; hint?: string; state: StepState; onClick?: () => void }[] }) {
  return (
    <ol className={cx("grid gap-2", steps.length >= 5 ? "sm:grid-cols-3 xl:grid-cols-5" : "sm:grid-cols-4")}>
      {steps.map((s, i) => {
        const Tag = s.onClick ? "button" : "div";
        return (
          <li key={s.label}>
            <Tag
              {...(s.onClick ? { onClick: s.onClick, type: "button" as const } : {})}
              className={cx(
                "flex w-full items-start gap-3 rounded-xl border px-3.5 py-3 text-left transition",
                s.state === "current" ? "border-accent/40 bg-accent-soft" : "border-line bg-surface",
                s.onClick && "hover:border-accent/40",
              )}
            >
              <span
                className={cx(
                  "grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-bold",
                  s.state === "done" ? "bg-good text-white" : s.state === "current" ? "bg-accent text-accent-ink" : "bg-surface-3 text-muted",
                )}
              >
                {s.state === "done" ? <CheckCircle2 size={14} strokeWidth={2.6} /> : i + 1}
              </span>
              <span className="min-w-0">
                <span className={cx("block text-[13px] font-semibold", s.state === "todo" ? "text-muted" : "text-ink")}>{s.label}</span>
                {s.hint && <span className="mt-0.5 block text-xs text-muted">{s.hint}</span>}
              </span>
            </Tag>
          </li>
        );
      })}
    </ol>
  );
}
