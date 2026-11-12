# Measured results

Measured on 12 Nov 2026 with engine 1.2.0, on a 2-core Intel Xeon 2.1 GHz cloud machine with
PostgreSQL 16. AI explanations were switched off (templates), so the times exclude LLM latency.
Rerun with the scripts in `backend/benchmarks/`.

| What | Result | How |
| --- | --- | --- |
| XIRR vs Excel | Microsoft's documented XIRR example (37.3362535%) matched to 0.00000015 percentage points | `tests/unit/test_xirr.py` |
| XIRR vs spreadsheet | 500 of 500 random portfolios (30,334 cash flows) matched LibreOffice Calc's XIRR(); largest difference 5.3 × 10⁻¹³ percentage points | `benchmarks/xirr_vs_spreadsheet.py` |
| Engine robustness | 200 of 200 random portfolios (2–12 holdings, SIPs, lump sums, partial sales, random risk profiles and goals) built with every invariant holding: values and weights reconcile, profits add up to total profit, every flag has options | `benchmarks/engine_and_validator.py` |
| Engine time | median 0.06 s, slowest 0.15 s per report (about 3.5 years of daily data) | same |
| Full report refresh | median 0.28 s (load from database + engine + save), sample client, 10 runs | API timing |
| Statement to report | median 0.82 s: CAS PDF upload, parse, match and reconcile 0.58 s, then build and save 0.25 s (synthetic CAS, 6 schemes, 5 runs) | API timing |
| AI-number validator | caught 9,069 of 9,093 injected errors (99.7%) across 1,548 correct explanations; 0 correct texts rejected | `benchmarks/engine_and_validator.py` |
| Validator, by error | invented figure 100% · invented date 100% · trade instruction 100% · fraction written as percent 100% · number × 10: 99.2% · one digit changed: 99.2% | same |
| Bug found by the benchmark | 90 of 1,548 correct texts (5.8%) were wrongly rejected when they described a loss or negative return; fixed (`validation.py`) with a regression test | `tests/unit/test_validation_negatives.py` |
| Analytics computed | 41 metrics and 9 review rules (list below) | report JSON |

The 24 missed errors (0.3%) are changes that turned one figure into another figure that is also in
the evidence (for example 10.0% → 10.3% when 10.3% is a real fact elsewhere). The validator checks
that every number exists in the evidence, not which claim it belongs to.

**Not yet measured:** a live LLM's own error rate (needs an API key), and real client CAS statements
(only synthetic statements so far).

## The 41 metrics

- **Returns (8):** current value, cost, unrealised gain, net invested, total profit, XIRR,
  time-weighted return, benchmark return.
- **Per holding (6):** weight, XIRR, lifetime profit, share of profit, index-equivalent XIRR (PME),
  gap vs index.
- **Exposure (7):** asset allocation, sector exposure after look-through, market-cap split, company
  exposure (direct + through funds), look-through coverage, fund overlap, liquid share.
- **Risk (8):** volatility, maximum drawdown, beta, historical VaR, parametric VaR, HHI, effective
  holdings, company-level HHI.
- **Planning (9):** risk score, equity share vs range, expected return of the mix,
  inflation-adjusted target, projected value, funded ratio, SIP needed, years to reach, one-time
  amount needed.
- **Tax (3):** short-term gain (FIFO), long-term gain, estimated tax (exemption unused and used).
