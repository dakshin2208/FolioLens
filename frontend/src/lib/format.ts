const inrFmt = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export const inr = (x: number | null | undefined) => (x == null ? "–" : inrFmt.format(x));
export const num = (x: number | string | null | undefined, digits = 4) =>
  x == null ? "–" : new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(Number(x));
export const pct = (x: number | null | undefined, digits = 1) =>
  x == null ? "–" : `${(x * 100).toFixed(digits)}%`;
export const signedPct = (x: number | null | undefined, digits = 1) =>
  x == null ? "–" : `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(digits)}%`;
export const signedInr = (x: number | null | undefined) =>
  x == null ? "–" : `${x >= 0 ? "+" : "−"}${inrFmt.format(Math.abs(x))}`;

/** Compact Indian notation: 12.4L, 1.2Cr */
export const inrShort = (x: number) => {
  const a = Math.abs(x);
  if (a >= 1e7) return `₹${(x / 1e7).toFixed(2)}Cr`;
  if (a >= 1e5) return `₹${(x / 1e5).toFixed(1)}L`;
  if (a >= 1e3) return `₹${(x / 1e3).toFixed(0)}K`;
  return `₹${x.toFixed(0)}`;
};

export const date = (iso: string | null | undefined) =>
  iso
    ? new Date(iso + (iso.length === 10 ? "T00:00:00" : "")).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "–";

export const shortDate = (iso: string) =>
  new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { month: "short", year: "2-digit" });

export const relativeTime = (iso: string | null | undefined) => {
  if (!iso) return "–";
  const t = new Date(iso.length === 10 ? iso + "T00:00:00" : iso).getTime();
  const s = Math.round((Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} d ago`;
  return date(iso.slice(0, 10));
};

export const titleCase = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export const initials = (name: string) =>
  name
    .replace(/\(.*?\)/g, "")
    .split(/[\s.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("") || "?";

/** Stable colour for an avatar, from the name. */
const HUES = [222, 168, 32, 262, 340, 196, 12, 140];
export const avatarHue = (name: string) => {
  let h = 7;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return HUES[h % HUES.length]!;
};

export const ASSET_COLORS: Record<string, string> = {
  equity: "var(--series-1)",
  debt: "var(--series-2)",
  gold: "var(--series-3)",
  cash: "var(--series-6)",
  hybrid: "var(--series-4)",
  other: "var(--series-8)",
};
export const SERIES = [1, 2, 3, 4, 5, 6, 7, 8].map((i) => `var(--series-${i})`);
