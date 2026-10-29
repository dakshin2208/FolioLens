# Learning notes and interview preparation

Read this file before any interview that mentions FolioLens. Run the app, open each file named
here, and be able to explain it in your own words.

## 1. The 60-second explanation

"FolioLens is a portfolio analytics tool for Indian financial advisors. An advisor uploads a client's
mutual fund statement, the CAS from CAMS or KFintech. I parse it into a transaction ledger, rebuild
holdings from the ledger, and calculate the real return (XIRR), allocation, look-through exposure to
the companies inside each fund, fund overlap and historical risk. A rules engine flags things like
sector concentration, and an LLM explains each finding in plain English, but it can only use numbers
my engine calculated: I validate every number it writes and fall back to a template if it fails.
It's FastAPI, PostgreSQL, Redis workers and React, with 75 tests and CI, deployed on AWS."

## 2. Walk through the code in this order

| Step | File | What to understand |
| --- | --- | --- |
| 1 | `backend/app/analytics/xirr.py` | NPV equation, sign conventions, root finding, ambiguous roots |
| 2 | `backend/app/analytics/holdings.py` | Average-cost method, which flows are external, switches |
| 3 | `backend/app/analytics/series.py` | Daily value, cash flows, time-weighted returns |
| 4 | `backend/app/analytics/risk.py` | Volatility, drawdown, beta, VaR |
| 5 | `backend/app/analytics/exposure.py` | Look-through, coverage, overlap, HHI |
| 6 | `backend/app/reports/engine.py` | How everything combines into one report |
| 7 | `backend/app/insights/` | Rules, templates, LLM adapter, validation |
| 8 | `backend/app/portfolio/parsers/` | Adapter pattern; CAS mapping; stamp duty |
| 9 | `backend/app/portfolio/ingest.py` | Idempotency, matching, reconciliation |
| 10 | `backend/app/portfolio/router.py` | Ownership checks, upload validation, consent |
| 11 | `backend/app/jobs/queue.py` | Background jobs; why the password goes to Redis with a TTL |
| 12 | `backend/tests/` | What each test proves |

## 3. Finance concepts

**XIRR (money-weighted return).** The annual rate `r` that makes the present value of all dated cash
flows zero: `Σ Cᵢ / (1 + r)^((dᵢ − d₀)/365) = 0`. Investments are negative, money received and the
final value are positive. It answers: "what return did *this investor* actually earn, given when they
put money in?"

**Time-weighted return (TWR).** Chains daily returns that exclude cash flows:
`Rₜ = (Vₜ − Fₜ) / Vₜ₋₁ − 1`. It answers: "how did the *investments* perform, regardless of when money
was added?" Fund managers and benchmarks are compared on TWR. In the demo, XIRR (13.1%) and TWR (11.9%)
differ because SIP timing helped.

**CAGR.** `(end / start)^(1/years) − 1`. Only valid with no money added or withdrawn in between.

**Volatility.** Standard deviation of daily returns × √252 (trading days a year).

**Maximum drawdown.** Largest fall from a peak: `min(Vₜ / max(V up to t) − 1)`. I compute it on the
time-weighted wealth index, because raw value rises with every SIP and would hide real losses.

**Beta.** `Cov(Rp, Rm) / Var(Rm)`. Beta 0.7 means the portfolio historically moved about 70% as much as
the market.

**Value at Risk (95%, 1-day, historical).** The 5th percentile of past daily returns × current value.
"On about 1 day in 20, losses exceeded ₹X." It is not the worst case.

**Look-through.** A fund is a basket of stocks. Exposure to stock s =
Σ (value in fund f × weight of s in f) + direct holding of s.

**Fund overlap.** `Σ min(weight in A, weight in B)` over shared stocks. 81% means the two funds are
mostly the same portfolio.

**HHI (Herfindahl).** Σ weight². 1/HHI is the "effective number of holdings".

**CAS.** Consolidated Account Statement from CAMS/KFintech: every mutual fund transaction across fund
houses for an investor, in a password-protected PDF (password usually the PAN).

**Total Return Index (TRI).** An index that assumes dividends are reinvested. The fair benchmark for
mutual funds, which reinvest dividends internally.

## 4. Engineering concepts

- **Modular monolith:** one deployable app with separate domain modules. Simpler than microservices,
  and modules can be split out later if needed.
