import {
  ArrowRight,
  BadgeCheck,
  Calculator,
  Check,
  FileText,
  Lightbulb,
  Lock,
  MessageSquareQuote,
  Send,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { MarketingLayout } from "../components/Layout";
import { buttonCls, cx, useDocumentTitle } from "../components/ui";
import { api } from "../lib/api";
import { inr, pct, signedInr } from "../lib/format";
import type { Report } from "../lib/types";

export function useDemoReport() {
  const [r, setR] = useState<Report | null>(null);
  useEffect(() => {
    api.demoReport().then(setR).catch(() => setR(null));
  }, []);
  return r;
}

const ICONS: Record<string, { icon: LucideIcon; cls: string }> = {
  headline: { icon: Lightbulb, cls: "bg-accent-soft text-accent" },
  good: { icon: ThumbsUp, cls: "bg-good-soft text-good" },
  bad: { icon: ThumbsDown, cls: "bg-bad-soft text-bad" },
  warn: { icon: MessageSquareQuote, cls: "bg-warn-soft text-warn" },
};

/** A live preview of the sample client's review, built from the real demo report. */
function PreviewCard({ r }: { r: Report | null }) {
  const overlap = r?.findings.find((f) => f.type === "fund_overlap");
  const option = overlap?.options?.[0];
  return (
    <div className="relative rounded-3xl border border-line bg-surface p-5 shadow-float sm:p-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-muted">Sample client · review</div>
          <div className="mt-0.5 text-lg font-semibold text-ink">{r ? inr(r.overview.current_value) : "₹43,78,102"}</div>
        </div>
        <span className="rounded-full bg-good-soft px-2.5 py-1 text-xs font-semibold text-good">
          {r ? `${signedInr(r.overview.current_value - r.overview.net_invested)} profit` : "+ profit"}
        </span>
      </div>
      <ul className="mt-5 space-y-3">
        {(r?.summary?.points ?? []).slice(1, 4).map((p, i) => {
          const m = ICONS[p.kind] ?? ICONS.headline!;
          return (
            <li key={i} className="flex gap-3">
              <span className={cx("grid h-7 w-7 shrink-0 place-items-center rounded-lg", m.cls)}><m.icon size={14} /></span>
              <p className="text-[13.5px] leading-relaxed text-ink-2">{p.text}</p>
            </li>
          );
        })}
        {!r && [0, 1, 2].map((i) => <li key={i} className="skeleton h-10" />)}
      </ul>
      {option && (
        <div className="mt-5 rounded-2xl border border-accent/20 bg-accent-soft p-4">
          <div className="flex items-center gap-2 text-[12px] font-semibold text-accent"><Lightbulb size={14} />Option to discuss</div>
          <div className="mt-1 text-[14px] font-semibold text-ink">{option.title}</div>
          <div className="mt-1 text-[12.5px] text-ink-2">
            Money to move {inr(Number(option.impact[0]?.value ?? 0))}
            {option.tax?.tax_if_exemption_unused != null && <> · estimated tax {inr(option.tax.tax_if_exemption_unused)}</>}
          </div>
        </div>
      )}
    </div>
  );
}

export function Landing() {
  useDocumentTitle("");
  const report = useDemoReport();
  return (
    <MarketingLayout>
      <section className="relative overflow-hidden border-b border-line">
        <div className="soft-grid absolute inset-0" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:py-24">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent-soft px-3 py-1 text-[12.5px] font-medium text-accent">
              <Sparkles size={14} /> For Indian financial advisors
            </div>
            <h1 className="mt-6 text-[38px] font-bold leading-[1.08] tracking-[-0.02em] text-ink sm:text-[52px]">
              Portfolio reviews your clients <span className="text-accent">actually understand.</span>
            </h1>
            <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-ink-2">
              Upload a client's CAS or broker statement. FolioLens checks every number, explains in plain English what helped and what
              hurt, suggests options with their tax cost, and gives you a client-ready report and email.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/demo" className={buttonCls("primary", "lg", "h-12 px-6")}>
                See a sample review <ArrowRight size={17} />
              </Link>
              <Link to="/register" className={buttonCls("secondary", "lg", "h-12 px-6")}>Try with a real statement</Link>
            </div>
            <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-[13.5px] text-ink-2">
              {["Numbers checked, never invented by AI", "Tax estimate on every option", "Files deleted after reading"].map((t) => (
                <li key={t} className="flex items-center gap-1.5"><Check size={15} className="text-good" />{t}</li>
              ))}
            </ul>
          </div>
          <PreviewCard r={report} />
        </div>
      </section>

      <section id="how" className="mx-auto max-w-6xl scroll-mt-24 px-4 py-20 sm:px-6">
        <div className="max-w-2xl">
          <div className="text-[13px] font-semibold text-accent">How it works</div>
          <h2 className="mt-2 text-[30px] font-bold tracking-tight text-ink">From a statement to a client conversation in four steps</h2>
        </div>
        <ol className="mt-10 grid gap-4 md:grid-cols-4">
          {[
            { icon: FileText, t: "Upload", d: "CAMS / KFintech CAS PDF, Zerodha tradebook or our CSV template." },
            { icon: BadgeCheck, t: "We check", d: "Every scheme is matched; rebuilt units must equal the statement. Nothing is guessed." },
            { icon: Lightbulb, t: "You review", d: "A plain-English summary, what helped and hurt, and options for each concern." },
            { icon: Send, t: "Share", d: "Tick the options you suggest. Print the client report and send the ready email." },
          ].map((s, i) => (
            <li key={s.t} className="rounded-2xl border border-line bg-surface p-5 shadow-card">
              <div className="flex items-center gap-3">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent-soft text-accent"><s.icon size={18} /></span>
                <span className="text-[13px] font-semibold text-muted">Step {i + 1}</span>
              </div>
              <h3 className="mt-4 text-[17px] font-semibold text-ink">{s.t}</h3>
              <p className="mt-1.5 text-[14px] leading-relaxed text-ink-2">{s.d}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-y border-line bg-surface py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="max-w-2xl">
            <div className="text-[13px] font-semibold text-accent">What you get</div>
            <h2 className="mt-2 text-[30px] font-bold tracking-tight text-ink">Not just numbers: the why, the options and the report</h2>
          </div>
          <div className="mt-10 grid gap-5 md:grid-cols-3">
            <Feature icon={Lightbulb} title="Explains the why">
              “Behind the index by {report?.performance.benchmark_annualized != null && report.performance.twr_annualized != null ? `${Math.abs((report.performance.benchmark_annualized - report.performance.twr_annualized) * 100).toFixed(1)} points` : "3.3 points"}, mainly because of one stock.”
              Each holding is compared with the index using the same money on the same dates.
            </Feature>
            <Feature icon={Calculator} title="Suggests options, with tax">
              Two funds 81% the same? Combine them, or redirect SIPs. Each option shows the money involved, the result and an estimated
              capital-gains tax (FY 2026-27 rules).
            </Feature>
            <Feature icon={Send} title="Ready for the client">
              A 2–3 page report in simple language, with only the next steps you chose, plus an email draft you can edit and send.
            </Feature>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
        <div className="grid gap-8 rounded-3xl border border-line bg-surface p-8 shadow-card md:grid-cols-[1.2fr_1fr] md:p-10">
          <div>
            <h2 className="text-[26px] font-bold tracking-tight text-ink">Built to be trusted</h2>
            <p className="mt-3 text-[15px] leading-relaxed text-ink-2">
              Calculations come first: XIRR matches Excel, units reconcile to the statement, and the AI only rewrites facts in plain
              English. If it writes a number that is not in the data, its text is thrown away and a template is used.
            </p>
            <Link to="/methodology" className="mt-5 inline-flex items-center gap-1.5 text-[14px] font-medium text-accent hover:underline">How we calculate <ArrowRight size={15} /></Link>
          </div>
          <ul className="space-y-3 text-[14px] text-ink-2">
            {[
              { icon: ShieldCheck, t: "Only you can see your clients; every access is checked." },
              { icon: Lock, t: "CAS passwords stay in memory for at most 10 minutes." },
              { icon: FileText, t: "Statement files are deleted right after reading." },
              { icon: BadgeCheck, t: report ? `Sample: ${pct(report.overview.xirr)} XIRR, ${report.findings.length} points to discuss.` : "Every number has its evidence." },
            ].map((x) => (
              <li key={x.t} className="flex gap-3"><x.icon size={18} className="mt-0.5 shrink-0 text-good" />{x.t}</li>
            ))}
          </ul>
        </div>
        <div className="mt-12 text-center">
          <Link to="/demo" className={buttonCls("primary", "lg", "h-12 px-7")}>See the sample review <ArrowRight size={17} /></Link>
        </div>
      </section>
    </MarketingLayout>
  );
}

function Feature({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-line bg-page p-6">
      <span className="grid h-10 w-10 place-items-center rounded-xl bg-accent-soft text-accent"><Icon size={19} /></span>
      <h3 className="mt-4 text-[17px] font-semibold text-ink">{title}</h3>
      <p className="mt-2 text-[14px] leading-relaxed text-ink-2">{children}</p>
    </div>
  );
}
