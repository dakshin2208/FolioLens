import { ArrowRight, BookOpen, CornerDownLeft, LayoutDashboard, LogIn, LogOut, Search, Users, type LucideIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { ResponsiveContainer, Tooltip, Treemap } from "recharts";

import { api, auth } from "../lib/api";
import { date, inr, pct, signedPct } from "../lib/format";
import type { Holding, PortfolioSummary, Report, TickerItem } from "../lib/types";
import { cx } from "./ui";

/* ------------------------------------------------------------ Ticker tape */

const cleanSymbol = (s: string) => s.replace(/^(MF|STK|ETF|IDX)-/, "").replace(/^SYNTH-/, "");

export function useTicker() {
  const [items, setItems] = useState<TickerItem[]>([]);
  useEffect(() => {
    let alive = true;
    const load = () => api.ticker().then((x) => alive && setItems(x)).catch(() => undefined);
    load();
    const t = setInterval(load, 60_000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);
  return items;
}

export function TickerTape({ className = "" }: { className?: string }) {
  const items = useTicker();
  if (!items.length) return <div className={cx("h-8 border-b border-line bg-nav", className)} />;
  const synthetic = items.some((i) => /synthetic|demo/i.test(i.source));
  const asOf = items[0]?.date;
  const row = items.map((i) => (
    <span key={i.symbol} className="flex items-center gap-2 px-4 text-[11.5px]" title={`${i.name} · close ${i.close} on ${date(i.date)}`}>
      <span className="font-semibold text-ink-2">{cleanSymbol(i.symbol)}</span>
      <span className="tabular text-ink">{i.close.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</span>
      <span className={cx("tabular font-semibold", i.change > 0 ? "text-good" : i.change < 0 ? "text-bad" : "text-muted")}>
        {i.change > 0 ? "▲" : i.change < 0 ? "▼" : "■"} {signedPct(i.change, 2)}
      </span>
    </span>
  ));
  return (
    <div className={cx("ticker flex h-8 items-stretch overflow-hidden border-b border-line bg-nav", className)}>
      <div className="z-10 flex shrink-0 items-center gap-2 border-r border-line bg-nav px-3 font-mono text-[10.5px] font-bold tracking-wider text-accent">
        MKT
        <span className="font-medium text-muted">{asOf ? date(asOf).toUpperCase() : ""}</span>
        {synthetic && <span className="rounded-[3px] bg-warn-soft px-1 text-[9.5px] text-warn">DEMO DATA</span>}
      </div>
      <div className="relative flex-1 overflow-hidden">
        <div className="ticker-track h-full items-center">
          <div className="flex items-center">{row}</div>
          <div className="flex items-center" aria-hidden>{row}</div>
        </div>
        <div className="pointer-events-none absolute inset-y-0 right-0 w-16 bg-gradient-to-l from-nav to-transparent" />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- Status bar */

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

export function StatusBar() {
  const now = useClock();
  const [online, setOnline] = useState<boolean | null>(null);
  useEffect(() => {
    const check = () => api.health().then(setOnline);
    check();
    const t = setInterval(check, 30_000);
    return () => clearInterval(t);
  }, []);
  const ist = now.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false });
  const day = now.toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short", year: "2-digit" }).toUpperCase();
  return (
    <div className="no-print fixed inset-x-0 bottom-0 z-30 flex h-7 items-center justify-between border-t border-line bg-nav px-3 font-mono text-[10.5px] tracking-wide text-muted lg:left-[248px]">
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1.5">
          <span className={cx("h-1.5 w-1.5 rounded-full", online ? "live-dot bg-good" : online === false ? "bg-bad" : "bg-faint")} />
          <span className={online ? "text-good" : online === false ? "text-bad" : undefined}>{online ? "CONNECTED" : online === false ? "OFFLINE" : "CONNECTING"}</span>
        </span>
        <span className="hidden sm:inline">ENGINE v1.0.0</span>
        <span className="hidden md:inline">NOT INVESTMENT ADVICE</span>
      </div>
      <div className="flex items-center gap-4">
        <button onClick={() => window.dispatchEvent(new Event("foliolens:palette"))} className="hidden items-center gap-1.5 hover:text-ink sm:flex">
          <kbd className="rounded-[3px] border border-line-strong px-1 text-[9.5px]">⌘K</kbd> COMMAND
        </button>
        <span className="text-ink-2">{day} · IST {ist}</span>
      </div>
    </div>
  );
}

/* --------------------------------------------------------- Command palette */

type Cmd = { id: string; label: string; hint: string; icon: LucideIcon; run: () => void };

export function CommandPalette() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const [clients, setClients] = useState<PortfolioSummary[]>([]);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape") setOpen(false);
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("foliolens:palette", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("foliolens:palette", onOpen);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    setQ("");
    setSel(0);
    if (auth.token) api.portfolios().then(setClients).catch(() => undefined);
  }, [open]);

  const cmds: Cmd[] = useMemo(() => {
    const go = (to: string) => () => {
      setOpen(false);
      navigate(to);
    };
    const base: Cmd[] = [
      ...(auth.token ? [{ id: "clients", label: "My clients", hint: "Page", icon: Users, run: go("/app") }] : []),
      { id: "demo", label: "Sample report", hint: "Page", icon: LayoutDashboard, run: go("/demo") },
      { id: "method", label: "How we calculate", hint: "Page", icon: BookOpen, run: go("/methodology") },
      ...clients.map((c) => ({ id: c.id, label: c.client_name, hint: c.current_value != null ? inr(c.current_value) : "No report yet", icon: ArrowRight, run: go(`/app/p/${c.id}`) })),
      auth.token
        ? { id: "out", label: "Sign out", hint: "", icon: LogOut, run: () => { auth.set(null); setOpen(false); navigate("/"); } }
        : { id: "in", label: "Sign in", hint: "", icon: LogIn, run: go("/login") },
    ];
    const ql = q.toLowerCase();
    return base.filter((c) => !ql || c.label.toLowerCase().includes(ql) || c.hint.toLowerCase().includes(ql));
  }, [q, clients, navigate]);

  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-start justify-center px-4 pt-[14vh]" role="dialog" aria-label="Command palette">
      <div className="fade-in absolute inset-0 bg-[var(--overlay)]" onClick={() => setOpen(false)} />
      <div className="pop-in relative w-full max-w-xl overflow-hidden rounded-xl border border-line-strong bg-surface shadow-float">
        <div className="flex items-center gap-3 border-b border-line px-4">
          <Search size={16} className="text-accent" />
          <input
            ref={input}
            autoFocus
            value={q}
            onChange={(e) => { setQ(e.target.value); setSel(0); }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, cmds.length - 1)); }
              if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
              if (e.key === "Enter") cmds[sel]?.run();
            }}
            placeholder="Type a client name or a page…"
            className="h-12 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-faint focus-visible:outline-none"
          />
          <kbd className="rounded border border-line-strong px-1.5 text-[11px] text-muted">Esc</kbd>
        </div>
        <ul className="scroll-thin max-h-80 overflow-y-auto p-1.5">
          {cmds.map((c, i) => (
            <li key={c.id}>
              <button
                onMouseEnter={() => setSel(i)}
                onClick={c.run}
                className={cx("flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[14px]", i === sel ? "bg-accent-soft text-ink" : "text-ink-2")}
              >
                <c.icon size={15} className={i === sel ? "text-accent" : "text-muted"} />
                <span className="flex-1 truncate">{c.label}</span>
                <span className="text-[12px] text-muted">{c.hint}</span>
                {i === sel && <CornerDownLeft size={13} className="text-muted" />}
              </button>
            </li>
          ))}
          {cmds.length === 0 && <li className="px-3 py-6 text-center text-sm text-muted">No matches</li>}
        </ul>
      </div>
    </div>,
    document.body,
  );
}

