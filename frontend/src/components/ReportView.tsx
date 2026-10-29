import {
  Activity,
  ArrowRight,
  ArrowUpDown,
  BadgeCheck,
  Building2,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Database,
  Gauge,
  Layers,
  Lightbulb,
  MessageSquareQuote,
  RefreshCw,
  Scale,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  ThumbsDown,
  ThumbsUp,
  TrendingDown,
  TrendingUp,
  Waves,
  type LucideIcon,
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { ASSET_COLORS, SERIES, date, inr, inrShort, num, pct, signedInr, signedPct, titleCase } from "../lib/format";
import { impactText, taxLine, usePlan } from "../lib/plan";
import type { ActionOption, Contribution, Finding, Holding, Report } from "../lib/types";
import { BarList, CompaniesChart, Donut, GrowthChart, LegendList, RANGES, StackBar, ValueAreaChart, sliceRange, type Range } from "./charts";
import { HoldingsHeatmap } from "./terminal";
import { Badge, Button, Card, EmptyState, Help, Meter, Notice, Segmented, SeverityBadge, Tabs, buttonCls, cx, inputCls, severityMeta } from "./ui";

export type ReportTab = "summary" | "plan" | "holdings" | "inside" | "performance" | "risk" | "discuss";

/** Plain-English meaning of every term the report uses. */
export const GLOSSARY = {
  xirr: "The yearly return this client actually earned, taking into account when each rupee went in and came out. The best single answer to “how did my money do?”.",
  twr: "How the chosen investments performed, ignoring when money was added or taken out. This is the fair way to compare with an index.",
  profit: "Today's value plus everything already taken out (sales, dividends paid), minus everything put in.",
  vsIndex: "We replay this holding's own purchases and sales into the index on the same dates. Positive means the holding did better than the index would have.",
  volatility: "How much the value usually swings in a year. Higher means a bumpier ride.",
  drawdown: "The biggest fall from a high point to a later low point in this period.",
  beta: "1.0 means it moves like the market. 0.7 means it moves about 70% as much.",
  var: "On roughly 1 day in 20, the one-day loss was bigger than this amount. It is not the worst possible loss.",
  overlap: "How much two funds own the same stocks. 81% means they are mostly the same portfolio.",
  lookthrough: "We look inside each mutual fund to see the stocks it owns, and add them to stocks held directly.",
  riskProfile: "From the client's answers to six questions. Each profile has a suggested range for the share of the portfolio in equity (hybrid funds count as half).",
  funded: "How much of the goal the plan is expected to cover by the date: money set aside today plus the monthly SIP, grown at the expected return, against the target grown with inflation.",
  effective: "If a few holdings dominate, ten holdings can behave like four. This counts how many equal-sized holdings the portfolio behaves like.",
};

export function ReportView({ report, storageKey, onRefresh, shareHref, onEditPlan }: {
  report: Report;
  storageKey: string;
  onRefresh?: () => Promise<void>;
  shareHref?: string;
  onEditPlan?: () => void;
}) {
  const [tab, setTab] = useState<ReportTab>("summary");
  const plan = usePlan(storageKey);
  if (report.status !== "ok") {
    return <Notice level={report.status === "error" ? "error" : "info"}>{report.message}</Notice>;
  }
  const high = report.findings.filter((f) => f.severity === "high").length;
  const outdated = !report.summary || !report.contribution || !report.planning;
  const goalsShort = (report.planning?.goals ?? []).filter((g) => g.status === "off_track").length;
  return (
    <div className="space-y-6">
      {outdated && (
        <Notice
          level="info"
          title="This report was made with an older version"
          action={onRefresh && <RefreshButton onRefresh={onRefresh} />}
        >
          Update it once to see the plain-English summary, goals and risk profile checks, what helped and hurt, and options with tax estimates.
        </Notice>
      )}
      <Snapshot r={report} />
      <Tabs<ReportTab>
        value={tab}
        onChange={setTab}
        className="no-print"
        tabs={[
          { id: "summary", label: "Summary", icon: Lightbulb },
          { id: "plan", label: "Goals & risk", icon: Target, dot: goalsShort > 0 || report.planning?.in_range === false },
          { id: "discuss", label: "To discuss", icon: MessageSquareQuote, count: report.findings.length, dot: high > 0 },
          { id: "holdings", label: "Holdings", icon: Layers, count: report.holdings.length },
          { id: "inside", label: "What's inside", icon: Building2 },
          { id: "performance", label: "Performance", icon: TrendingUp },
          { id: "risk", label: "Risk", icon: ShieldCheck },
        ]}
      />
      <div key={tab} className="fade-in">
        {tab === "summary" && <SummaryTab r={report} goTo={setTab} shareHref={shareHref} planCount={plan.selected.length} />}
        {tab === "plan" && <PlanTab r={report} onEditPlan={onEditPlan} />}
        {tab === "discuss" && <Discuss r={report} selected={plan.selected} toggle={plan.toggle} shareHref={shareHref} />}
        {tab === "holdings" && <Holdings r={report} />}
        {tab === "inside" && <Inside r={report} />}
        {tab === "performance" && <Performance r={report} />}
        {tab === "risk" && <Risk r={report} />}
      </div>
    </div>
  );
}

function RefreshButton({ onRefresh }: { onRefresh: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  return (
    <Button size="sm" icon={RefreshCw} loading={busy} onClick={async () => { setBusy(true); try { await onRefresh(); } finally { setBusy(false); } }}>
      Update report
    </Button>
  );
}

/* ------------------------------------------------------------ Snapshot */

function Snapshot({ r }: { r: Report }) {
  const o = r.overview, p = r.performance;
  const profit = o.current_value - o.net_invested;
  const profitPct = o.net_invested > 0 ? profit / o.net_invested : null;
  const gap = p.benchmark_compatible && p.twr_annualized != null && p.benchmark_annualized != null ? p.twr_annualized - p.benchmark_annualized : null;
  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Kpi label="Value today" value={inr(o.current_value)} sub={`On ${date(r.meta.valuation_date)} · ${o.holdings_count} holdings`} />
      <Kpi
        label="Total profit"
        help={GLOSSARY.profit}
        value={signedInr(profit)}
        tone={profit >= 0 ? "good" : "bad"}
        sub={`${profitPct != null ? signedPct(profitPct) + " on " : "on "}${inr(o.net_invested)} put in`}
      />
      <Kpi label="Annual return (XIRR)" help={GLOSSARY.xirr} value={pct(o.xirr)} tone={(o.xirr ?? 0) >= 0 ? "good" : "bad"} sub={o.first_investment ? `Since ${date(o.first_investment)}` : undefined} />
      <Kpi
        label="Compared with the index"
        help={GLOSSARY.twr}
        value={gap == null ? "–" : `${gap >= 0 ? "+" : "−"}${Math.abs(gap * 100).toFixed(1)} pts`}
        tone={gap == null ? undefined : gap >= 0 ? "good" : "bad"}
        sub={gap == null ? (p.benchmark_name ? "Index not comparable for this mix" : "No index data") : `${pct(p.twr_annualized)} a year vs ${pct(p.benchmark_annualized)} for ${p.benchmark_name}`}
      />
    </section>
  );
}

export function Kpi({ label, value, sub, tone, icon: Icon, help, children }: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "good" | "bad";
  icon?: LucideIcon;
  help?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-card">
      <div className="flex items-center justify-between gap-2">
        <span className="label flex items-center gap-1.5">{label}{help && <Help>{help}</Help>}</span>
        {Icon && <Icon size={16} className="text-faint" />}
      </div>
      <div className={cx("tabular mt-1.5 text-[24px] font-semibold tracking-tight", tone === "good" ? "text-good" : tone === "bad" ? "text-bad" : "text-ink")}>
        {value}
      </div>
      {sub && <div className="mt-0.5 text-[12.5px] leading-snug text-muted">{sub}</div>}
      {children}
    </div>
  );
}

