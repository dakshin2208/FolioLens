import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { date, inr, inrShort, pct, shortDate } from "../lib/format";
import type { Report } from "../lib/types";

type Series = Report["performance"]["series"];

const AXIS = { stroke: "transparent", tick: { fill: "var(--muted)", fontSize: 11.5 }, tickLine: false, axisLine: false };

export type Range = "1Y" | "3Y" | "ALL";
export const RANGES: { id: Range; label: string }[] = [
  { id: "1Y", label: "1Y" },
  { id: "3Y", label: "3Y" },
  { id: "ALL", label: "All" },
];

export function sliceRange(series: Series, range: Range): Series {
  if (range === "ALL" || !series.length) return series;
  const end = new Date(series[series.length - 1]!.date + "T00:00:00");
  end.setFullYear(end.getFullYear() - (range === "1Y" ? 1 : 3));
  const cut = end.toISOString().slice(0, 10);
  const out = series.filter((p) => p.date >= cut);
  return out.length > 1 ? out : series;
}

function TipBox({ label, rows }: { label: string; rows: { name: string; value: string; color: string }[] }) {
  return (
    <div className="min-w-[190px] rounded-xl border border-line bg-surface px-3 py-2.5 text-[12.5px] shadow-float">
      <div className="mb-1.5 text-[12px] font-medium text-muted">{label}</div>
      {rows.map((r) => (
        <div key={r.name} className="flex items-center justify-between gap-4 py-0.5">
          <span className="flex items-center gap-2 text-ink-2">
            <span className="h-2 w-2 rounded-full" style={{ background: r.color }} />
            {r.name}
          </span>
          <span className="tabular font-semibold text-ink">{r.value}</span>
        </div>
      ))}
    </div>
  );
}

/** Market value against money put in, as two areas. */
export function ValueAreaChart({ series, height = 260 }: { series: Series; height?: number }) {
  return (
    <div style={{ height }} role="img" aria-label="Portfolio value versus net amount invested">
      <ResponsiveContainer>
        <AreaChart data={series} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="gValue" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--good)" stopOpacity={0.28} />
              <stop offset="100%" stopColor="var(--good)" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gInv" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--series-8)" stopOpacity={0.12} />
              <stop offset="100%" stopColor="var(--series-8)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={48} {...AXIS} />
          <YAxis tickFormatter={inrShort} width={58} {...AXIS} />
          <Tooltip
            cursor={{ stroke: "var(--accent)", strokeOpacity: 0.5, strokeDasharray: "3 3" }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TipBox
                  label={date(String(label))}
                  rows={[
                    { name: "Market value", value: inr(payload[0]?.payload.value), color: "var(--good)" },
                    { name: "Money put in (net)", value: inr(payload[0]?.payload.invested), color: "var(--series-8)" },
                    { name: "Profit so far", value: inr(payload[0]!.payload.value - payload[0]!.payload.invested), color: "transparent" },
                  ]}
                />
              ) : null
            }
          />
          <Area isAnimationActive={false} type="stepAfter" dataKey="invested" stroke="var(--series-8)" strokeWidth={1.5} strokeDasharray="4 3" fill="url(#gInv)" />
          <Area isAnimationActive={false} type="monotone" dataKey="value" stroke="var(--good)" strokeWidth={2} fill="url(#gValue)" activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--page)" }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Growth of ₹100, time-weighted, rebased to 100 at the start of the selected range. */