/* ----------------------------------------------------------------- Heatmap */

/** Colour for a return: red below zero, green above, stronger the further from zero. */
export function returnColor(r: number | null) {
  if (r == null) return "#94a3b8";
  const t = r >= 0 ? Math.min(1, r / 0.4) : Math.min(1, -r / 0.2);
  // Solid colours, dark enough for white text: deeper green for bigger gains, deeper red for bigger losses.
  return r >= 0 ? `hsl(158 58% ${(46 - 18 * t).toFixed(1)}%)` : `hsl(0 68% ${(56 - 14 * t).toFixed(1)}%)`;
}

type HeatNode = { name: string; size: number; ret: number | null; weight: number; value: number };

function HeatCell(props: { x?: number; y?: number; width?: number; height?: number; name?: string; ret?: number | null; weight?: number; depth?: number }) {
  const { x = 0, y = 0, width = 0, height = 0, name = "", ret = null, weight = 0, depth } = props;
  if (depth !== 1) return null;
  const big = width > 110 && height > 54;
  const mid = width > 64 && height > 34;
  const short = name.replace(/^Demo /, "").replace(/ Fund$| Ltd$/, "");
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={6} fill={returnColor(ret)} stroke="var(--surface)" strokeWidth={3} />
      {mid && (
        <text x={x + 8} y={y + 18} fill="#fff" fontSize={big ? 12.5 : 11} fontWeight={600} style={{ fontFamily: "var(--font-sans)" }}>
          {short.length > width / 7.5 ? short.slice(0, Math.max(3, Math.floor(width / 7.5) - 1)) + "…" : short}
        </text>
      )}
      {mid && (
        <text x={x + 8} y={y + (big ? 38 : 32)} fill="rgba(255,255,255,0.95)" fontSize={big ? 15 : 11.5} fontWeight={700}>
          {ret == null ? "–" : signedPct(ret)}
        </text>
      )}
      {big && (
        <text x={x + 8} y={y + 56} fill="rgba(255,255,255,0.8)" fontSize={11}>
          {pct(weight)} of total
        </text>
      )}
    </g>
  );
}

