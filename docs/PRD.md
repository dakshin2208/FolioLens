# FolioLens — Product Requirements Document v1.1

Advisor-focused portfolio analytics for India · 13 October 2026

| Version | Changes |
| --- | --- |
| 1.0 | Initial PRD |
| 1.1 | CAS closing-unit reconciliation; casparser behind a parser adapter; blended-benchmark caveat; decisions-log fixes; renamed to FolioLens |

# 1. Executive summary

FolioLens (formerly Portfolio X-Ray) is a web application for Indian financial advisors that
turns supported investment statements into a review-ready portfolio
analysis. It ingests mutual fund CAS PDFs and a limited set of broker
CSV exports, normalizes transactions, reconstructs holdings, calculates
returns and selected risk metrics, detects concentration and fund
overlap, and produces evidence-backed explanations.

Product principle: verified financial calculations first, transparent
evidence second, AI explanations third.

V1 is a focused engineering project, not a full wealth-management suite.
The primary differentiator to validate is the quality of look-through
exposure, overlap, risk analysis, data-quality transparency and
evidence-backed findings—not basic portfolio tracking.

# 2. Target user and workflow

Primary user: an independent financial advisor or mutual fund
distributor preparing a portfolio review. For V1, each client is
represented by one portfolio owned by the advisor's account; a
client-name field is displayed in the UI. Full CRM, multi-staff
permissions and organization management are out of scope.

1.  Open demo or sign in.

2.  Create a client portfolio and enter a client label/name.

3.  Confirm that the advisor has appropriate client consent to process
    the uploaded information.

4.  Upload a supported CAS PDF or broker CSV.

5.  Review parsed transactions and unmatched instruments; correct
    mappings and resolve warnings.

6.  Run analytics using documented price, benchmark and constituent
    data.

7.  Inspect overview, allocation, performance, risk and evidence-backed
    findings.

8.  Export a PDF report if time permits; otherwise provide an in-app
    review-ready report.

# 3. V1 scope and cut line

## Must ship

- Synthetic demo mode with no login.

- CSV import and one supported CAS PDF path (CAMS/KFintech detailed CAS
  where feasible).

- Import review screen with instrument mapping corrections and clear
  errors.

- Portfolio valuation and holdings reconstruction.

- XIRR, asset allocation and supported fund look-through.

- Historical volatility and maximum drawdown where data coverage is
  adequate.

- Rule-based findings and AI explanations grounded in calculated
  evidence, with deterministic fallback.

- A deployed application and reproducible README/demo.

## Stretch goals

- Beta and Value at Risk (VaR), including parametric VaR.

- PDF export.

- Additional broker CSV formats beyond the first selected broker.

- More advanced report customization.

## Explicitly out of scope

- Live broker or bank connections; trade execution; buy/sell
  recommendations.

- Tax filing, goal planning, retirement modelling, broad financial
  copilot and full advisor CRM.

- Multi-advisor organizations, staff management, subscription billing
  and mobile apps.

- Comprehensive support for every asset class or every statement format.

# 4. Product screens

| **Screen**                | **Required behavior**                                                                                            |
|---------------------------|------------------------------------------------------------------------------------------------------------------|
| **Landing/demo**          | Product promise, Try Demo and Upload actions; synthetic demo requires no login.                                  |
| **Client portfolios**     | List/create portfolios; include a client-name/label field. Do not imply full CRM functionality.                  |
| **Import & review**       | Upload progress, parsed transactions, unmatched instruments, validation warnings and manual mapping corrections. |
| **Overview**              | Portfolio value, invested amount where meaningful, XIRR, valuation date, key findings and data coverage.         |
| **Allocation & holdings** | Asset allocation, market-cap/sector exposure, top underlying companies and supported fund overlap.               |
| **Performance & risk**    | Performance series, XIRR, volatility and drawdown; beta/VaR only if stretch scope is achieved.                   |
| **Findings**              | Severity, evidence, source date, calculation method, limitation and advisor discussion prompts.                  |
| **Settings/privacy**      | Account controls, data deletion and privacy/consent information.                                                 |

# 5. Data sources and initial coverage

Initial candidates (availability, licensing/terms, redistribution rights
and operational reliability must be checked before use):

- Mutual fund NAV: AMFI daily NAV file.

- Equity prices: an appropriate NSE daily market-data source, such as
  the relevant bhavcopy product, subject to its current terms.

- Benchmark: Nifty 50 Total Return Index (TRI) history, using an
  authorized/appropriate source.

- Fund constituents: AMC monthly portfolio disclosures for an initial
  list of roughly 20–30 commonly held funds.

- Broker data: one broker's holdings and tradebook CSV; Zerodha Console
  is a candidate, subject to confirming the actual export formats.

