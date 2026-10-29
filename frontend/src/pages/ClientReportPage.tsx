import { ArrowLeft, Check, Copy, Mail, Printer } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { DISCLAIMER, LogoMark, ThemeToggle } from "../components/Layout";
import { Donut, LegendList, ValueAreaChart } from "../components/charts";
import { Button, Notice, PageSkeleton, buttonCls, cx, useDocumentTitle, useToast } from "../components/ui";
import { api } from "../lib/api";
import { ASSET_COLORS, SERIES, date, inr, inrShort, pct, signedInr, signedPct, titleCase } from "../lib/format";
import { impactText, readPlan, taxLine } from "../lib/plan";
import type { ActionOption, Finding, Report } from "../lib/types";

/** Client-facing report for a saved client. */
export function ClientReportPage() {
  const { id = "" } = useParams();
  const [report, setReport] = useState<Report | null>(null);
  const [client, setClient] = useState("");
  const [advisor, setAdvisor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    Promise.all([api.portfolio(id), api.report(id)])
      .then(([p, r]) => {
        setClient(p.client_name);
        setReport(r);
      })
      .catch((e) => setError((e as Error).message));
    api.me().then((m) => setAdvisor(m.email)).catch(() => undefined);
  }, [id]);
  return <ClientReport report={report} client={client} advisor={advisor} error={error} storageKey={id} back={`/app/p/${id}`} />;
}

/** The same page for the synthetic demo. */
export function DemoClientReportPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.demoReport().then(setReport).catch((e) => setError((e as Error).message));
  }, []);
  return <ClientReport report={report} client="Sample Client" advisor={null} error={error} storageKey="demo" back="/demo" demo />;
}

function firstName(name: string) {
  const n = name.replace(/\(.*?\)/g, "").trim();
  const parts = n.split(/\s+/);
  return parts.length > 1 && /^[A-Z]\.?$/.test(parts[0]!) ? n : parts[0] ?? n;
}