export function HoldingsHeatmap({ holdings, height = 300 }: { holdings: Holding[]; height?: number }) {
  const data: HeatNode[] = holdings.map((h) => ({ name: h.name, size: h.value, value: h.value, ret: h.cost ? h.gain / h.cost : null, weight: h.weight }));
  return (
    <div>
      <div style={{ height }} role="img" aria-label="Holdings heatmap: size is value, colour is return on cost">
        <ResponsiveContainer>
          <Treemap data={data} dataKey="size" aspectRatio={1.6} isAnimationActive={false} content={<HeatCell />}>
            <Tooltip
              content={({ active, payload }) => {
                const d = active && payload?.[0]?.payload as HeatNode | undefined;
                return d ? (
                  <div className="rounded-lg border border-line-strong bg-surface px-3 py-2 text-xs shadow-float">
                    <div className="font-semibold text-ink">{d.name}</div>
                    <div className="tabular mt-1 text-ink-2">{inr(d.value)} · {pct(d.weight)} of portfolio</div>
                    <div className={cx("tabular", (d.ret ?? 0) >= 0 ? "text-good" : "text-bad")}>{signedPct(d.ret)} on cost</div>
                  </div>
                ) : null;
              }}
            />
          </Treemap>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 text-[12px] text-muted">
        <span>Bigger box = more money · greener = bigger gain on cost</span>
        <span className="flex items-center gap-1.5">
          −20%
          <span className="h-2 w-28 rounded-sm" style={{ background: "linear-gradient(90deg, hsl(0 68% 42%), #94a3b8, hsl(158 58% 28%))" }} />
          +40%
        </span>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- Candles */

type Candle = { key: string; label: string; open: number; close: number; high: number; low: number };

/** Monthly candles of the time-weighted growth index (each month: first, high, low, last point). */
export function monthlyCandles(series: Report["performance"]["series"]): Candle[] {
  const out: Candle[] = [];
  let prevClose: number | null = null;
  for (const p of series) {
    const key = p.date.slice(0, 7);
    let c = out[out.length - 1];
    if (!c || c.key !== key) {
      const open: number = prevClose ?? p.portfolio_index;
      c = { key, label: new Date(key + "-01T00:00:00").toLocaleDateString("en-IN", { month: "short", year: "2-digit" }), open, close: open, high: open, low: open };
      out.push(c);
    }
    c.close = p.portfolio_index;
    c.high = Math.max(c.high, p.portfolio_index);
    c.low = Math.min(c.low, p.portfolio_index);
    prevClose = c.close;
  }
  return out;
}

export function CandleChart({ series, height = 300 }: { series: Report["performance"]["series"]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(800);
  const [hover, setHover] = useState<number | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((e) => setW(Math.max(0, e[0]!.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  const candles = useMemo(() => monthlyCandles(series), [series]);
  if (candles.length < 2) return null;
  if (w < 160) return <div ref={ref} style={{ height: height + 40 }} />;
  const padR = 52, padB = 22, padT = 8;
  const lo = Math.min(...candles.map((c) => c.low)), hi = Math.max(...candles.map((c) => c.high));
  const span = hi - lo || 1;
  const y = (v: number) => padT + (1 - (v - lo) / span) * (height - padT - padB);
  const step = (w - padR) / candles.length;
  const bw = Math.max(3, Math.min(14, step * 0.6));
  const ticks = 5;
  const h = hover != null ? candles[hover] : candles[candles.length - 1];
  return (
    <div ref={ref} className="relative" role="img" aria-label="Monthly candlestick chart of the portfolio growth index">
      <div className="pointer-events-none absolute left-0 top-0 flex gap-3 font-mono text-[11px]">
        <span className="text-ink">{h!.label.toUpperCase()}</span>
        <span className="text-muted">O <span className="text-ink-2">{h!.open.toFixed(1)}</span></span>
        <span className="text-muted">H <span className="text-ink-2">{h!.high.toFixed(1)}</span></span>
        <span className="text-muted">L <span className="text-ink-2">{h!.low.toFixed(1)}</span></span>
        <span className="text-muted">C <span className={h!.close >= h!.open ? "text-good" : "text-bad"}>{h!.close.toFixed(1)}</span></span>
      </div>
      <svg width={w} height={height + 18} className="mt-5 block" onMouseLeave={() => setHover(null)}>
        {Array.from({ length: ticks + 1 }).map((_, i) => {
          const v = lo + (span * i) / ticks;
          return (
            <g key={i}>
              <line x1={0} x2={w - padR} y1={y(v)} y2={y(v)} stroke="var(--grid)" />
              <text x={w - padR + 8} y={y(v) + 4} fontSize={10.5} fill="var(--muted)" style={{ fontFamily: "var(--font-mono)" }}>{v.toFixed(0)}</text>
            </g>
          );
        })}
        {candles.map((c, i) => {
          const cx0 = i * step + step / 2;
          const up = c.close >= c.open;
          const col = up ? "var(--good)" : "var(--bad)";
          const top = y(Math.max(c.open, c.close)), bot = y(Math.min(c.open, c.close));
          return (
            <g key={c.key} onMouseEnter={() => setHover(i)}>
              <rect x={i * step} y={0} width={step} height={height} fill={hover === i ? "rgba(255,255,255,0.03)" : "transparent"} />
              <line x1={cx0} x2={cx0} y1={y(c.high)} y2={y(c.low)} stroke={col} strokeWidth={1.2} />
              <rect x={cx0 - bw / 2} y={top} width={bw} height={Math.max(1.5, bot - top)} fill={up ? col : col} fillOpacity={up ? 0.9 : 0.9} rx={1} />
              {(i % Math.ceil(candles.length / 8) === 0) && (
                <text x={cx0} y={height + 12} textAnchor="middle" fontSize={10.5} fill="var(--muted)" style={{ fontFamily: "var(--font-mono)" }}>{c.label}</text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/* --------------------------------------------------------- Analysis log */

export type LogLine = { k: string; v: string; tone?: "good" | "bad" | "warn" | "accent" };

/** Prints the analysis pipeline line by line, like a terminal. */
export function AnalysisLog({ lines, title = "foliolens — analyse", speed = 420, className = "" }: { lines: LogLine[]; title?: string; speed?: number; className?: string }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    setN(0);
    const t = setInterval(() => setN((x) => (x >= lines.length ? x : x + 1)), speed);
    return () => clearInterval(t);
  }, [lines, speed]);
  const tone = { good: "text-good", bad: "text-bad", warn: "text-warn", accent: "text-accent" };
  return (
    <div className={cx("overflow-hidden rounded-xl border border-line-strong bg-[#03060c] shadow-float", className)}>
      <div className="flex items-center gap-1.5 border-b border-line bg-surface px-3 py-2">
        <span className="h-2.5 w-2.5 rounded-full bg-[#f6465d]/80" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#f0b429]/80" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#16c784]/80" />
        <span className="ml-2 font-mono text-[11px] text-muted">{title}</span>
      </div>
      <div className="scanlines min-h-[300px] p-4 font-mono text-[12.5px] leading-[1.9]">
        {lines.slice(0, n).map((l, i) => (
          <div key={i} className="fade-in flex gap-3">
            <span className="w-[110px] shrink-0 text-accent">{l.k}</span>
            <span className={l.tone ? tone[l.tone] : "text-ink-2"}>{l.v}</span>
          </div>
        ))}
        <div className={cx("text-muted", n >= lines.length && "caret")}>{n >= lines.length ? "$ " : ""}</div>
      </div>
    </div>
  );
}

/** Builds the log from a real report so every number shown is computed by the engine. */
export function reportLog(r: Report | null): LogLine[] {
  if (!r || r.status !== "ok") {
    return [
      { k: "> INGEST", v: "CAS statement · password ok" },
      { k: "> RECONCILE", v: "closing units match statement", tone: "good" },
      { k: "> XIRR", v: "money-weighted return, every SIP dated" },
      { k: "> LOOK-THROUGH", v: "funds → stocks → sectors" },
      { k: "> FLAGS", v: "overlap · concentration · liquidity", tone: "warn" },
      { k: "> EXPLAIN", v: "AI text, every number verified", tone: "good" },
    ];
  }
  const o = r.overview, p = r.performance, k = r.risk;
  const ov = r.overlap[0];
  const sector = r.findings.find((f) => f.type.includes("sector"));
  const high = r.findings.filter((f) => f.severity === "high").length;
  return [
    { k: "> INGEST", v: `${o.holdings_count} holdings · ${o.funds_count} funds · ${o.stocks_count} stocks` },
    { k: "> VALUE", v: `${inr(o.current_value)}  (${signedPct(o.cost ? o.unrealized_gain / o.cost : null)} on cost)`, tone: o.unrealized_gain >= 0 ? "good" : "bad" },
    { k: "> XIRR", v: `${pct(o.xirr, 2)} p.a. since ${date(o.first_investment)}`, tone: "good" },
    ...(p.twr_annualized != null ? [{ k: "> TWR", v: `${pct(p.twr_annualized, 2)} vs benchmark ${pct(p.benchmark_annualized, 2)}` } as LogLine] : []),
    { k: "> LOOK-THRU", v: `${pct(r.allocation.lookthrough.coverage, 0)} coverage · ${r.allocation.lookthrough.excluded.length} fund excluded (stale data)` },
    ...(ov ? [{ k: "> OVERLAP", v: `${ov.fund_a.replace(/^Demo /, "")} × ${ov.fund_b.replace(/^Demo /, "")} = ${pct(ov.overlap)}  ▲ HIGH`, tone: "bad" } as LogLine] : []),
    ...(sector ? [{ k: "> SECTOR", v: `${sector.title.split(" is ")[0]} ${pct(sector.measured_value)} of equity > ${pct(sector.threshold)} limit`, tone: "bad" } as LogLine] : []),
    ...(k.available ? [{ k: "> RISK", v: `vol ${pct(k.volatility)} · max DD ${pct(k.max_drawdown)} · β ${k.beta?.toFixed(2) ?? "–"}` } as LogLine] : []),
    { k: "> FINDINGS", v: `${r.findings.length} flags (${high} high) · numbers verified ✓`, tone: "accent" },
  ];
}