Do not assume that a public download automatically permits commercial
redistribution. Record source, date, terms and update process for each
dataset. If a source is unavailable or not permitted, document an
alternative before implementation.

# 6. Data normalization and calculation conventions

| **Topic**                    | **Decision / convention**                                                                                                                                                                                                    |
|------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Pricing date**             | Use the latest eligible NAV/price on or before the selected valuation date; display the actual as-of date.                                                                                                                   |
| **XIRR cash flows**          | Investments are negative cash flows and ending portfolio value is positive; use Actual/365 day count.                                                                                                                        |
| **Dividends**                | Dividend payout is an investment cash inflow for performance calculations; dividend reinvestment is represented as a purchase plus appropriate dividend treatment. Document the chosen convention and avoid double counting. |
| **Switches**                 | Represent a mutual fund switch as a linked sell and buy, preserving the economic cash-flow treatment and source references.                                                                                                  |
| **Charges**                  | Stamp duty and STT remain reflected in transaction amounts according to the selected source format; document whether each import amount is gross or net.                                                                     |
| **Corporate actions**        | Use a small, versioned manual table for stock splits and bonus issues in V1; record source and effective date.                                                                                                               |
| **Instrument matching**      | Exact supported identifier/ISIN match may auto-match. Name similarity \>= 0.90 is a suggestion only. Lower-confidence or ambiguous matches require user review.                                                              |
| **Look-through coverage**    | Display look-through only when at least 80% of fund value has constituent data no older than three months; disclose coverage and exclusions.                                                                                 |
| **Historical risk coverage** | Require at least one year of usable daily data for volatility, drawdown and beta; if the calculation method needs more observations, say so and suppress the metric.                                                         |
| **Missing data**             | Never silently replace missing prices, transactions or constituents with zero. Mark metrics incomplete or unavailable when necessary.                                                                                        |

# 7. Financial analytics

- Portfolio valuation: quantity × eligible price/NAV, with a visible
  valuation timestamp and missing-price warnings.

- XIRR: solve the dated cash-flow NPV equation; validate input signs and
  dates, handle non-convergence and ambiguous/multiple roots explicitly.

- Allocation: calculate weights from supported asset values; distinguish
  direct exposure from look-through exposure.

- Look-through: combine fund weight × constituent weight with direct
  holdings, avoiding double-counting.

- Overlap: use a documented formula over compatible dated constituent
  weights and identify the compared funds and data date.

- Volatility: standard deviation of periodic returns with documented
  annualization convention.

- Maximum drawdown: largest fall from a running peak to a subsequent
  trough over the selected interval.

- Beta/VaR: stretch goals only; document benchmark alignment,
  observation count, confidence level, horizon and methodology.

- Benchmark comparison: use Nifty 50 TRI only where appropriate, with
  aligned dates and clearly explained return methodology.

# 8. Rules and AI explanations

The rules engine detects configured conditions, for example:

- A single stock exceeds a configured portfolio-weight threshold.

- A sector exceeds a configured share of equity exposure.

- Two funds have high overlap based on available constituent data.

- Cash/liquid allocation is below a configured threshold.

- Historical performance trails a compatible benchmark by a configured
  amount over a specified period.

Each finding must include a type, severity, measured value, threshold
where applicable, supporting instruments, data date, calculation version
and limitations. Thresholds are review flags, not personalized
investment advice.

The LLM may explain structured findings in plain English. It must not
calculate metrics, invent missing values or recommend specific
securities to buy or sell. Validate numeric claims against the input
findings; if validation fails or the provider is unavailable, use a
deterministic template. Minimize personal data in model requests.

# 9. Proposed architecture

- Frontend: React, TypeScript, Vite, Tailwind CSS and Recharts.

- API/backend: Python 3.12, FastAPI, Pydantic, SQLAlchemy and Alembic.

- Database: PostgreSQL.

- Background jobs: Redis + RQ for initial simplicity; jobs must be
  idempotent and retry-safe.

- Analytics: pandas, NumPy and SciPy, isolated from API, UI and LLM
  code.

- Parsing: pdfplumber for supported PDF layouts plus format-specific CSV
  parsers.

- AI: provider adapter with structured JSON output and deterministic
  fallback.

- Deployment: one EC2 instance running Docker Compose, managed
  PostgreSQL/RDS if budget permits, and private S3 storage. Re-evaluate
  ECS only if scale or operations justify it.

- Quality: pytest, coverage, Ruff, mypy, integration tests and CI.

# 10. Data model and API

Core tables: users, portfolios (with client_name/label), uploads,
instruments, transactions, holdings, prices, fund_constituents, sectors,
analytics_snapshots, calculation_runs and audit_logs. Add consent
records or equivalent auditable consent metadata for the upload
workflow. Transactions remain the source of truth; holdings are derived.