- **Pure core, imperative shell:** the analytics engine has no I/O, so it is easy to test, and the
  same code serves the API, the worker and the demo.
- **Ledger as source of truth:** holdings are derived, never stored, so they cannot drift.
- **Idempotency:** a deterministic `source_ref` per row plus a unique constraint make retries safe.
- **Adapter pattern:** parsers return a neutral `ParsedStatement`; storage is `put/get/delete` with
  local and S3 versions; the LLM is one function per provider.
- **Async processing:** the API returns 202 and a worker does slow parsing; the UI polls.
- **Defence in depth:** ownership checks, 404 for others' data, rate limiting, upload validation,
  file deletion, audit log, CSP headers, secrets in SSM, an IAM role instead of keys, a private RDS.
- **Responsible AI:** the LLM only explains; numbers are validated; trade advice is rejected; there is
  a deterministic fallback; no PII is sent; uploaded text is treated as data, not instructions.

## 5. Likely interview questions

**Q: Why XIRR and not simple return?**
Simple return ignores timing. ₹1 lakh invested five years ago and ₹1 lakh invested last month are
treated the same. XIRR discounts each flow by its date.

**Q: How do you solve XIRR?**
There's no closed form. I evaluate NPV on a grid of rates to find sign changes, solve each bracket with
Brent's method (guaranteed to converge inside a bracket), then polish with Newton. If there are two
different roots I raise an error instead of picking one.

**Q: When can XIRR have multiple answers?**
When cash flows change sign more than once, e.g. invest, withdraw, invest again. -100, +230, -132 has
roots at 10% and 20%. I have a test for exactly that.

**Q: How do you know your numbers are right?**
Reference tests: Microsoft's documented XIRR example (37.336%) to 6 decimal places, an independent
bisection solver for SIP cases, hand-computed cases for drawdown, beta and VaR, and an integration test
that the database pipeline matches the pure engine within ₹1. Plus CAS reconciliation against the
statement's own closing units.

**Q: Why is there no holdings table?**
Holdings are a function of the ledger. Storing them creates two sources of truth that can disagree.
Recomputing is cheap at this scale; if it ever wasn't, I'd add a cache that is rebuilt from the
ledger, never edited directly.

**Q: What happens if a background job runs twice?**
Each transaction gets a SHA-256 `source_ref` from its content plus an occurrence counter, with a
unique constraint on (portfolio, source_ref). The insert uses `ON CONFLICT DO NOTHING`, so the second
run inserts zero rows. The same holds for re-uploading the same statement; there's a test for it.

**Q: How do you stop the LLM from hallucinating numbers?**
It never calculates. It receives structured findings, must return JSON, and every number in its text
must match a value in that finding's evidence (as a fraction or a percentage, within rounding). Text
telling someone to buy or sell is rejected. Anything that fails uses a deterministic template, and the
product works with no LLM at all.

**Q: How do you secure multi-user data?**
Every private route loads the resource and checks `owner_id == current_user.id`; otherwise it returns
404 so ids can't be probed. Tests log in as two users and confirm one can't read, list or delete the
other's data.

**Q: Why is the CAS password not stored?**
It's a credential (often the PAN). It goes into Redis with a 10-minute TTL, the worker reads it once
with GETDEL, and it's never in the database, the job arguments or the logs.

**Q: How would you scale this?**
The API is stateless, so run more API containers behind a load balancer; move rate limiting to Redis;
add workers for parsing; use RDS read replicas for reports; cache snapshots (already immutable);
partition the prices table by date if it grows large.

**Q: Why RQ and not Celery or Kafka?**
RQ with Redis is simple and enough for a job queue at this scale. Kafka is for event streaming with
replay and many consumers, which this product doesn't need yet.

**Q: What would you build next?**
Automatic corporate-action adjustments, NSDL/CDSL CAS support, a blended benchmark matching the
equity/debt mix, then goal planning with Monte Carlo simulation.

**Q: What was the hardest bug?**
The demo portfolio gave different numbers in different processes. The cause: I iterated over a Python
`set` of sector names to draw random numbers, and set order of strings changes per process because of
hash randomisation. Fix: sort before iterating. I added a test that runs the demo in two processes
with different `PYTHONHASHSEED` values and requires identical results.

**Q: Did you use AI to build it?**
Answer honestly: yes, as a coding assistant, the same way many engineers do now. Then show that you
own it: explain the design decisions, the trade-offs and the tests above in your own words.

