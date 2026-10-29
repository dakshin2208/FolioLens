# Resume, LinkedIn and referral material

Only claim what is true at that moment. Replace the `[ ]` placeholders once the app is live; until
then, say "AWS deployment design" rather than "deployed on AWS".

## Resume project entry

**FolioLens: Wealth Management Platform for Indian Financial Advisors** · [Live demo] · [GitHub]
*Python, FastAPI, PostgreSQL, Redis, React, TypeScript, Docker, LLM APIs, AWS*

- Built a full-stack wealth management platform that turns a client's CAMS/KFintech CAS statement into
  a complete advisory review: portfolio analytics, risk profiling, goal planning, tax-aware
  recommendations and a client-ready report.
- Implemented a pure-Python analytics engine for XIRR (verified against Excel), time-weighted return,
  volatility, drawdown, beta, VaR, mutual fund look-through and fund overlap, with every report
  versioned so past results stay explainable.
- Added client risk profiling (6-question model, 5 profiles with equity ranges) and a suitability check
  that flags portfolios outside the client's range and computes a tax-aware rebalance, selling the
  lowest-gain holdings first.
- Built goal-based planning: inflation-adjusted targets, projections from the portfolio's asset mix,
  funded ratio, and the SIP, date change or lump sum needed to put each goal back on track.
- Added performance attribution (public market equivalent vs the index) and FIFO capital-gains tax
  estimates under FY 2026-27 rules for every suggested action.
- Designed grounded AI explanations: the LLM only rewords calculated facts, a validator rejects any
  number not in the data, and templates are the fallback.
- Secured client data with JWT auth, per-advisor isolation (404 on other users' data), consent capture,
  audit logging and statements deleted after parsing; 110 automated tests, CI, Docker and an AWS
  deployment design (EC2, RDS, S3).

Shorter version (when space is tight):

- **FolioLens** (FastAPI, PostgreSQL, React, LLM APIs): wealth management platform for Indian advisors.
  It covers portfolio analytics (XIRR verified against Excel, look-through, overlap, risk), client risk
  profiling and goal planning, and tax-aware rebalancing options. AI explanations are validated against
  computed numbers, and it produces client-ready reports. 110 tests, CI, Docker. [Demo] · [Code]

## Skills line

Python, SQL, TypeScript · FastAPI, React, SQLAlchemy, pandas, NumPy, SciPy · PostgreSQL, Redis ·
Docker, GitHub Actions · AWS (EC2, RDS, S3, IAM, SSM) · LLM integration (Anthropic, OpenAI) ·
Wealth management: portfolio analytics (XIRR, TWR, VaR, beta, drawdown), risk profiling and
suitability, goal-based planning, performance attribution, Indian capital-gains tax

## What to say if asked "is it a full wealth management platform?"

"It covers the advisory side end to end: reading the client's statement, analysing the portfolio, risk
profiling, goal planning, tax-aware recommendations and the client report. It doesn't place trades or
run a CRM. Those are execution and back-office tools, and the advisor keeps using their existing
platform for them."

## 30-second pitch

"I built FolioLens, a wealth management platform for Indian financial advisors. The advisor uploads a
client's mutual fund statement and answers six risk questions, then adds the client's goals. FolioLens
calculates the real return and finds hidden risks such as overlapping funds. It checks whether the
portfolio fits the client's risk profile and whether each goal is on track. For every problem it
suggests options with the money involved and the capital-gains tax, and it produces a report the
client can read. The AI only rewords numbers my engine has verified, so it can't invent anything."

## Interview deep-dives (have one ready)

1. **XIRR for SIP histories:** irregular dates, partial sales and switches; root bracketing plus
   Brent's method; it reports when two rates fit instead of picking one.
2. **Fair benchmark comparison:** the public market equivalent method replays a fund's own cash flows
   into the index.
3. **Goal maths:** target × (1 + inflation)^years against set-aside × (1 + r)^years + SIP × an annuity
   factor; then solving for the SIP needed or the date that works.
4. **Tax-aware rebalancing:** FIFO lots, short- and long-term gains, the ₹1.25 lakh exemption used
   once across several sales, and selling the lowest-gain holdings first.
5. **Grounded AI:** the model gets pre-formatted facts, every number is validated, it gets one retry,
   and a template is the fallback.

## Referral message (LinkedIn, under 300 characters for a connection note)

> Hi [Name], I'm a [year] BTech student applying for [role, job ID] at [company]. I built FolioLens,
> a wealth management platform for Indian advisors (FastAPI, React, LLMs). 2-min demo: [link].
> Would you be open to referring me?

## Referral message (follow-up after they accept)

> Thanks for connecting, [Name]. I'm applying for [role] ([job ID]) at [company].
>
> I recently built FolioLens, a wealth management platform for financial advisors. It reads a
> client's mutual fund statement, checks the portfolio against their risk profile and goals, and
> suggests tax-aware changes with a client-ready report. I verified the return calculations against
> Excel and designed the AI layer so it can't invent numbers.
>
> Demo (no sign-in): [link] · Code: [GitHub] · Resume: [link]
>
> If you think I'd be a fit, I'd be grateful for a referral. Happy to answer any questions.

## LinkedIn post (after launch)

> I built FolioLens: a wealth management platform for Indian financial advisors.
>
> Upload a client's CAS statement, answer six risk questions, add their goals, and it shows:
> • real returns (XIRR, verified against Excel) and what helped or hurt them
> • hidden risks: overlapping funds, too much in one stock or sector
> • whether the portfolio fits the client's risk profile
> • whether each goal (education, home, retirement) is on track, and the SIP needed if not
> • options for every issue, with the estimated capital-gains tax
>
> The part I'm proudest of: the AI explanations can't invent numbers. Every figure is checked
> against the calculation engine, with a fallback when it fails.
>
> Stack: FastAPI, PostgreSQL, Redis, React, Docker, LLM APIs.
> Demo: [link] · Code: [link]