Proposed API base path: /api/v1

- POST /auth/register and /auth/login

- POST /portfolios; GET /portfolios

- POST /portfolios/{id}/uploads

- GET /uploads/{id}; POST /uploads/{id}/review

- GET /portfolios/{id}/holdings

- GET /portfolios/{id}/allocation

- GET /portfolios/{id}/performance

- GET /portfolios/{id}/risk

- GET /portfolios/{id}/insights

- GET /demo/report

All endpoints require explicit authentication/authorization behavior,
typed schemas, validation, pagination where appropriate and consistent
error responses. Every private query must be scoped to the authenticated
user's permitted resources.

# 11. Privacy, consent and security

- Before processing a client's statement, require the advisor to confirm
  they have appropriate authority/consent to upload and process it;
  record timestamp, user, portfolio and consent-text version.

- The consent checkbox is a product control, not a substitute for legal
  review of the advisor's obligations under applicable Indian
  data-protection law.

- Encrypt data in transit and at rest; keep storage private and secrets
  outside source code.

- Delete raw files after successful parsing according to the selected
  policy; delete failed uploads after 24 hours unless needed for a
  user-requested retry or documented operational reason.

- Keep extracted financial data until the user requests deletion,
  subject to documented retention and legal obligations.

- Use least privilege, rate limiting, secure password hashing/session
  handling and backend ownership checks.

- Test that one user cannot access another user's portfolios, files,
  reports or job results.

- Treat uploaded documents as untrusted input; protect parsers and AI
  flows against malicious instructions embedded in documents.

- Audit uploads, consent changes, logins, report access and deletions
  without logging unnecessary financial contents.

# 12. Revised delivery plan: vertical slices

| **Week**   | **Milestone**              | **Acceptance focus**                                                                                     |
|------------|----------------------------|----------------------------------------------------------------------------------------------------------|
| **Week 1** | Foundation slice           | Repo, Docker Compose, database, migrations, auth, portfolio creation, CI and synthetic demo data.        |
| **Week 2** | CSV-to-screen slice        | Choose one broker CSV format; upload, parse, review, correct mappings and display holdings in a bare UI. |
| **Week 3** | End-to-end portfolio slice | CSV upload → holdings screen → valuation and allocation; early usable workflow by end of week.           |
| **Week 4** | CAS ingestion              | Implement one supported CAMS/KFintech detailed CAS path; transaction ledger and reconciliation.          |
| **Week 5** | Performance engine         | XIRR, valuation history, reference tests and error handling.                                             |
| **Week 6** | Risk and look-through      | Fund constituents, overlap, volatility, drawdown and data coverage.                                      |
| **Week 7** | Findings and hardening     | Rules, AI explanations/fallback, privacy, authorization and job retry testing.                           |
| **Week 8** | Ship and showcase          | Deploy, run regression tests, documentation, demo video and release checklist.                           |

This schedule is aggressive for a solo developer working 15–20
hours/week. Protect the must-ship cut line. If parsing or data access
consumes more time than expected, cut stretch features rather than
weakening financial correctness or security.

# 13. Acceptance criteria and test plan

- Demo works without login and uses synthetic data.

- A user can upload the selected CSV and supported CAS format and see a
  clear import status.

- A user can correct unmatched instruments and regenerate analytics.

- Holdings reconcile to the transaction ledger for reference portfolios.

- XIRR matches independently checked Excel/reference results within 0.01
  percentage points on the agreed test cases.

- Portfolio values match reference calculations within ₹1 for the agreed
  deterministic fixtures, subject to rounding conventions.

- Ten hand-built reference portfolios cover regular contributions,
  irregular flows, partial sales, dividends, switches, missing prices
  and edge cases.

- Look-through is shown only when the documented coverage threshold is
  met; data date and coverage are visible.

- Volatility/drawdown/beta are suppressed or qualified when historical
  data is insufficient; beta is stretch scope.

- Every finding is traceable to calculations and source data.

- LLM numeric output is validated and fallback works with the LLM
  disabled.

- Cross-user authorization, file retention and deletion tests pass.

- A fresh deployment can be started using documented instructions.

# 14. Decisions log

