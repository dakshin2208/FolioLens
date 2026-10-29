import { BookOpen } from "lucide-react";
import type { ReactNode } from "react";

import { PageHeader, useDocumentTitle } from "../components/ui";

const SECTIONS: { id: string; title: string; formula?: string; body: ReactNode }[] = [
  {
    id: "xirr",
    title: "XIRR (money-weighted return)",
    formula: "Σ Cᵢ / (1 + r)^((dᵢ − d₀) / 365) = 0",
    body: "The annual rate that makes the present value of every dated cash flow zero. Purchases are negative, redemptions, dividends paid out and today's value are positive. Solved by scanning for sign changes, Brent's method inside each bracket and a Newton polish. If two different rates both fit, FolioLens reports that instead of picking one.",
  },
  {
    id: "twr",
    title: "Time-weighted return",
    formula: "Rₜ = (Vₜ − Fₜ) / Vₜ₋₁ − 1",
    body: "Daily returns with the day's cash flow Fₜ removed, chained together and annualised. It shows how the investments performed regardless of when money was added, which is how funds and benchmarks are compared.",
  },
  {
    id: "holdings",
    title: "Holdings and cost",
    body: "Holdings are rebuilt from the transaction ledger every time, never stored separately. Cost uses the average-cost method; switches move cost between schemes. Each holding is valued at its latest price on or before the valuation date.",
  },
  {
    id: "lookthrough",
    title: "Look-through exposure",
    formula: "exposure(s) = Σ value in fund f × weight of s in f + direct holding of s",
    body: "Uses each fund's dated monthly disclosure. Disclosures older than 92 days are excluded and named. Sector and company views are flagged as partial when less than 80% of equity fund value is covered.",
  },
  {
    id: "overlap",
    title: "Fund overlap",
    formula: "overlap(A, B) = Σ min(weight in A, weight in B)",
    body: "Summed across every stock both funds hold. 81% means the two funds are mostly the same portfolio.",
  },
  {
    id: "risk",
    title: "Risk",
    formula: "σ = stdev(daily returns) × √252 · β = Cov(Rp, Rm) / Var(Rm)",
    body: "Volatility, maximum drawdown on the time-weighted wealth index, beta against the benchmark and 1-day 95% historical VaR, with a parametric VaR as a cross-check. Hidden when there is not enough history.",
  },
  {
    id: "concentration",
    title: "Concentration",
    formula: "HHI = Σ wᵢ² · effective holdings = 1 / HHI",
    body: "A portfolio of ten holdings can behave like four if a few dominate. Effective holdings makes that visible.",
  },
  {
    id: "profit",
    title: "What helped and what held it back",
    formula: "profit = value today + money taken out − money put in",
    body: "Worked out for every holding, including ones already sold, so all profits add up exactly to the portfolio's total profit. To compare an equity holding with the index fairly, FolioLens replays that holding's own purchases and sales into the index on the same dates (the public market equivalent method) and compares the two annual returns. A holding that trails this replay held the portfolio back.",
  },
  {
    id: "options",
    title: "Options to discuss",
    body: "Each review flag comes with a few concrete options: how much money is involved, what the measured value would become, and the trade-offs. For example, two overlapping funds can be combined into the one with the higher annual return since purchase, or new SIPs can go to one of them. The numbers are calculated, not written by AI. The advisor decides which options to show the client.",
  },
  {
    id: "tax",
    title: "Tax estimate",
    formula: "equity: 20% on gains held ≤ 12 months · 12.5% on longer-held gains above ₹1.25 lakh a year",
    body: "If an option involves selling, FolioLens estimates capital-gains tax using first-in, first-out lots (the oldest units are sold first) under FY 2026-27 rules for equity-oriented holdings. It shows two figures: if the client's yearly ₹1.25 lakh exemption is still unused, and if it is already used. For debt, gold and other funds the rules depend on the fund type and purchase date, so only the gain is shown. Exit loads, surcharge and cess are not included.",
  },
  {
    id: "riskprofile",
    title: "Risk profile and suitability",
    formula: "score = average answer (0–4) ÷ 4 × 100 · equity share = equity + ½ × hybrid",
    body: "Six questions (age, horizon, income, reaction to a 20% fall, experience, emergency savings) give a score from 0 to 100 and one of five profiles, each with a suggested equity range: Conservative 10–30%, Moderately conservative 25–45%, Moderate 40–60%, Moderately aggressive 55–75%, Aggressive 70–90%. If the portfolio's equity share is outside the range, FolioLens flags it and works out the rebalance: the amount to move, the holdings to sell (smallest gains first, to keep tax low) and the estimated tax. It is a transparent starting model; advisors should also follow their firm's own risk-profiling process.",
  },
  {
    id: "goals",
    title: "Goal projections",
    formula: "target then = target today × (1 + inflation)^years · projected = set aside × (1 + r)^years + SIP × FV factor",
    body: "Each goal has a target in today's rupees, a date, a monthly SIP and a share of today's portfolio set aside for it. The target grows with 6% inflation. The money grows at an expected return r taken from the portfolio's own asset mix (equity 11%, hybrid 9%, debt 7%, gold 7%, cash 5% a year; planning assumptions, not forecasts). Funded = projected ÷ target then: 100% or more is on track, 80–100% slightly short, below 80% not on track. For a goal that falls short, FolioLens works out the SIP needed, how much later the goal could move, the target the plan can reach, and the one-time amount that would close the gap. A goal less than 3 years away whose money sits in a mostly-equity portfolio is flagged too.",
  },
  {
    id: "ai",
    title: "AI explanations",
    body: "Findings come from fixed rules with configured thresholds. A language model only rewrites a finding, and the portfolio summary, in plain English. Every number it writes must match the calculated facts, dates must come from the data, and buy or sell instructions are rejected. Anything that fails is retried once, then replaced with a template written from the numbers.",
  },
];

export function MethodologyPage() {
  useDocumentTitle("Methodology");
  return (
    <div className="space-y-6">
      <PageHeader
        leading={<span className="grid h-12 w-12 place-items-center rounded-xl bg-accent-soft text-accent"><BookOpen size={22} /></span>}
        title="How we calculate"
        subtitle="Every number in a FolioLens report, and where it comes from."
      />
      <div className="grid items-start gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
        <nav className="sticky top-6 hidden space-y-0.5 lg:block">
          {SECTIONS.map((s) => (
            <a key={s.id} href={`#${s.id}`} className="block rounded-lg px-3 py-1.5 text-[13px] text-muted hover:bg-surface hover:text-ink">{s.title}</a>
          ))}
        </nav>
        <div className="space-y-4">
          {SECTIONS.map((s) => (
            <section key={s.id} id={s.id} className="scroll-mt-6 rounded-2xl border border-line bg-surface p-6 shadow-card">
              <h2 className="text-[17px] font-semibold tracking-tight text-ink">{s.title}</h2>
              {s.formula && (
                <div className="mt-3 overflow-x-auto rounded-xl bg-surface-2 px-4 py-3 font-mono text-[13px] text-ink-2">{s.formula}</div>
              )}
              <p className="mt-3 text-sm leading-relaxed text-ink-2">{s.body}</p>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}

export function NotFoundPage() {
  useDocumentTitle("Not found");
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <div className="tabular text-6xl font-semibold tracking-tight text-accent">404</div>
      <h1 className="mt-3 text-xl font-semibold text-ink">This page doesn't exist</h1>
      <a href="/" className="mt-5 text-sm font-medium text-accent hover:underline">Back to FolioLens</a>
    </div>
  );
}