## 6. System design talking points (AWS)

- EC2 in a public subnet; RDS in private subnets reachable only from the EC2 security group.
- S3 bucket: public access blocked, SSE, lifecycle deletion after 1 day.
- IAM role on EC2: least-privilege access to one S3 prefix, SSM parameters and CloudWatch Logs.
- Secrets in SSM Parameter Store as SecureString, fetched at deploy time into a 600-permission file.
- HTTPS through Caddy with automatic certificates; HSTS header.
- Next step for availability: an ALB with two instances in two AZs, RDS Multi-AZ, and ElastiCache.

## 7. Frontend design: the "terminal" theme (v1.2)

- **Why a terminal look:** the users are advisors who live in Kite, Bloomberg-style screens and Excel. A dark
  quote-screen layout says "finance" in one glance and fits dense numbers.
- **Design tokens:** every colour, radius and shadow is a CSS variable in `frontend/src/index.css` (exposed to
  Tailwind via `@theme`). Gold `#f0b429` is the brand and the action colour; green/red are *only* used for
  gains and losses, so colour always carries meaning.
- **Monospace numbers:** the `.tabular` class switches figures to JetBrains Mono with tabular digits, so
  columns of rupees line up like a quote screen. Fonts are self-hosted, so the strict CSP still holds.
- **Ticker tape:** `GET /api/v1/market/ticker` (in `app/market_data/router.py`) returns the latest two closes
  per instrument using a SQL window function (`row_number() over (partition by instrument order by date desc)`).
  The change shown is a real day-on-day move from the prices table, and the UI labels it DEMO DATA when the
  source is synthetic. Two integration tests cover it.
- **Quote strip:** each report opens like a stock quote: value, gain, then XIRR / TWR / benchmark / volatility /
  drawdown / beta / flags in one row.
- **Holdings heatmap:** a treemap where box size = value and colour = return on cost (red below zero, green above).
- **Monthly candles:** each candle is one month of the time-weighted growth index (open = previous month's close,
  high, low, close). It is built from the engine's series; the browser only groups points by month.
- **Command palette (Ctrl/⌘ + K):** jump to any client or page from the keyboard, like a terminal command line.
- **Status bar:** API health (CONNECTED/OFFLINE, checked every 30 s) and an IST clock.
- **Bug fixes found while testing:** switching clients kept the old tab (fixed with `key={id}`); cards in a CSS
  grid overflowed on phones because grid items default to `min-width: auto` (fixed with `min-w-0`).
- **Bug found by browser QA (Chrome 155):** every page change crashed with "n is not a function". The cause was
  `useEffect(() => window.scrollTo(0, 0), [path])`: an arrow without braces returns its value, newer Chrome's
  `scrollTo` returns a Promise, and React treats an effect's return value as its cleanup function, so it tried
  to call the Promise. Fix: `useEffect(() => { window.scrollTo(0, 0); }, [path])`. Lesson: effects should only
  ever return a cleanup function or nothing. There is no automated browser test for this
  yet; adding a Playwright test that fakes a Promise-returning `scrollTo` would stop it coming back.
- **Export PDF:** print CSS swaps the dark tokens for a light, paper-friendly palette and hides the chrome.


## V1.1: from numbers to advice (engine 1.1.0)

**The problem:** V1 showed correct numbers, but an advisor still had to work out *why* and *what to do*. V1.1 adds
that layer without giving up the rule "verified calculations first, AI explanations third".

- **What helped and what held it back** (`app/analytics/attribution.py`): profit per holding =
  value today + money taken out − money put in. Sold holdings are included, so the profits add up exactly
  to the portfolio's total profit (a unit test checks this). *Interview point:* this is lifetime profit, not
  "unrealised gain", which ignores money already taken out.
- **Fair comparison with the index (PME):** for each equity holding we replay its own purchases and sales
  into the index on the same dates and compare the two XIRRs. Comparing a fund's XIRR with the index's
  time-weighted return would be apples vs oranges; this is like-for-like. The method is called the
  *public market equivalent* (Long–Nickels).
- **Tax estimate** (`app/analytics/tax.py`): FIFO lots (oldest units sold first, as Indian tax rules do),
  equity rules for FY 2026-27: 20% short-term (≤ 12 months), 12.5% long-term above ₹1.25 lakh a year. Two
  numbers are shown because we cannot know whether the client already used the exemption. For debt and gold
  we show only the gain: guessing a slab rate would be a made-up number.