| **ID**                       | **Decision**      | **Recommended answer**                                                                                                                                                                                                                                                |
|------------------------------|-------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **D-01 Statement formats**   | **CAMS/KFintech** | CAMS/KFintech detailed CAS first where parsing is feasible; one broker's holdings + tradebook CSV (Zerodha Console is a candidate). NSDL/CDSL CAS later.                                                                                                              |
| **D-02 Market data**         | **AMFI**          | AMFI daily NAV file; an appropriate NSE daily-price source; Nifty 50 TRI history; AMC monthly constituent disclosures for an initial set of 20–30 funds. Verify current terms, licensing and availability.                                                            |
| **D-03 Transaction events**  | **Dividend**      | Dividend payout = cash inflow; dividend reinvestment = purchase plus appropriate dividend treatment; switch = linked sell and buy; charges remain reflected according to source amount semantics; stock splits/bonuses via a small versioned manual table.            |
| **D-04 Conventions**         | **Latest**        | Latest eligible price/NAV on or before valuation date; investment outflows negative and ending value positive for XIRR; Actual/365.                                                                                                                                   |
| **D-05 Minimum coverage**    | **Require**       | Require at least one year of daily observations for initial volatility/drawdown/beta policy; show look-through only if at least 80% of fund value has constituents no older than three months. Suppress or qualify results when method-specific data is insufficient. |
| **D-06 Instrument matching** | **Exact**         | Exact supported identifier/ISIN match may auto-match; name similarity \>= 0.90 suggests a match but does not silently finalize it; ambiguous mappings require review.                                                                                                 |
| **D-07 Job framework**       | **RQ**            | RQ + Redis for initial scale, with idempotent jobs and retry-safe processing.                                                                                                                                                                                         |
| **D-08 AWS setup**           | **One**           | One EC2 instance running Docker Compose; private S3; managed PostgreSQL/RDS if budget permits. Verify current pricing and free-tier eligibility; move to ECS only when justified.                                                                                     |
| **D-09 Retention**           | **Delete**        | Delete raw file after successful parse; delete failed uploads after 24 hours subject to retry/support policy; retain extracted data until user deletion subject to documented obligations.                                                                            |
| **D-10 Correctness**         | **XIRR**          | XIRR within 0.01 percentage points of Excel/reference calculations; values within ₹1 on deterministic fixtures; ten hand-built reference portfolios.                                                                                                                  |
| **D-11 First demo**          | **Demo**          | Demo mode + CSV upload + overview + allocation + XIRR. The end-of-week-3 slice should already show uploaded CSV holdings on screen.                                                                                                                                   |
| **D-12 Advisor validation**  | **Interview**     | Interview five mutual fund distributors and SEBI-registered investment advisers (RIAs). Ask them to demonstrate current tools and identify the most time-consuming review steps.                                                                                      |

# 15. Advisor discovery interview guide

9.  Which software do you use today for portfolio reviews, valuation and
    client reporting?

10. Please walk through the last portfolio review you prepared. What
    files did you receive and what steps did you take?

11. Which task took the longest? How long did it take for a typical
    client?

12. How do you identify overlapping mutual fund holdings and sector
    concentration today?

13. Which errors, missing data or reconciliation problems create the
    most rework?

14. How do you verify the accuracy of return and risk calculations?

15. Would evidence-linked findings and visible data-quality warnings
    change your workflow? Why or why not?

16. What would you need to see before trusting a new tool with client
    statements?

17. Would you pay for this, replace an existing tool, or use it
    alongside existing software? What would justify the cost?

# 16. Solo developer operating plan

Although this is written as a team handoff, V1 is scoped for a solo
developer. Keep a decisions log, implement one vertical slice at a time,
and do not start a new feature until the current slice works end to end.
Prioritize the correctness harness and synthetic demo early. Use advisor
interviews to validate the product thesis before investing in a broader
advisor workspace.

# Final product definition

FolioLens (formerly Portfolio X-Ray) is an advisor-focused Indian portfolio analytics tool
that converts supported investment statements into portfolio valuations,
performance measurements, supported look-through exposure, risk analysis
and evidence-backed findings. Its initial competitive hypothesis is that
transparent data-quality handling and review-ready explanations can
improve an advisor's workflow. This hypothesis must be validated through
advisor interviews.

Build principle: verified calculations first. Transparent evidence
second. AI explanations third.


# v1.1 additions (authoritative where they differ from the text above)

- **Parsing:** put format-specific parsers behind an internal adapter. Evaluate the open-source `casparser` library for CAMS/KFintech CAS first: pin the version, verify its license and dependency licenses, run representative password-protected PDFs through reconciliation fixtures, and keep a manual-review fallback. Never couple domain logic to the library's output.
- **CAS reconciliation:** for CAMS/KFintech CAS imports, units rebuilt per scheme from the ledger must match the CAS closing unit balance within a documented tolerance. Any mismatch blocks a clean import and routes the portfolio to review, showing the scheme and the variance.
- **Benchmark:** don't compare debt-heavy portfolios with Nifty 50 TRI alone. A blended benchmark matching the portfolio's equity/debt mix is a stretch item.