function ClientReport({ report, client, advisor, error, storageKey, back, demo }: {
  report: Report | null;
  client: string;
  advisor: string | null;
  error: string | null;
  storageKey: string;
  back: string;
  demo?: boolean;
}) {
  useDocumentTitle(client ? `${client}: portfolio review` : "Client report");
  const chosen = useMemo(() => new Set(readPlan(storageKey)), [storageKey]);
  const toast = useToast();

  if (error) return <Shell back={back}><Notice level="error" title="Could not load the report">{error}</Notice></Shell>;
  if (!report) return <Shell back={back}><PageSkeleton /></Shell>;
  if (report.status !== "ok") return <Shell back={back}><Notice>{report.message}</Notice></Shell>;

  const o = report.overview;
  const p = report.performance;
  const profit = o.current_value - o.net_invested;
  const steps: { f: Finding; o: ActionOption }[] = report.findings.flatMap((f) => (f.options ?? []).filter((x) => chosen.has(x.id)).map((x) => ({ f, o: x })));
  const assets = report.allocation.asset_class.map((a, i) => ({ name: titleCase(a.name), weight: a.weight, value: a.value, color: ASSET_COLORS[a.name] ?? SERIES[i % SERIES.length]! }));
  const items = Object.fromEntries((report.contribution?.items ?? []).map((i) => [i.instrument_id, i]));
  const helped = (report.contribution?.helped ?? []).map((i) => items[i]!).filter(Boolean);
  const hurt = (report.contribution?.hurt ?? []).map((i) => items[i]!).filter(Boolean);
  const gap = p.benchmark_compatible && p.twr_annualized != null && p.benchmark_annualized != null ? p.twr_annualized - p.benchmark_annualized : null;
  const today = new Date().toISOString().slice(0, 10);

  const email = buildEmail({ client, advisor, report, steps });
  const pl = report.planning;
  let k = 0;
  const sec = () => ++k;

  return (
    <Shell back={back} actions={<Button icon={Printer} onClick={() => window.print()}>Print or save as PDF</Button>}>
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,820px)_minmax(0,1fr)]">
        <article className="print-full rounded-2xl border border-line bg-surface px-6 py-8 shadow-card sm:px-10 sm:py-10">
          <header className="flex flex-wrap items-start justify-between gap-4 border-b border-line pb-6">
            <div>
              <div className="text-[13px] font-medium text-accent">Portfolio review</div>
              <h1 className="mt-1 text-[28px] font-semibold tracking-tight text-ink">{client}</h1>
              <p className="mt-1 text-sm text-muted">Prepared on {date(today)} · values as of {date(report.meta.valuation_date)}{advisor ? ` · by ${advisor}` : ""}</p>
            </div>
            <div className="flex items-center gap-2 text-sm font-semibold text-ink"><LogoMark size={24} />FolioLens</div>
          </header>
          {demo && <p className="mt-4 rounded-lg bg-warn-soft px-3 py-2 text-xs text-ink-2">Sample report: every company, fund and price here is fictional.</p>}

          <Section n={sec()} title="In short">
            <p className="text-[15px] leading-relaxed text-ink-2">{report.summary?.text ?? "Update the report to include the summary."}</p>
          </Section>

          <Section n={sec()} title="Your portfolio at a glance">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Value today" value={inr(o.current_value)} />
              <Stat label="Total profit" value={signedInr(profit)} tone={profit >= 0 ? "good" : "bad"} sub={o.net_invested > 0 ? `${signedPct(profit / o.net_invested)} on money put in` : undefined} />
              <Stat label="Yearly return" value={pct(o.xirr)} sub="Taking timing into account" />
              <Stat label="Against the market" value={gap == null ? "–" : `${gap >= 0 ? "+" : "−"}${Math.abs(gap * 100).toFixed(1)} pts`} tone={gap == null ? undefined : gap >= 0 ? "good" : "bad"} sub={gap == null ? undefined : `vs ${p.benchmark_name}`} />
            </div>
            {p.series.length > 1 && (
              <div className="mt-5">
                <ValueAreaChart series={p.series} height={220} />
                <p className="mt-1 text-xs text-muted">Green line: value of the portfolio. Dashed line: money put in (net). The gap between them is the profit.</p>
              </div>
            )}
          </Section>

          {pl?.available && (
            <Section n={sec()} title="Your goals and risk">
              {pl.profile && (
                <p className="text-[14px] leading-relaxed text-ink-2">
                  Your answers suggest a <strong className="text-ink">{pl.profile.category.toLowerCase()}</strong> approach, with {pct(pl.profile.equity_min, 0)} to {pct(pl.profile.equity_max, 0)} of
                  the portfolio in equity. Today it is <strong className={pl.in_range ? "text-good" : "text-bad"}>{pct(pl.equity_share)}</strong>
                  {pl.in_range ? ", which fits." : `, which is ${pl.equity_share > pl.profile.equity_max ? "more" : "less"} than suggested.`}
                </p>
              )}
              {pl.goals.length > 0 && (
                <table className="mt-4 w-full text-[13px]">
                  <thead className="text-left text-xs text-muted">
                    <tr className="border-b border-line">
                      <th className="py-2 font-medium">Goal</th><th className="py-2 font-medium">By</th>
                      <th className="py-2 text-right font-medium">Needed then</th><th className="py-2 text-right font-medium">Expected</th><th className="py-2 text-right font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="tabular divide-y divide-[var(--border)]">
                    {pl.goals.map((g) => (
                      <tr key={g.id}>
                        <td className="py-2 text-ink">{g.name}</td>
                        <td className="py-2 text-ink-2">{date(g.target_date)}</td>
                        <td className="whitespace-nowrap py-2 text-right text-ink-2">{inr(g.target_future)}</td>
                        <td className="whitespace-nowrap py-2 text-right text-ink-2">{inr(g.projected)}</td>
                        <td className={cx("py-2 text-right font-medium", g.status === "on_track" ? "text-good" : g.status === "at_risk" ? "text-warn" : "text-bad")}>
                          {g.status === "on_track" ? "On track" : g.status === "at_risk" ? "Slightly short" : g.status === "due" ? "Due" : "Not on track"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <p className="mt-2 text-xs text-muted">
                “Needed then” includes {pct(pl.assumptions.inflation, 0)} yearly inflation. “Expected” assumes about {pct(pl.assumptions.portfolio_expected_return)} a year from the
                current mix; these are planning assumptions, not promises.
              </p>
            </Section>
          )}

          <Section n={sec()} title="What you own">
            <div className="flex flex-col items-center gap-6 sm:flex-row">
              <Donut items={assets} center={inrShort(o.current_value)} sub={`${o.holdings_count} holdings`} size={150} />
              <LegendList items={assets} />
            </div>
            <table className="mt-5 w-full text-[13px]">
              <thead className="text-left text-xs text-muted"><tr className="border-b border-line"><th className="py-2 font-medium">Largest holdings</th><th className="py-2 text-right font-medium">Value</th><th className="py-2 text-right font-medium">Share</th></tr></thead>
              <tbody className="tabular divide-y divide-[var(--border)]">
                {report.holdings.slice(0, 6).map((h) => (
                  <tr key={h.instrument_id}><td className="py-2 text-ink">{h.name}</td><td className="whitespace-nowrap py-2 text-right text-ink-2">{inr(h.value)}</td><td className="py-2 text-right text-ink-2">{pct(h.weight)}</td></tr>
                ))}
              </tbody>
            </table>
          </Section>

          {(helped.length > 0 || hurt.length > 0) && (
            <Section n={sec()} title="What helped and what held it back">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <div className="mb-2 text-[13px] font-semibold text-good">Helped most</div>
                  <ul className="space-y-1.5 text-[13.5px]">
                    {helped.map((i) => <li key={i.instrument_id} className="flex justify-between gap-3"><span className="text-ink">{i.name}</span><span className="tabular shrink-0 text-good">{signedInr(i.profit)}</span></li>)}
                  </ul>
                </div>
                <div>
                  <div className="mb-2 text-[13px] font-semibold text-bad">Held it back</div>
                  {hurt.length ? (
                    <ul className="space-y-1.5 text-[13.5px]">
                      {hurt.map((i) => (
                        <li key={i.instrument_id} className="flex justify-between gap-3"><span className="text-ink">{i.name}</span>
                          <span className="tabular shrink-0 text-bad">{i.profit < 0 ? signedInr(i.profit) : i.vs_index != null ? `${(i.vs_index * 100).toFixed(1)} pts vs index` : ""}</span></li>
                      ))}
                    </ul>
                  ) : <p className="text-[13.5px] text-muted">Nothing lost money or trailed the index.</p>}
                </div>
              </div>
            </Section>
          )}

          <Section n={sec()} title="Points to discuss">
            {report.findings.length ? (
              <ul className="space-y-4">
                {report.findings.map((f) => (
                  <li key={f.id} className="avoid-break">
                    <div className="text-[14px] font-semibold text-ink">{f.title}</div>
                    <p className="mt-0.5 text-[13.5px] leading-relaxed text-ink-2">{f.explanation}</p>
                  </li>
                ))}
              </ul>
            ) : <p className="text-[13.5px] text-ink-2">Nothing crossed a review limit.</p>}
          </Section>

          <Section n={sec()} title="Suggested next steps">
            {steps.length ? (
              <ul className="space-y-4">
                {steps.map(({ o: opt }) => (
                  <li key={opt.id} className="avoid-break rounded-xl border border-line p-4">
                    <div className="flex items-start gap-2 text-[14px] font-semibold text-ink"><Check size={16} className="mt-0.5 shrink-0 text-accent" />{opt.title}</div>
                    <p className="mt-1 text-[13.5px] leading-relaxed text-ink-2">{opt.summary}</p>
                    <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[12.5px] text-muted">
                      {opt.impact.slice(0, 3).map((i) => <span key={i.label}>{i.label}: <span className="tabular font-medium text-ink">{impactText(i)}</span></span>)}
                    </div>
                    {opt.tax && <p className="mt-2 text-[12.5px] text-ink-2">{taxLine(opt.tax)}</p>}
                  </li>
                ))}
              </ul>
            ) : (
              <>
                <p className="text-[13.5px] text-ink-2">We will agree the next steps together when we meet.</p>
                <p className="no-print mt-2 rounded-lg bg-accent-soft px-3 py-2 text-[12.5px] text-ink-2">
                  Tip for you: tick options under <Link to={back} className="font-medium text-accent hover:underline">To discuss</Link> and they appear here.
                </p>
              </>
            )}
          </Section>

          <footer className="mt-10 border-t border-line pt-4 text-[11px] leading-relaxed text-muted">
            <p>Numbers are calculated from the client's statements and the market data listed in the report (calculation version {report.meta.calc_version}). Tax figures are estimates under current Indian rules and exclude exit loads, surcharge and cess. Past returns do not guarantee future returns.</p>
            <p className="mt-2">{DISCLAIMER}</p>
          </footer>
        </article>

        <aside className="no-print space-y-4 xl:sticky xl:top-6">
          <EmailDraft email={email} onCopied={() => toast("success", "Email copied. Paste it into your mail app.")} />
          <div className="rounded-2xl border border-line bg-surface p-4 text-[13px] text-ink-2 shadow-card">
            <div className="font-semibold text-ink">Before you send</div>
            <ul className="mt-2 space-y-1.5">
              <li>• Read the summary once; edit the email to your own words.</li>
              <li>• Use <strong>Print or save as PDF</strong> and attach the PDF.</li>
              <li>• {steps.length ? `${steps.length} next step${steps.length === 1 ? "" : "s"} included.` : "No next steps ticked yet."}</li>
            </ul>
          </div>
        </aside>
      </div>
    </Shell>
  );
}

function Shell({ back, actions, children }: { back: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-page">
      <div className="no-print sticky top-0 z-20 border-b border-line bg-surface/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1280px] items-center justify-between gap-3 px-4 sm:px-6">
          <Link to={back} className="inline-flex items-center gap-2 text-[14px] font-medium text-ink-2 hover:text-ink"><ArrowLeft size={16} />Back to the review</Link>
          <div className="flex items-center gap-2"><ThemeToggle />{actions}</div>
        </div>
      </div>
      <main className="print-full mx-auto max-w-[1280px] px-4 py-8 sm:px-6">{children}</main>
    </div>
  );
}

function Section({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="mb-3 flex items-center gap-2.5 text-[17px] font-semibold tracking-tight text-ink">
        <span className="grid h-6 w-6 place-items-center rounded-full bg-accent-soft text-[12px] font-bold text-accent">{n}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "good" | "bad" }) {
  return (
    <div className="rounded-xl bg-surface-2 p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className={cx("tabular mt-1 text-[18px] font-semibold", tone === "good" ? "text-good" : tone === "bad" ? "text-bad" : "text-ink")}>{value}</div>
      {sub && <div className="mt-0.5 text-[11.5px] text-muted">{sub}</div>}
    </div>
  );
}

function buildEmail({ client, advisor, report, steps }: { client: string; advisor: string | null; report: Report; steps: { f: Finding; o: ActionOption }[] }) {
  const lines = [
    `Dear ${firstName(client) || "Sir/Madam"},`,
    "",
    "I have reviewed your investment portfolio. Here is a short summary:",
    "",
    report.summary?.text ?? `Your portfolio is worth ${inr(report.overview.current_value)}.`,
    "",
  ];
  if (report.findings.length) {
    lines.push("A few points I would like to discuss with you:");
    for (const f of report.findings.slice(0, 4)) lines.push(`- ${f.title}`);
    lines.push("");
  }
  if (steps.length) {
    lines.push("Options I suggest we consider:");
    for (const s of steps) lines.push(`- ${s.o.title}${s.o.tax ? ` (${taxLine(s.o.tax)})` : ""}`);
    lines.push("");
  }
  lines.push("The full review is attached. Could we find 20 minutes this week to go through it together?", "", "Warm regards,", advisor ?? "");
  return { subject: `Your portfolio review, ${date(report.meta.valuation_date)}`, body: lines.join("\n").trim() };
}

function EmailDraft({ email, onCopied }: { email: { subject: string; body: string }; onCopied: () => void }) {
  const [subject, setSubject] = useState(email.subject);
  const [body, setBody] = useState(email.body);
  useEffect(() => {
    setSubject(email.subject);
    setBody(email.body);
  }, [email.subject, email.body]);
  const mailto = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-card">
      <div className="flex items-center gap-2 text-[15px] font-semibold text-ink"><Mail size={16} className="text-accent" />Email to the client</div>
      <p className="mt-0.5 text-[12.5px] text-muted">A ready draft. Edit it freely; nothing is sent from FolioLens.</p>
      <input className="mt-3 h-9 w-full rounded-lg border border-line-strong bg-surface px-3 text-[13px] text-ink outline-none focus:border-accent" value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Email subject" />
      <textarea className="scroll-thin mt-2 h-80 w-full resize-y rounded-lg border border-line-strong bg-surface p-3 text-[13px] leading-relaxed text-ink outline-none focus:border-accent" value={body} onChange={(e) => setBody(e.target.value)} aria-label="Email body" />
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" icon={Copy} onClick={async () => { try { await navigator.clipboard.writeText(`${subject}\n\n${body}`); onCopied(); } catch { /* clipboard blocked */ } }}>Copy email</Button>
        <a href={mailto} className={buttonCls("secondary", "sm")}><Mail size={14} />Open in mail app</a>
      </div>
    </div>
  );
}