/* ------------------------------------------------------------- Summary */

const POINT_ICON: Record<string, { icon: LucideIcon; cls: string }> = {
  headline: { icon: Lightbulb, cls: "bg-accent-soft text-accent" },
  good: { icon: ThumbsUp, cls: "bg-good-soft text-good" },
  bad: { icon: ThumbsDown, cls: "bg-bad-soft text-bad" },
  warn: { icon: MessageSquareQuote, cls: "bg-warn-soft text-warn" },
};

function SummaryTab({ r, goTo, shareHref, planCount }: { r: Report; goTo: (t: ReportTab) => void; shareHref?: string; planCount: number }) {
  const p = r.performance;
  const [range, setRange] = useState<Range>("ALL");
  const series = useMemo(() => sliceRange(p.series, range), [p.series, range]);
  const flags = r.findings;
  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card
          title="In short"
          subtitle="The whole portfolio in a few sentences"
          action={r.summary && (r.summary.source === "llm"
            ? <Badge tone="info" icon={Sparkles}>Written by AI · numbers checked</Badge>
            : <Badge tone="neutral">Written from the numbers</Badge>)}
        >
          {r.summary ? (
            <ul className="space-y-3">
              {(r.summary.source === "llm" ? [{ kind: "headline" as const, text: r.summary.text }] : r.summary.points).map((pt, i) => {
                const m = POINT_ICON[pt.kind] ?? POINT_ICON.headline!;
                return (
                  <li key={i} className="flex gap-3">
                    <span className={cx("grid h-7 w-7 shrink-0 place-items-center rounded-lg", m.cls)}><m.icon size={15} /></span>
                    <p className={cx("pt-0.5 leading-relaxed", pt.kind === "headline" ? "text-[15px] font-medium text-ink" : "text-[14px] text-ink-2")}>{pt.text}</p>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-sm text-muted">Update the report to see the summary.</p>
          )}
        </Card>

        <Card title="Next step" subtitle="Turn this review into something the client can read">
          <ol className="space-y-3 text-[13.5px] text-ink-2">
            <li className="flex gap-3"><Num n={1} />
              <span>Open <button className="font-medium text-accent hover:underline" onClick={() => goTo("discuss")}>To discuss</button> and tick the options you want to suggest.{planCount > 0 && <span className="text-good"> {planCount} ticked.</span>}</span>
            </li>
            <li className="flex gap-3"><Num n={2} /><span>Open the client report: a simple 2–3 page summary you can print or save as PDF.</span></li>
            <li className="flex gap-3"><Num n={3} /><span>Copy the ready-made email and send it with the report.</span></li>
          </ol>
          {shareHref && (
            <Link to={shareHref} className={buttonCls("primary", "md", "mt-5 w-full")}>
              <Send size={16} /> Open client report
            </Link>
          )}
        </Card>
      </div>

      {r.contribution && <HelpedHurt r={r} />}

      <Card title="Things to discuss" subtitle={flags.length ? `${flags.length} points crossed a review limit. Each has options with numbers.` : undefined}
        action={flags.length > 0 && <button onClick={() => goTo("discuss")} className="no-print inline-flex items-center gap-1 text-[13px] font-medium text-accent hover:underline">See options <ArrowRight size={14} /></button>}>
        {flags.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-good"><ShieldCheck size={18} /> Nothing crossed a review limit.</div>
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {flags.map((f) => (
              <li key={f.id}>
                <button onClick={() => goTo("discuss")} className="flex w-full items-start gap-3 py-3 text-left hover:bg-surface-2/60 sm:items-center">
                  <SeverityBadge severity={f.severity} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[14px] font-medium text-ink">{f.title}</span>
                    {f.options?.[0] && <span className="mt-0.5 block text-[12.5px] text-muted">Option: {f.options[0].title}</span>}
                  </span>
                  <span className="tabular shrink-0 text-[14px] font-semibold text-ink-2">{f.unit === "percent" ? pct(f.measured_value) : f.measured_value}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Value and money put in" subtitle="The gap between the two lines is the profit" action={<Segmented options={RANGES} value={range} onChange={setRange} />}>
        {p.series.length > 1 ? (
          <>
            <ValueAreaChart series={series} height={260} />
            <div className="mt-2 flex flex-wrap gap-4 text-[12.5px] text-ink-2">
              <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-good" />Value</span>
              <span className="flex items-center gap-1.5"><span className="h-0 w-4 border-t-2 border-dashed border-[var(--series-8)]" />Money put in (net)</span>
            </div>
          </>
        ) : (
          <Notice>Not enough price history to chart value over time.</Notice>
        )}
      </Card>

      <DataQuality r={r} />
    </div>
  );
}

function Num({ n }: { n: number }) {
  return <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent-soft text-[12px] font-bold text-accent">{n}</span>;
}

function HelpedHurt({ r }: { r: Report }) {
  const c = r.contribution!;
  const byId = Object.fromEntries(c.items.map((i) => [i.instrument_id, i]));
  const helped = c.helped.map((id) => byId[id]).filter(Boolean) as Contribution[];
  const hurt = c.hurt.map((id) => byId[id]).filter(Boolean) as Contribution[];
  const maxProfit = Math.max(...c.items.map((i) => Math.abs(i.profit)), 1);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card title="What helped" subtitle="Holdings that made the most profit" icon={ThumbsUp}>
        {helped.length ? (
          <ul className="space-y-4">
            {helped.map((i) => (
              <li key={i.instrument_id}>
                <div className="flex items-baseline justify-between gap-3 text-[14px]">
                  <span className="min-w-0 truncate font-medium text-ink" title={i.name}>{i.name}</span>
                  <span className="tabular shrink-0 font-semibold text-good">{signedInr(i.profit)}</span>
                </div>
                <Meter className="mt-1.5 h-2" value={i.profit} max={maxProfit} color="var(--good)" />
                <div className="mt-1 flex flex-wrap gap-x-3 text-[12.5px] text-muted">
                  {i.share_of_profit != null && <span>{pct(i.share_of_profit)} of all profit</span>}
                  {i.xirr != null && <span>{pct(i.xirr)} a year</span>}
                  {i.vs_index != null && <span className={i.vs_index >= 0 ? "text-good" : "text-bad"}>{i.vs_index >= 0 ? "beat" : "trailed"} the index by {Math.abs(i.vs_index * 100).toFixed(1)} pts</span>}
                </div>
              </li>
            ))}
          </ul>
        ) : <p className="text-sm text-muted">No holding has made a profit yet.</p>}
      </Card>
      <Card title="What held it back" subtitle={<>Losses, or holdings that did worse than the index with the same money <Help>{GLOSSARY.vsIndex}</Help></>} icon={ThumbsDown}>
        {hurt.length ? (
          <ul className="space-y-4">
            {hurt.map((i) => (
              <li key={i.instrument_id}>
                <div className="flex items-baseline justify-between gap-3 text-[14px]">
                  <span className="min-w-0 truncate font-medium text-ink" title={i.name}>{i.name}</span>
                  <span className={cx("tabular shrink-0 font-semibold", i.vs_index != null && i.profit >= 0 ? "text-bad" : i.profit < 0 ? "text-bad" : "text-ink")}>
                    {i.profit < 0 ? signedInr(i.profit) : i.vs_index != null ? `−${Math.abs(i.vs_index * 100).toFixed(1)} pts a year` : signedInr(i.profit)}
                  </span>
                </div>
                <div className="mt-1 text-[12.5px] text-muted">
                  {i.profit < 0
                    ? `Lost ${inr(-i.profit)} on ${inr(i.money_in)} put in.`
                    : `Earned ${pct(i.xirr)} a year; the index would have earned ${pct(i.index_xirr)} with the same money and dates.`}
                </div>
              </li>
            ))}
          </ul>
        ) : <p className="text-sm text-muted">Every equity holding kept up with the index. Nothing lost money.</p>}
        <p className="mt-4 border-t border-line pt-3 text-[12px] text-muted">{c.method}</p>
      </Card>
    </div>
  );
}

function DataQuality({ r }: { r: Report }) {
  if (!r.data_quality.length) return null;
  return (
    <Card title="What the numbers can and cannot see" subtitle="Data coverage and limitations" icon={Database}>
      <div className="space-y-2">
        {r.data_quality.map((q, i) => (
          <Notice key={i} level={q.level}>{q.message}</Notice>
        ))}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------- Goals & risk */

const GOAL_STATUS: Record<string, { label: string; tone: "good" | "warn" | "bad" | "neutral"; color: string }> = {
  on_track: { label: "On track", tone: "good", color: "var(--good)" },
  at_risk: { label: "Slightly short", tone: "warn", color: "var(--warn)" },
  off_track: { label: "Not on track", tone: "bad", color: "var(--bad)" },
  due: { label: "Due now", tone: "neutral", color: "var(--series-8)" },
};

function PlanTab({ r, onEditPlan }: { r: Report; onEditPlan?: () => void }) {
  const pl = r.planning;
  if (!pl?.available)
    return (
      <EmptyState
        icon={Target}
        title="Add the client's risk profile and goals"
        action={onEditPlan && <Button icon={Target} onClick={onEditPlan}>Add profile and goals</Button>}
      >
        Six quick questions and the client's goals let FolioLens check whether the portfolio's risk fits the client, whether each goal
        is on track, and what to change if not.
      </EmptyState>
    );
  const prof = pl.profile;
  const eq = pl.equity_share;
  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <Card title="Risk profile" subtitle={<>From the client's answers <Help>{GLOSSARY.riskProfile}</Help></>} icon={ShieldCheck}
          action={onEditPlan && <button onClick={onEditPlan} className="no-print text-[13px] font-medium text-accent hover:underline">Edit</button>}>
          {prof ? (
            <>
              <div className="flex items-baseline justify-between gap-3">
                <div className="text-[22px] font-semibold tracking-tight text-ink">{prof.category}</div>
                <div className="tabular text-[13px] text-muted">score {prof.score.toFixed(0)}/100</div>
              </div>
              <Meter className="mt-2 h-2" value={prof.score} max={100} color="var(--accent)" />
              <div className="mt-1 flex justify-between text-[11px] text-muted"><span>Conservative</span><span>Aggressive</span></div>
              {prof.answered < prof.questions && <p className="mt-2 text-xs text-warn">{prof.answered} of {prof.questions} questions answered.</p>}
            </>
          ) : (
            <p className="text-[13.5px] text-muted">No questionnaire yet. {onEditPlan && <button className="font-medium text-accent hover:underline" onClick={onEditPlan}>Answer it</button>}</p>
          )}
        </Card>
        <Card title="Does the portfolio's risk fit?" subtitle="Share of the portfolio in equity against the suggested range">
          {prof ? (
            <>
              <EquityRange eq={eq} lo={prof.equity_min} hi={prof.equity_max} />
              <p className={cx("mt-4 text-[14px]", pl.in_range ? "text-good" : "text-bad")}>
                {pl.in_range
                  ? `Fits: ${pct(eq)} in equity is inside the ${pct(prof.equity_min, 0)}–${pct(prof.equity_max, 0)} range.`
                  : `${pct(eq)} in equity is ${eq > prof.equity_max ? "above" : "below"} the ${pct(prof.equity_min, 0)}–${pct(prof.equity_max, 0)} range. See the options under To discuss.`}
              </p>
            </>
          ) : <p className="text-[13.5px] text-muted">Needs the risk profile.</p>}
        </Card>
      </div>

      <Card title="Goals" subtitle={pl.goals.length ? `${pl.goals_on_track} of ${pl.goals.length} on track` : "No goals added yet"} icon={Target}
        action={onEditPlan && <button onClick={onEditPlan} className="no-print text-[13px] font-medium text-accent hover:underline">Edit goals</button>}>
        {pl.goals.length === 0 ? (
          <p className="text-[13.5px] text-muted">Add goals to see whether the portfolio and SIPs can reach them.</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {pl.goals.map((g) => {
              const st = GOAL_STATUS[g.status] ?? GOAL_STATUS.due!;
              return (
                <div key={g.id} className="rounded-xl border border-line p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-[15px] font-semibold text-ink">{g.name}</div>
                      <div className="text-[12.5px] text-muted">by {date(g.target_date)} · {g.years.toFixed(1)} years</div>
                    </div>
                    <Badge tone={st.tone}>{st.label}</Badge>
                  </div>
                  <div className="mt-4 flex items-baseline justify-between text-[13px]">
                    <span className="flex items-center gap-1 text-muted">Funded <Help>{GLOSSARY.funded}</Help></span>
                    <span className="tabular font-semibold" style={{ color: st.color }}>{g.funded_ratio == null ? "–" : pct(g.funded_ratio, 0)}</span>
                  </div>
                  <Meter className="mt-1.5 h-2" value={Math.min(g.funded_ratio ?? 0, 1)} max={1} color={st.color} />
                  <dl className="tabular mt-4 grid grid-cols-2 gap-x-3 gap-y-2 text-[12.5px]">
                    <div><dt className="text-muted">Target today</dt><dd className="font-medium text-ink">{inr(g.target_today)}</dd></div>
                    <div><dt className="text-muted">Target then</dt><dd className="font-medium text-ink">{inr(g.target_future)}</dd></div>
                    <div><dt className="text-muted">Projected</dt><dd className="font-medium text-ink">{inr(g.projected)}</dd></div>
                    <div><dt className="text-muted">Set aside today</dt><dd className="font-medium text-ink">{inr(g.set_aside)}</dd></div>
                    <div><dt className="text-muted">SIP now</dt><dd className="font-medium text-ink">{inr(g.monthly_sip)}</dd></div>
                    <div><dt className="text-muted">SIP needed</dt><dd className={cx("font-medium", (g.required_sip ?? 0) > g.monthly_sip ? "text-bad" : "text-good")}>{g.required_sip == null ? "–" : inr(g.required_sip)}</dd></div>
                  </dl>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card title="Planning assumptions" subtitle="Used for goal projections only. They are assumptions, not forecasts." icon={BadgeCheck}>
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-ink-2">
          {Object.entries(pl.assumptions.expected_return).map(([k, v]) => (
            <span key={k}>{titleCase(k)} <strong className="tabular text-ink">{pct(v)}</strong> a year</span>
          ))}
          <span>Inflation <strong className="tabular text-ink">{pct(pl.assumptions.inflation)}</strong></span>
          <span>This portfolio's mix <strong className="tabular text-ink">{pct(pl.assumptions.portfolio_expected_return)}</strong> a year</span>
        </div>
        <p className="mt-3 text-[12px] text-muted">{pl.assumptions.note}</p>
      </Card>
    </div>
  );
}

function EquityRange({ eq, lo, hi }: { eq: number; lo: number; hi: number }) {
  const inRange = eq >= lo && eq <= hi;
  return (
    <div className="pt-6">
      <div className="relative h-3 rounded-full bg-surface-3">
        <div className="absolute inset-y-0 rounded-full bg-good-soft ring-1 ring-good/30" style={{ left: `${lo * 100}%`, width: `${(hi - lo) * 100}%` }} />
        <div className="absolute -top-1.5 -bottom-1.5 w-[3px] -translate-x-1/2 rounded bg-ink ring-2 ring-surface" style={{ left: `${Math.min(eq, 1) * 100}%` }} />
        <span className={cx("absolute -top-6 -translate-x-1/2 whitespace-nowrap text-[12px] font-semibold", inRange ? "text-good" : "text-bad")} style={{ left: `${Math.min(eq, 1) * 100}%` }}>
          {pct(eq)} now
        </span>
      </div>
      <div className="relative mt-1.5 h-4 text-[11px] text-muted">
        <span className="absolute left-0">0%</span>
        <span className="absolute -translate-x-1/2 text-good" style={{ left: `${lo * 100}%` }}>{pct(lo, 0)}</span>
        <span className="absolute -translate-x-1/2 text-good" style={{ left: `${hi * 100}%` }}>{pct(hi, 0)}</span>
        <span className="absolute right-0">100%</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------- To discuss */

function Discuss({ r, selected, toggle, shareHref }: { r: Report; selected: string[]; toggle: (id: string) => void; shareHref?: string }) {
  const [sev, setSev] = useState("all");
  if (!r.findings.length)
    return (
      <div className="flex flex-col items-center rounded-2xl border border-line bg-surface py-14 text-center shadow-card">
        <ShieldCheck size={32} className="text-good" />
        <div className="mt-3 font-semibold text-ink">Nothing crossed a review limit</div>
        <p className="mt-1 text-sm text-muted">Every rule is within its limit.</p>
      </div>
    );
  const list = r.findings.filter((f) => sev === "all" || f.severity === sev);
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented
          options={[{ id: "all", label: `All ${r.findings.length}` }, ...(["high", "medium", "low"] as const).filter((s) => r.findings.some((f) => f.severity === s)).map((s) => ({ id: s, label: s === "high" ? "Important" : titleCase(s) }))]}
          value={sev}
          onChange={setSev}
        />
        {shareHref && (
          <Link to={shareHref} className={buttonCls(selected.length ? "primary" : "secondary", "sm")}>
            <Send size={14} /> Client report{selected.length ? ` · ${selected.length} option${selected.length === 1 ? "" : "s"}` : ""}
          </Link>
        )}
      </div>
      <Notice level="info">
        Options are for <strong>you</strong> to weigh with the client. FolioLens calculates the numbers; it does not recommend buying or selling.
        Tick <strong>Add to client report</strong> on the ones you want to suggest.
      </Notice>
      {list.map((f) => (
        <FindingCard key={f.id} f={f} selected={selected} toggle={toggle} />
      ))}
    </div>
  );
}

function FindingCard({ f, selected, toggle }: { f: Finding; selected: string[]; toggle: (id: string) => void }) {
  const meta = severityMeta(f.severity);
  const Icon = meta.icon;
  const fmt = (x: number | null) => (x == null ? "–" : f.unit === "percent" ? pct(x) : String(x));
  const color = f.severity === "high" ? "var(--bad)" : f.severity === "medium" ? "var(--warn)" : "var(--series-8)";
  const showMeter = f.unit === "percent" && f.threshold != null;
  const scale = showMeter ? Math.max(f.measured_value, f.threshold!) * 1.25 : 1;
  return (
    <article className="avoid-break overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
      <div className="p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl" style={{ background: `color-mix(in srgb, ${color} 12%, transparent)`, color }}>
              <Icon size={19} />
            </span>
            <div className="min-w-0">
              <h3 className="text-[16px] font-semibold tracking-tight text-ink">{f.title}</h3>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <SeverityBadge severity={f.severity} />
                {f.explanation_source === "llm" ? <Badge tone="info" icon={Sparkles}>Explained by AI · numbers checked</Badge> : null}
                {f.data_date && <span className="text-xs text-muted">Data as of {date(f.data_date)}</span>}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="tabular text-[26px] font-semibold tracking-tight" style={{ color: f.severity === "low" ? "var(--ink)" : color }}>{fmt(f.measured_value)}</div>
            {f.threshold != null && <div className="text-xs text-muted">review limit {fmt(f.threshold)}</div>}
          </div>
        </div>

        <p className="mt-4 text-[14.5px] leading-relaxed text-ink-2">{f.explanation}</p>

        {showMeter && (
          <div className="mt-5">
            <div className="relative">
              <Meter className="h-2.5" value={f.measured_value} max={scale} marker={f.threshold!} color={color} />
              <span className="absolute -top-6 -translate-x-1/2 whitespace-nowrap text-[11px] font-medium text-ink-2" style={{ left: `${(f.threshold! / scale) * 100}%` }}>
                limit {fmt(f.threshold)}
              </span>
            </div>
            <div className="mt-1.5 flex justify-between text-[11px] text-muted"><span>0%</span><span>{pct(scale, 0)}</span></div>
          </div>
        )}

        {f.instruments.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-1.5">
            {f.instruments.map((i) => (
              <span key={i} className="rounded-md border border-line bg-surface-2 px-2 py-0.5 text-xs text-ink-2">{i}</span>
            ))}
          </div>
        )}
        {f.discussion_prompts.length > 0 && (
          <p className="mt-4 flex gap-2 text-[13.5px] text-ink-2">
            <MessageSquareQuote size={16} className="mt-0.5 shrink-0 text-accent" />
            <span><span className="font-medium text-ink">Ask the client: </span>{f.discussion_prompts.join(" ")}</span>
          </p>
        )}
      </div>

      {f.options && f.options.length > 0 && (
        <div className="border-t border-line bg-surface-2/60 p-5 sm:p-6">
          <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-ink"><Lightbulb size={15} className="text-accent" />Options to discuss</div>
          <div className="grid gap-3 lg:grid-cols-2">
            {f.options.map((o) => (
              <OptionCard key={o.id} o={o} checked={selected.includes(o.id)} onToggle={() => toggle(o.id)} />
            ))}
          </div>
        </div>
      )}
      {f.limitations.length > 0 && <p className="border-t border-line px-5 py-3 text-xs text-muted sm:px-6"><span className="font-medium">Limitations:</span> {f.limitations.join(" ")}</p>}
    </article>
  );
}

export function OptionCard({ o, checked, onToggle }: { o: ActionOption; checked: boolean; onToggle?: () => void }) {
  return (
    <div className={cx("flex flex-col rounded-xl border bg-surface p-4 transition", checked ? "border-accent ring-2 ring-accent/15" : "border-line")}>
      <div className="text-[14px] font-semibold text-ink">{o.title}</div>
      <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{o.summary}</p>
      <dl className="mt-3 grid grid-cols-1 gap-x-4 gap-y-1.5 text-[12.5px] sm:grid-cols-2">
        {o.impact.map((i) => (
          <div key={i.label} className="min-w-0">
            <dt className="truncate text-muted" title={i.label}>{i.label}</dt>
            <dd className={cx("tabular font-semibold", i.unit === "percent_points" && typeof i.value === "number" && i.value < 0 ? "text-bad" : "text-ink")}>{impactText(i)}</dd>
          </div>
        ))}
      </dl>
      {o.tax && (
        <div className="mt-3 rounded-lg bg-warn-soft px-3 py-2 text-[12.5px] text-ink-2">
          <span className="font-medium text-ink">Tax estimate: </span>{taxLine(o.tax)}
          <Help label="How is this tax estimated?">
            {o.tax.notes.join(" ")} Short-term gain {inr(o.tax.short_term_gain)}, long-term gain {inr(o.tax.long_term_gain)}. Rules: {o.tax.rules}.
          </Help>
        </div>
      )}
      {o.tradeoffs.length > 0 && (
        <ul className="mt-3 space-y-1 text-[12.5px] text-muted">
          {o.tradeoffs.map((t) => <li key={t}>• {t}</li>)}
        </ul>
      )}
      {onToggle && (
        <label className="no-print mt-4 flex cursor-pointer items-center gap-2 border-t border-line pt-3 text-[13px] font-medium text-ink">
          <input type="checkbox" checked={checked} onChange={onToggle} className="h-4 w-4 cursor-pointer accent-[var(--accent)]" />
          Add to client report
          {checked && <CheckCircle2 size={15} className="ml-auto text-accent" />}
        </label>
      )}
    </div>
  );
}

/* ------------------------------------------------------------ Holdings */

type SortKey = "name" | "value" | "weight" | "cost" | "gain" | "xirr";

function Holdings({ r }: { r: Report }) {
  const [q, setQ] = useState("");
  const [cls, setCls] = useState("all");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "value", dir: -1 });
  const classes = ["all", ...Array.from(new Set(r.holdings.map((h) => h.asset_class)))];

  const rows = useMemo(() => {
    const ql = q.toLowerCase();
    return r.holdings
      .filter((h) => (cls === "all" || h.asset_class === cls) && (!ql || h.name.toLowerCase().includes(ql) || (h.category ?? "").toLowerCase().includes(ql)))
      .sort((a, b) => {
        const av = sort.key === "name" ? a.name : (a[sort.key] ?? -Infinity);
        const bv = sort.key === "name" ? b.name : (b[sort.key] ?? -Infinity);
        return (av < bv ? -1 : av > bv ? 1 : 0) * sort.dir;
      });
  }, [r.holdings, q, cls, sort]);

  const tot = rows.reduce((s, h) => ({ value: s.value + h.value, cost: s.cost + h.cost, gain: s.gain + h.gain, weight: s.weight + h.weight }), { value: 0, cost: 0, gain: 0, weight: 0 });
  const maxW = Math.max(...r.holdings.map((h) => h.weight), 0.01);

  const Th = ({ k, children, right }: { k: SortKey; children: ReactNode; right?: boolean }) => (
    <th className={cx("whitespace-nowrap px-4 py-3 font-medium", right && "text-right")}>
      <button
        className={cx("inline-flex items-center gap-1 hover:text-ink", sort.key === k && "text-ink")}
        onClick={() => setSort((s) => ({ key: k, dir: s.key === k ? ((-s.dir) as 1 | -1) : k === "name" ? 1 : -1 }))}
      >
        {children}
        {sort.key === k ? <ChevronDown size={13} className={sort.dir === 1 ? "rotate-180" : undefined} /> : <ArrowUpDown size={12} className="opacity-40" />}
      </button>
    </th>
  );

  return (
    <div className="space-y-6">
      <Card title="Where the money is" subtitle="Each box is one holding. Bigger box = more money; greener = bigger gain on what was paid.">
        <HoldingsHeatmap holdings={r.holdings} height={280} />
      </Card>
      <section className="overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4">
          <div className="relative w-full sm:w-72">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
            <input className={cx(inputCls, "h-9 pl-9")} placeholder="Search holdings" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <Segmented options={classes.map((c) => ({ id: c, label: c === "all" ? "All" : titleCase(c) }))} value={cls} onChange={setCls} />
        </div>
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full min-w-[880px] text-[13.5px]">
            <thead className="bg-surface-2 text-left text-[12.5px] text-muted">
              <tr>
                <Th k="name">Holding</Th>
                <Th k="value" right>Value</Th>
                <Th k="weight">Share</Th>
                <Th k="cost" right>Paid</Th>
                <Th k="gain" right>Gain</Th>
                <Th k="xirr" right>Annual return</Th>
              </tr>
            </thead>
            <tbody className="tabular divide-y divide-[var(--border)]">
              {rows.map((h) => <HoldingRow key={h.instrument_id} h={h} maxW={maxW} />)}
              {rows.length === 0 && <tr><td colSpan={6} className="px-4 py-10 text-center text-muted">No holdings match.</td></tr>}
            </tbody>
            {rows.length > 0 && (
              <tfoot className="tabular border-t border-line-strong bg-surface-2 font-semibold text-ink">
                <tr>
                  <td className="px-4 py-3">Total · {rows.length} holdings</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">{inr(tot.value)}</td>
                  <td className="px-4 py-3">{pct(tot.weight)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">{inr(tot.cost)}</td>
                  <td className={cx("whitespace-nowrap px-4 py-3 text-right", tot.gain >= 0 ? "text-good" : "text-bad")}>{signedInr(tot.gain)}</td>
                  <td className="px-4 py-3 text-right text-muted">{cls === "all" && !q ? pct(r.overview.xirr) : "–"}</td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
        <p className="border-t border-line px-4 py-3 text-xs text-muted">
          Rebuilt from every transaction. “Paid” is the average cost of the units still held. Prices are the latest on or before {date(r.meta.valuation_date)}.
        </p>
      </section>
    </div>
  );
}

function HoldingRow({ h, maxW }: { h: Holding; maxW: number }) {
  const color = ASSET_COLORS[h.asset_class] ?? "var(--series-8)";
  const gainPct = h.cost ? h.gain / h.cost : null;
  return (
    <tr className="hover:bg-surface-2/50">
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg" style={{ background: `color-mix(in srgb, ${color} 14%, transparent)`, color }}>
            {h.type === "stock" ? <Building2 size={15} /> : <Layers size={15} />}
          </span>
          <div className="min-w-0">
            <div className="truncate font-medium text-ink">{h.name}</div>
            <div className="text-xs text-muted">{h.category ?? titleCase(h.type)} · {num(h.units, 3)} units @ {num(h.price, 2)}</div>
          </div>
        </div>
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-right font-medium text-ink">{inr(h.value)}</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="w-20"><Meter value={h.weight} max={maxW} color={color} /></div>
          <span className="w-11 text-xs text-ink-2">{pct(h.weight)}</span>
        </div>
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-right text-ink-2">{inr(h.cost)}</td>
      <td className="whitespace-nowrap px-4 py-3 text-right">
        <div className={cx("font-medium", h.gain >= 0 ? "text-good" : "text-bad")}>{signedInr(h.gain)}</div>
        <div className="text-xs text-muted">{signedPct(gainPct)}</div>
      </td>
      <td className={cx("whitespace-nowrap px-4 py-3 text-right font-medium", h.xirr != null && h.xirr < 0 ? "text-bad" : "text-ink")}>{pct(h.xirr)}</td>
    </tr>
  );
}

/* ------------------------------------------------------- What's inside */

function sectorThreshold(r: Report) {
  const f = r.findings.find((x) => x.type.includes("sector"));
  return f?.threshold ?? undefined;
}

function Inside({ r }: { r: Report }) {
  const a = r.allocation;
  const lt = a.lookthrough;
  const assets = a.asset_class.map((x, i) => ({ name: titleCase(x.name), weight: x.weight, value: x.value, color: ASSET_COLORS[x.name] ?? SERIES[i]! }));
  const caps = a.market_cap.map((m, i) => ({ name: `${titleCase(m.name)} companies`, weight: m.weight, value: m.value, color: SERIES[i]! }));
  const sectors = a.sector.items.map((s) => ({ name: s.name, weight: s.weight_of_equity, value: s.value }));
  return (
    <div className="space-y-6">
      {!lt.reliable && (
        <Notice level="warning" title="We can only see part of what the funds own">
          Look-through covers {pct(lt.coverage, 0)} of equity fund value (we need 80%), so the sector and company views are incomplete.
        </Notice>
      )}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Asset classes" subtitle="How the money is split today">
          <div className="flex flex-col items-center gap-6 sm:flex-row">
            <Donut items={assets} center={inrShort(r.overview.current_value)} sub="total value" size={170} />
            <LegendList items={assets} />
          </div>
        </Card>
        <Card title="Company size" subtitle={<>Share of the stocks we can see, including inside funds <Help>{GLOSSARY.lookthrough}</Help></>}>
          {caps.length ? (
            <div className="space-y-5">
              <StackBar items={caps} className="h-3" />
              <LegendList items={caps} />
            </div>
          ) : (
            <p className="text-sm text-muted">No stock exposure identified.</p>
          )}
          <div className="mt-6 border-t border-line pt-4">
            <div className="flex items-center justify-between text-[13px]">
              <span className="font-medium text-ink">How much of the funds we can see</span>
              <span className={cx("tabular font-semibold", lt.reliable ? "text-good" : "text-warn")}>{pct(lt.coverage, 0)}</span>
            </div>
            <Meter className="mt-2 h-2" value={lt.coverage} marker={0.8} color={lt.reliable ? "var(--good)" : "var(--series-3)"} />
            <p className="mt-1.5 text-xs text-muted">The line marks the 80% we need for reliable sector and company views.</p>
            {lt.excluded.length > 0 && (
              <ul className="mt-3 space-y-1.5 text-xs text-ink-2">
                {lt.excluded.map((e) => (
                  <li key={e.name} className="rounded-lg bg-surface-2 px-2.5 py-1.5"><span className="font-medium text-ink">{e.name}</span>: {e.reason}</li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Sectors" subtitle="Share of equity, after looking inside the funds. Red = above the review limit.">
          <BarList items={sectors} highlightAbove={sectorThreshold(r)} />
        </Card>
        <Card title="Fund overlap" subtitle={<>Pairs of funds that own the same stocks <Help>{GLOSSARY.overlap}</Help></>} icon={Layers}>
          {r.overlap.length === 0 ? (
            <p className="text-sm text-muted">Needs at least two funds with recent holdings data.</p>
          ) : (
            <div className="space-y-3">
              {r.overlap.map((o) => {
                const hot = o.overlap >= 0.5;
                return (
                  <div key={o.fund_a + o.fund_b} className={cx("rounded-xl border p-4", hot ? "border-bad/25 bg-bad-soft" : "border-line")}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 text-[13px]">
                        <div className="font-medium text-ink">{o.fund_a}</div>
                        <div className="text-xs text-faint">and</div>
                        <div className="font-medium text-ink">{o.fund_b}</div>
                      </div>
                      <div className="text-right">
                        <div className={cx("tabular text-2xl font-semibold tracking-tight", hot ? "text-bad" : "text-ink")}>{pct(o.overlap, 0)}</div>
                        <div className="text-xs text-muted">the same</div>
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-muted">{o.shared_stocks} stocks in common · data as of {date(o.as_of)}</div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>

      <Card title="Biggest companies" subtitle="Held directly plus held through funds, as a share of the whole portfolio" icon={Building2}>
        <CompaniesChart companies={a.top_companies} total={r.overview.current_value} />
      </Card>
    </div>
  );
}

/* ---------------------------------------------------------- Performance */

function Performance({ r }: { r: Report }) {
  const p = r.performance;
  const [range, setRange] = useState<Range>("ALL");
  const series = useMemo(() => sliceRange(p.series, range), [p.series, range]);
  if (p.series.length < 2) return <Notice>Not enough price history to show performance yet.</Notice>;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Annual return (XIRR)" help={GLOSSARY.xirr} icon={TrendingUp} value={pct(r.overview.xirr)} sub="What the client actually earned" />
        <Kpi label="Investment return" help={GLOSSARY.twr} icon={Waves} value={pct(p.twr_annualized)} sub="A year, ignoring timing of money" />
        <Kpi label="Index" icon={Scale} value={pct(p.benchmark_annualized)} sub={`${p.benchmark_name ?? "Benchmark"}, same period`} />
        <Kpi label="Period" icon={CalendarDays} value={<span className="text-lg">{date(p.period_start)}</span>} sub={`to ${date(p.period_end)}`} />
      </div>
      {!p.benchmark_compatible && p.benchmark_name && (
        <Notice>This portfolio holds a lot outside equity, so the equity index is shown for reference only.</Notice>
      )}
      <Card
        title="Growth of ₹100"
        subtitle="If ₹100 had been invested at the start, here is what it would be worth. New money never looks like growth here."
        action={<Segmented options={RANGES} value={range} onChange={setRange} />}
      >
        <div className="mb-3 flex flex-wrap gap-4 text-[12.5px] text-ink-2">
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-accent" />This portfolio</span>
          {p.benchmark_name && <span className="flex items-center gap-1.5"><span className="h-0 w-4 border-t-2 border-dashed border-[var(--series-3)]" />{p.benchmark_name}</span>}
        </div>
        <GrowthChart series={series} benchmarkName={p.benchmark_name} />
      </Card>
      <Card title="Value and money put in" subtitle="Money put in = purchases minus sale proceeds and dividends paid out">
        <ValueAreaChart series={series} height={280} />
      </Card>
      {r.contribution && <HelpedHurt r={r} />}
      <div className="grid gap-4 md:grid-cols-2">
        <Explainer icon={TrendingUp} title="Why the two returns differ">
          The annual return (XIRR) is what this investor earned, so the timing of each SIP matters. The investment return ignores
          timing; it is how funds and indices are compared.
        </Explainer>
        <Explainer icon={Scale} title="Which index">
          A total return index, which assumes dividends are reinvested, as mutual funds do internally.
        </Explainer>
      </div>
    </div>
  );
}

function Explainer({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: ReactNode }) {
  return (
    <div className="flex gap-3 rounded-2xl border border-line bg-surface p-4 text-[13.5px] shadow-card">
      <Icon size={18} className="mt-0.5 shrink-0 text-accent" />
      <div>
        <div className="font-semibold text-ink">{title}</div>
        <p className="mt-1 leading-relaxed text-ink-2">{children}</p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Risk */

function Risk({ r }: { r: Report }) {
  const k = r.risk;
  const [showMethods, setShowMethods] = useState(false);
  return (
    <div className="space-y-6">
      {!k.available && <Notice level="warning" title="Not enough history for risk numbers yet">{k.reason}</Notice>}
      {k.available && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi label="Ups and downs" help={GLOSSARY.volatility} icon={Waves} value={pct(k.volatility)} sub="Typical yearly swing (volatility)">
            <Meter className="mt-3 h-1.5" value={k.volatility ?? 0} max={0.4} color="var(--series-1)" />
          </Kpi>
          <Kpi label="Worst fall" help={GLOSSARY.drawdown} icon={TrendingDown} value={pct(k.max_drawdown)} tone="bad" sub={`${date(k.drawdown_peak)} → ${date(k.drawdown_trough)}`}>
            <Meter className="mt-3 h-1.5" value={Math.abs(k.max_drawdown ?? 0)} max={0.5} color="var(--bad)" />
          </Kpi>
          <Kpi label="Moves with the market" help={GLOSSARY.beta} icon={Activity} value={k.beta != null ? k.beta.toFixed(2) : "–"}
            sub={k.beta != null ? `About ${Math.round(k.beta * 100)}% as much as the index (beta)` : "Index not comparable"}>
            {k.beta != null && <Meter className="mt-3 h-1.5" value={k.beta} max={2} marker={1} color="var(--series-4)" />}
          </Kpi>
          <Kpi label="A bad day could cost" help={GLOSSARY.var} icon={Gauge} value={inr(k.var_95_1d)} sub={`1 day in 20 (95% VaR) · from ${k.observations} days`} />
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="How spread out it is" subtitle={<>Effective number of holdings <Help>{GLOSSARY.effective}</Help></>} icon={Scale}>
          <div className="flex items-end gap-6">
            <div>
              <div className="tabular text-3xl font-semibold tracking-tight text-ink">{k.effective_holdings?.toFixed(1) ?? "–"}</div>
              <div className="mt-1 text-xs text-muted">effective holdings</div>
            </div>
            <div className="pb-1 text-[13.5px] text-ink-2">
              The portfolio behaves like {k.effective_holdings?.toFixed(1)} equal-sized holdings, out of {r.overview.holdings_count} actual ones
              (HHI {k.hhi.toFixed(3)}).
            </div>
          </div>
          <div className="mt-5 flex gap-1" aria-hidden>
            {Array.from({ length: r.overview.holdings_count }).map((_, i) => (
              <div key={i} className={cx("h-6 flex-1 rounded", i < Math.round(k.effective_holdings ?? 0) ? "bg-accent" : "bg-surface-3")} />
            ))}
          </div>
        </Card>
        <Card title="How these are calculated" icon={BadgeCheck}
          action={<button className="no-print text-[13px] font-medium text-accent hover:underline" onClick={() => setShowMethods((s) => !s)}>{showMethods ? "Hide formulas" : "Show formulas"}</button>}>
          <p className="text-[13.5px] text-ink-2">
            All risk numbers use daily investment returns, so new money never looks like a gain. Period: {date(k.period_start)} to {date(k.period_end)}.
          </p>
          {showMethods && (
            <dl className="mt-4 space-y-3 text-[13px]">
              {Object.entries(k.method).map(([key, v]) => (
                <div key={key}>
                  <dt className="font-medium text-ink">{key === "var" ? "VaR" : titleCase(key)}</dt>
                  <dd className="mt-0.5 font-mono text-xs text-ink-2">{v}</dd>
                </div>
              ))}
            </dl>
          )}
        </Card>
      </div>
    </div>
  );
}