export function GrowthChart({ series, benchmarkName, height = 300 }: { series: Series; benchmarkName: string | null; height?: number }) {
  const p0 = series[0]?.portfolio_index ?? 100;
  const b0 = series.find((s) => s.benchmark_index != null)?.benchmark_index ?? null;
  const data = series.map((s) => ({
    date: s.date,
    portfolio: (s.portfolio_index / p0) * 100,
    benchmark: s.benchmark_index != null && b0 ? (s.benchmark_index / b0) * 100 : null,
  }));
  const hasBench = data.some((d) => d.benchmark != null);
  return (
    <div style={{ height }} role="img" aria-label="Growth of 100 rupees, portfolio versus benchmark">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={48} {...AXIS} />
          <YAxis domain={["auto", "auto"]} width={40} {...AXIS} />
          <Tooltip
            cursor={{ stroke: "var(--accent)", strokeOpacity: 0.5, strokeDasharray: "3 3" }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TipBox
                  label={date(String(label))}
                  rows={[
                    { name: "Portfolio", value: `₹${Number(payload[0]?.payload.portfolio).toFixed(1)}`, color: "var(--accent)" },
                    ...(payload[0]?.payload.benchmark != null
                      ? [{ name: benchmarkName ?? "Benchmark", value: `₹${Number(payload[0].payload.benchmark).toFixed(1)}`, color: "var(--series-3)" }]
                      : []),
                  ]}
                />
              ) : null
            }
          />
          <Line isAnimationActive={false} type="monotone" dataKey="portfolio" stroke="var(--accent)" strokeWidth={2.2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--page)" }} />
          {hasBench && (
            <Line isAnimationActive={false} type="monotone" dataKey="benchmark" stroke="var(--series-3)" strokeWidth={1.6} strokeDasharray="5 3" dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--page)" }} />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Donut with a centre label. */
export function Donut({ items, center, sub, size = 180 }: {
  items: { name: string; value: number; color: string }[];
  center: string;
  sub?: string;
  size?: number;
}) {
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label="Allocation donut chart">
      <ResponsiveContainer>
        <PieChart>
          <Pie
            data={items}
            dataKey="value"
            nameKey="name"
            innerRadius="72%"
            outerRadius="100%"
            paddingAngle={items.length > 1 ? 2 : 0}
            cornerRadius={4}
            stroke="none"
            isAnimationActive={false}
            startAngle={90}
            endAngle={-270}
          >
            {items.map((i) => (
              <Cell key={i.name} fill={i.color} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <div className="tabular text-lg font-semibold tracking-tight text-ink">{center}</div>
        {sub && <div className="text-[11px] text-muted">{sub}</div>}
      </div>
    </div>
  );
}

/** Legend rows for a donut or stacked bar. */
export function LegendList({ items }: { items: { name: string; weight: number; value?: number; color: string }[] }) {
  return (
    <ul className="w-full space-y-2.5">
      {items.map((i) => (
        <li key={i.name} className="flex items-center gap-3 text-[13px]">
          <span className="h-2.5 w-2.5 shrink-0 rounded-[3px]" style={{ background: i.color }} />
          <span className="min-w-0 flex-1 truncate text-ink-2" title={i.name}>{i.name}</span>
          {i.value != null && <span className="tabular hidden text-muted sm:inline">{inrShort(i.value)}</span>}
          <span className="tabular w-14 text-right font-semibold text-ink">{pct(i.weight)}</span>
        </li>
      ))}
    </ul>
  );
}

/** One horizontal bar split into segments (shares of a whole). */
export function StackBar({ items, className = "h-2.5" }: { items: { name: string; weight: number; color: string }[]; className?: string }) {
  return (
    <div className={`flex w-full gap-0.5 overflow-hidden rounded-full ${className}`}>
      {items.map((i) => (
        <div key={i.name} style={{ width: `${i.weight * 100}%`, background: i.color }} title={`${i.name} ${pct(i.weight)}`} />
      ))}
    </div>
  );
}

/** Horizontal bars in plain HTML: label, bar, value. */
export function BarList({ items, color = "var(--series-1)", highlightAbove }: {
  items: { name: string; weight: number; value?: number }[];
  color?: string;
  highlightAbove?: number;
}) {
  const max = Math.max(...items.map((i) => i.weight), 0.0001);
  return (
    <ul className="space-y-3">
      {items.map((i) => {
        const hot = highlightAbove != null && i.weight > highlightAbove;
        return (
          <li key={i.name} className="text-[13px]">
            <div className="mb-1 flex items-center justify-between gap-3">
              <span className="truncate text-ink-2" title={i.name}>{i.name}</span>
              <span className={`tabular font-semibold ${hot ? "text-bad" : "text-ink"}`}>{pct(i.weight)}</span>
            </div>
            <div className="h-2 rounded-full bg-surface-3" title={i.value != null ? inr(i.value) : undefined}>
              <div className="h-full rounded-full" style={{ width: `${(i.weight / max) * 100}%`, background: hot ? "var(--bad)" : color }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** Company exposure split into direct holdings and holdings through funds. */
export function CompaniesChart({ companies, total }: { companies: Report["allocation"]["top_companies"]; total: number }) {
  const data = companies.map((c) => ({
    name: c.name.replace(/ Ltd$/, ""),
    sector: c.sector,
    Direct: total ? c.direct_value / total : 0,
    "Via funds": total ? c.via_funds_value / total : 0,
    value: c.value,
  }));
  const max = Math.max(...data.map((d) => d.Direct + d["Via funds"]), 0.01);
  const step = max > 0.4 ? 0.1 : 0.05;
  const ticks = Array.from({ length: Math.ceil(max / step) + 1 }, (_, i) => i * step);
  return (
    <div>
      <div className="mb-3 flex gap-4 text-xs text-ink-2">
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[3px] bg-[var(--series-1)]" />Held directly</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[3px] bg-[var(--series-2)]" />Through funds</span>
      </div>
      <div style={{ height: 16 + data.length * 34 }} role="img" aria-label="Top company exposures">
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }} barCategoryGap={9}>
            <CartesianGrid stroke="var(--grid)" horizontal={false} />
            <XAxis type="number" ticks={ticks} domain={[0, ticks[ticks.length - 1]!]} tickFormatter={(v) => pct(v, 0)} {...AXIS} />
            <YAxis type="category" dataKey="name" width={176} {...AXIS} tick={{ fill: "var(--ink-2)", fontSize: 11.5 }} />
            <Tooltip
              cursor={{ fill: "var(--surface-2)" }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <TipBox
                    label={`${payload[0]!.payload.name}${payload[0]!.payload.sector ? " · " + payload[0]!.payload.sector : ""}`}
                    rows={[
                      { name: "Held directly", value: pct(payload[0]!.payload.Direct), color: "var(--series-1)" },
                      { name: "Through funds", value: pct(payload[0]!.payload["Via funds"]), color: "var(--series-2)" },
                      { name: "Total value", value: inr(payload[0]!.payload.value), color: "transparent" },
                    ]}
                  />
                ) : null
              }
            />
            <Bar isAnimationActive={false} dataKey="Direct" stackId="a" fill="var(--series-1)" />
            <Bar isAnimationActive={false} dataKey="Via funds" stackId="a" fill="var(--series-2)" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** Tiny sparkline for KPI cards. */
export function Sparkline({ values, color = "var(--series-1)", height = 36 }: { values: number[]; color?: string; height?: number }) {
  const data = values.map((v, i) => ({ i, v }));
  return (
    <div style={{ height }} aria-hidden>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
          <defs>
            <linearGradient id="gSpark" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.25} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Area isAnimationActive={false} type="monotone" dataKey="v" stroke={color} strokeWidth={1.8} fill="url(#gSpark)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