- **Options to discuss** (`app/insights/actions.py`): each flag gets 2–3 concrete options with the money
  involved, the result and the trade-offs, e.g. "Combine into the fund with the higher return since
  purchase". Calculated, not written by the LLM. Worded as options for the advisor, because the advisor is the
  one licensed to recommend.
- **Plain-English summary** (`app/insights/summary.py`): a template builds 4–5 sentences from the numbers. If
  an LLM is configured, it may rewrite them, but its text must pass the *same* number validator as findings
  (`explain_summary` in `llm.py`). A unit test proves the template itself passes the validator.
- **Why bump `CALC_VERSION` to 1.1.0:** new formulas. Old saved reports lack the new fields; the UI shows an
  "Update report" button instead of crashing.

### Frontend (v1.3 design)

- **Light theme by default**, dark optional (toggle in the sidebar). Still one token file: the dark theme is
  just a second set of values under `:root[data-theme="dark"]`, so the two cannot drift apart.
- **Plain words:** "Annual return (XIRR)" instead of "XIRR", "Worst fall" instead of "Max DD", with a `?`
  (`Help` component) that explains each term. Ticker tape, status bar, candles and terminal codes are gone:
  they looked impressive but did not help an advisor.
- **Guided steps** (`Stepper`): Add a statement → Check the import → Review the report → Share with the client.
- **Summary tab first**, then "To discuss" with options; the advisor ticks "Add to client report".
- **Client report** (`/app/p/:id/share`): a printable page in simple language with only the ticked options, and
  an editable email draft. The ticks are stored in the browser (`lib/plan.ts`) because they are a working
  choice, not part of the calculated report.
- **QA fixes:** card titles no longer cut off ("ASSET CL…"), the gain column no longer wraps, the review-limit
  line on flags is labelled, and the PDF password box no longer shows a value-like placeholder.


## V1.2: risk profiling and goal planning (engine 1.2.0)

**Why:** analysis alone can't tell whether a portfolio is *right for this client*. Wealth management
needs two more inputs, the client's risk profile and their goals. With them, FolioLens moves from
"portfolio analytics" to an advisory workflow.

- **Risk profile** (`app/analytics/planning.py`): six questions, each answered 0–4. Score = average ÷ 4 ×
  100 → one of five profiles with an equity range (Conservative 10–30% … Aggressive 70–90%). Simple and
  transparent on purpose; real advisers also use their firm's own process (SEBI requires risk profiling
  for RIAs).
- **Suitability:** equity share = equity + ½ × hybrid. Outside the range → a `risk_mismatch` flag with a
  rebalance option: amount to move = (equity share − edge) × portfolio value.
- **Tax-aware rebalancing:** the holdings to sell are picked in order of *smallest gain per rupee*, so the
  same amount of money moves with the least capital-gains tax. `tax.combine()` merges several sales and
  applies the ₹1.25 lakh exemption once. *Interview point:* this is what "tax-loss/tax-aware
  rebalancing" means in wealth management.
- **Goal projection:** target then = target today × (1 + inflation)^years; projected = set-aside ×
  (1 + r)^years + SIP × annuity-due factor with a monthly rate (1 + r)^(1/12) − 1; r comes from the
  portfolio's own asset mix. Funded ratio ≥ 100% on track, 80–100% slightly short, < 80% not on track.
- **What to do if a goal is short:** the SIP that exactly closes the gap (a unit test proves it lands on
  100%), the earliest date that works with the current SIP, the reachable target in today's rupees,
  and the one-time amount needed now.
- **Near goals in equity:** a goal under 3 years away whose money sits in a mostly-equity portfolio is
  flagged, with an option to move that money to safer funds (tax-aware), or gradually over 12 months.
- **Storage:** one `client_plans` row per portfolio (answers + goals as JSON, validated by Pydantic).
  Migration `0002`. The planning router is mounted before the portfolio router, because
  `/portfolios/{id}/plan` would otherwise be caught by `/portfolios/{id}/{section}`.
- **Assumptions are shown, not hidden:** expected returns (equity 11%, hybrid 9%, debt 7%, gold 7%, cash 5%)
  and 6% inflation appear next to every projection and in the client report.
