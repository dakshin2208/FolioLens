# Decisions log

| ID | Decision | Choice | Reason |
| --- | --- | --- | --- |
| D-01 | Statement formats | CAMS/KFintech detailed CAS; Zerodha tradebook CSV; generic CSV | Covers most mutual fund investors and one large broker; the generic CSV covers everything else |
| D-02 | Market data | AMFI NAV files, NSE bhavcopy, Nifty 50 TRI export, AMC disclosures | Public sources; terms must be verified before commercial use |
| D-03 | Transaction events | Payout = cash inflow; reinvest = units added, no external flow; switch = linked out/in, internal to the portfolio; stamp duty folded into the purchase amount, STT/TDS deducted from redemption proceeds | Uses the investor's real cash flows and avoids double counting |
| D-04 | Conventions | Latest price on or before the valuation date (≤ 5 trading rows forward fill); XIRR outflows negative; Actual/365 | Matches Excel and industry practice |
| D-05 | Minimum coverage | Risk needs ≥ 365 days and ≥ 200 daily returns; look-through needs ≥ 80% of equity fund value with constituents ≤ 92 days old | Avoids confident numbers from thin data |
| D-06 | Matching | Exact ISIN or exact stock symbol auto-matches; name similarity ≥ 0.90 is only a suggestion | Nothing is guessed silently |
| D-07 | Job framework | Redis + RQ with retries; idempotent jobs | Simpler than Celery at this scale |
| D-08 | AWS shape | One EC2 with Docker Compose, RDS in a private subnet, private S3 | Cheapest setup that is still secure and realistic |
| D-09 | Retention | Raw file deleted after parse; failed uploads after 24 h; extracted data until the user deletes the portfolio | Minimal retention of sensitive files |
| D-10 | Correctness | XIRR within 0.01 percentage points of Excel; values within ₹1 | Measurable acceptance criteria |
| D-13 | Holdings storage | Derived from the ledger on demand, no holdings table | One source of truth; no sync bugs |
| D-14 | Drawdown basis | Time-weighted wealth index, not raw portfolio value | Raw value rises with every SIP, which hides real falls |
| D-15 | Demo data | Fully synthetic, fixed seed, fictional names, ISINs prefixed `XX` | No real person's data; deterministic screenshots and tests |
| D-16 | Sector data | Stored on the instrument (`sector`, `market_cap`) instead of a separate table | Simpler for V1; history of reclassifications not needed yet |
| D-17 | LLM | Provider adapter (Anthropic or OpenAI), JSON output, number validation, template fallback; demo always uses templates | Cost control, determinism, and the product never depends on the LLM |
| D-18 | Ownership errors | Another user's resource returns 404, not 403 | Doesn't reveal that the id exists |

## D-UI-1: Redesigned frontend with a design-token system (v1.1)
**Decision:** Dark sidebar app shell, token-based light theme, Inter (self-hosted), lucide icons, and a
dashboard-style report. **Why:** the product is judged in seconds by advisors and recruiters; a polished,
consistent UI makes the verified analytics credible. **Trade-off:** two small new dependencies
(`lucide-react`, `@fontsource-variable/inter`); no CDN, so the CSP stays strict.

## D-UI-2: Trading-terminal theme (v1.2)
**Decision:** Replace the generic light SaaS look with a dark market-terminal theme: gold brand, green/red only
for gains/losses, monospace figures, ticker tape from real price data, quote strip, heatmap, candles and a
command palette. **Why:** the product should look like a finance tool at first glance and show what it does.
**Trade-off:** dark-only UI; printing switches to a light palette.

## D-19: Profit attribution and index comparison (engine 1.1)
**Decision:** Lifetime profit per holding (including sold holdings) and a public-market-equivalent comparison
with the index on the holding's own cash flows. **Why:** explains *why* returns differ from the index, like for
like. **Trade-off:** only equity holdings are compared with the equity index.

## D-20: Tax estimate on options
**Decision:** FIFO lots; FY 2026-27 equity rules (20% STCG ≤ 12 months, 12.5% LTCG above ₹1.25 lakh); two
figures (exemption unused / used); gain only for non-equity. **Why:** the cost of acting is what advisors
need; showing only what can be calculated honestly. **Trade-off:** exit loads, surcharge, cess and
grandfathering are excluded and labelled as such. Rates live in `app/analytics/tax.py`; change them there and
bump `CALC_VERSION`.

## D-21: Options are calculated, not generated
**Decision:** Options to discuss come from deterministic code with numbers; the LLM never proposes actions.
**Why:** principle 7 (the LLM only explains) and SEBI: the advisor makes the recommendation.

## D-22: Summary through the same validator
**Decision:** The LLM may rewrite the template summary only if every number passes `validate_explanation`.
**Why:** one validation path for all AI text.

## D-UI-3: Light, plain-language design with a client report (v1.3)
**Decision:** Light theme by default (dark optional), plain labels with `?` help, guided steps, a Summary-first
report, and a printable client report with an email draft. Removed ticker tape, status bar and candles.
**Why:** advisors found the terminal look hard to use and the output had no clear next step.
**Trade-off:** less "trading screen" flair.

## D-23: Risk profiling model (engine 1.2)
**Decision:** Six questions, average score → five profiles with equity ranges; hybrid counts half equity.
**Why:** transparent and explainable in one sentence. **Trade-off:** not a regulatory questionnaire; the
UI tells advisors to also use their firm's process.

## D-24: Goal planning maths
**Decision:** Inflation 6%; expected return from the portfolio's asset mix (equity 11%, hybrid 9%, debt 7%,
gold 7%, cash 5%); deterministic projection, not Monte Carlo; thresholds 100% / 80%. **Why:** an advisor
can check every number by hand. **Trade-off:** no range of outcomes yet. Assumptions live in
`app/analytics/planning.py`; change them there and bump `CALC_VERSION`.

## D-25: Plan storage as JSON
**Decision:** One `client_plans` row per portfolio with answers and goals as JSON. **Why:** small, always
read and written together, validated by Pydantic. **Trade-off:** no SQL queries across goals.

## D-26: Tax-aware selection
**Decision:** Rebalancing sells the holdings with the smallest gain per rupee first. **Why:** the same
amount moves with the least tax. **Trade-off:** ignores exit loads and fund quality; the advisor decides.
