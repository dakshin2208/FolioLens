"""Builds a complete portfolio report from plain inputs.

Pure function: no database, network or LLM. The API, the background worker and the demo
all call `build_report`, so they always produce identical numbers for identical inputs.
"""

from datetime import UTC, date, datetime
from itertools import combinations
from typing import Any

import pandas as pd

from app.analytics import exposure, risk, series
from app.analytics.attribution import contributions
from app.analytics.holdings import build_holdings, holding_cashflows, portfolio_cashflows
from app.analytics.planning import build_planning
from app.analytics.tax import fifo_lots
from app.analytics.types import PortfolioInput
from app.analytics.xirr import XirrError, xirr
from app.config import CALC_VERSION
from app.insights.actions import ActionContext, attach_options
from app.insights.rules import evaluate_rules
from app.insights.summary import build_summary

MAX_PRICE_AGE_DAYS = 7
SERIES_POINTS = 160


def _latest_price(prices: dict[date, float], on_or_before: date) -> tuple[date, float] | None:
    eligible = [d for d in prices if d <= on_or_before]
    if not eligible:
        return None
    d = max(eligible)
    return d, prices[d]


def _base_date(vs: pd.DataFrame, rets: pd.Series) -> pd.Timestamp:
    """The day before the first return: where the wealth index starts at 1.0."""
    pos = vs.index.get_loc(rets.index[0])
    return vs.index[pos - 1] if isinstance(pos, int) and pos > 0 else rets.index[0] - pd.Timedelta(days=1)


def _safe_xirr(flows: list[tuple[date, float]]) -> tuple[float | None, str | None]:
    try:
        return xirr(flows), None
    except XirrError as e:
        return None, str(e)


def build_report(inp: PortfolioInput) -> dict[str, Any]:
    quality: list[dict[str, str]] = []
    txns = inp.transactions
    holdings = build_holdings(txns, inp.valuation_date)

    held_dates = [max(inp.prices[i]) for i in holdings if inp.prices.get(i)]
    valuation_date = inp.valuation_date or (max(held_dates) if held_dates else date.today())

    # ---- Valuation -------------------------------------------------------------------
    values: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    for iid, h in holdings.items():
        info = inp.instruments[iid]
        latest = _latest_price(inp.prices.get(iid, {}), valuation_date)
        if latest is None:
            quality.append(
                {
                    "level": "error",
                    "message": f"No price for {info.name}; it is excluded from the portfolio value.",
                }
            )
            continue
        pdate, price = latest
        age = (valuation_date - pdate).days
        if age > MAX_PRICE_AGE_DAYS:
            quality.append(
                {"level": "warning", "message": f"Price for {info.name} is {age} days old ({pdate})."}
            )
        value = h.units * price
        values[iid] = value
        h_xirr, _ = _safe_xirr(holding_cashflows(txns, iid) + [(valuation_date, value)])
        rows.append(
            {
                "instrument_id": iid,
                "name": info.name,
                "type": info.type,
                "asset_class": info.asset_class,
                "category": info.category,
                "units": h.units,
                "price": price,
                "price_date": pdate.isoformat(),
                "value": value,
                "cost": h.cost,
                "gain": value - h.cost,
                "xirr": h_xirr,
            }
        )
    total = sum(values.values())
    for r in rows:
        r["weight"] = r["value"] / total if total else 0.0
    rows.sort(key=lambda r: -r["value"])

    # Holdings with no usable price are excluded from returns entirely: keeping their purchases
    # while valuing them at zero would understate XIRR (never replace missing data with zero).
    unpriced = set(holdings) - set(values)
    txns = [t for t in txns if t.instrument_id not in unpriced]
    flows = portfolio_cashflows([t for t in txns if t.date <= valuation_date])
    p_xirr, xirr_error = _safe_xirr(flows + [(valuation_date, total)]) if total else (None, "No value")
    if xirr_error:
        quality.append({"level": "warning", "message": f"Portfolio XIRR unavailable: {xirr_error}"})
    cost = sum(r["cost"] for r in rows)
    liquid = sum(
        v
        for i, v in values.items()
        if inp.instruments[i].is_liquid or inp.instruments[i].asset_class == "cash"
    )

    # ---- Allocation and look-through ---------------------------------------------------
    asset = exposure.asset_allocation(values, inp.instruments)
    lt = exposure.look_through(values, inp.instruments, inp.constituents, valuation_date)
    for ex in lt.excluded_funds:
        quality.append({"level": "info", "message": f"Look-through excludes {ex['name']}: {ex['reason']}."})
    if not lt.is_reliable and lt.eligible_fund_value > 0:
        quality.append(
            {
                "level": "warning",
                "message": f"Look-through covers only "
                f"{lt.coverage:.0%} of equity fund value (minimum 80%); sector and "
                "company views are partial.",
            }
        )

    equity_exposure = sum(lt.stock_values.values()) + lt.residual_in_funds
    top_companies = []
    for sid, v in sorted(lt.stock_values.items(), key=lambda kv: -kv[1])[:10]:
        sinfo = inp.instruments.get(sid)
        direct = lt.direct_values.get(sid, 0.0)
        top_companies.append(
            {
                "instrument_id": sid,
                "name": sinfo.name if sinfo else sid,
                "sector": sinfo.sector if sinfo else None,
                "value": v,
                "weight": v / total if total else 0.0,
                "direct_value": direct,
                "via_funds_value": v - direct,
            }
        )
    sector_values = exposure.group_exposure(lt.stock_values, inp.instruments, "sector")
    if lt.residual_in_funds > 0:
        sector_values["Cash & others in funds"] = lt.residual_in_funds
    sector_items = [
        {
            "name": k,
            "value": v,
            "weight": v / total if total else 0.0,
            "weight_of_equity": v / equity_exposure if equity_exposure else 0.0,
        }
        for k, v in sorted(sector_values.items(), key=lambda kv: -kv[1])
    ]
    mcap = exposure.group_exposure(lt.stock_values, inp.instruments, "market_cap")
    stock_total = sum(mcap.values())
    mcap_items = [
        {"name": k, "value": v, "weight": v / stock_total if stock_total else 0.0} for k, v in mcap.items()
    ]

    # ---- Fund overlap --------------------------------------------------------------------
    overlap_rows: list[dict[str, Any]] = []
    covered_funds = [i for i in values if i in lt.data_dates]
    for a, b in combinations(sorted(covered_funds), 2):
        ca, cb = inp.constituents[a], inp.constituents[b]
        shared = ca.weights.keys() & cb.weights.keys()
        overlap_rows.append(
            {
                "fund_a_id": a,
                "fund_b_id": b,
                "fund_a": inp.instruments[a].name,
                "fund_b": inp.instruments[b].name,
                "overlap": exposure.fund_overlap(ca, cb),
                "shared_stocks": len(shared),
                "as_of": min(ca.as_of, cb.as_of).isoformat(),
            }
        )
    overlap_rows.sort(key=lambda o: -o["overlap"])

    hhi = exposure.herfindahl(list(values.values()))
    company_hhi = exposure.herfindahl(list(lt.stock_values.values()))

    # ---- Performance -------------------------------------------------------------------
    vs = series.value_series(txns, inp.prices, valuation_date)
    rets = series.daily_returns(vs)
    if not vs.empty and not vs["complete"].all():
        n = int((~vs["complete"]).sum())
        quality.append(
            {
                "level": "info",
                "message": f"{n} days lack a price for a held "
                "instrument and are excluded from return and risk calculations.",
            }
        )
    twr = series.annualized_return(rets)
    equity_share = asset.get("equity", 0.0)
    bench_compatible = equity_share >= 0.65 and bool(inp.benchmark_prices)
    bench_rets = pd.Series(dtype=float)
    bench_ann = None
    if inp.benchmark_prices:
        b = pd.Series({pd.Timestamp(d): v for d, v in inp.benchmark_prices.items()}).sort_index()
        bench_rets = b.pct_change().dropna()
        if not rets.empty:
            bench_rets = bench_rets.loc[rets.index[0] : rets.index[-1]]
            bench_ann = series.annualized_return(bench_rets)
    if inp.benchmark_prices and not bench_compatible:
        quality.append(
            {
                "level": "info",
                "message": f"Equity is {equity_share:.0%} of the "
                f"portfolio, so {inp.benchmark_name} is not a fair benchmark; "
                "benchmark comparison is shown for reference only.",
            }
        )

    perf_series: list[dict[str, Any]] = []
    if not rets.empty:
        base = _base_date(vs, rets)
        wi = series.wealth_index(rets, base)
        bwi = (
            series.wealth_index(bench_rets.reindex(rets.index).fillna(0.0), base)
            if not bench_rets.empty
            else None
        )
        invested = vs["flow"].cumsum()
        step = max(len(wi) // SERIES_POINTS, 1)
        idx = list(wi.index[::step])
        if idx[-1] != wi.index[-1]:
            idx.append(wi.index[-1])
        for ts in idx:
            perf_series.append(
                {
                    "date": ts.date().isoformat(),
                    "value": round(float(vs.loc[ts, "value"]), 2),
                    "invested": round(float(invested.loc[ts]), 2),
                    "portfolio_index": round(float(wi.loc[ts]) * 100, 3),
                    "benchmark_index": round(float(bwi.loc[ts]) * 100, 3) if bwi is not None else None,
                }
            )

    # ---- Risk ----------------------------------------------------------------------------
    risk_block: dict[str, Any] = {
        "available": False,
        "observations": len(rets),
        "hhi": hhi,
        "effective_holdings": (1 / hhi) if hhi else None,
        "company_hhi": company_hhi,
        "method": {
            "returns": "Time-weighted daily returns: (V_t - F_t) / V_{t-1} - 1",
            "volatility": "Sample standard deviation of daily returns x sqrt(252)",
            "drawdown": "Largest fall from a running peak of the time-weighted wealth index",
            "beta": "Cov(Rp, Rm) / Var(Rm) on aligned daily returns",
            "var": "1-day 95% historical VaR; parametric VaR shown as a cross-check",
        },
    }
    if risk.has_enough_history(rets):
        dd = risk.max_drawdown(series.wealth_index(rets, _base_date(vs, rets)))
        beta_value = risk.beta(rets, bench_rets) if not bench_rets.empty else None
        risk_block.update(
            {
                "available": True,
                "period_start": rets.index[0].date().isoformat(),
                "period_end": rets.index[-1].date().isoformat(),
                "volatility": risk.annualized_volatility(rets),
                "max_drawdown": dd.max_drawdown,
                "drawdown_peak": dd.peak_date,
                "drawdown_trough": dd.trough_date,
                "beta": beta_value if bench_compatible else None,
                "var_95_1d": risk.historical_var(rets, total),
                "var_95_1d_parametric": risk.parametric_var(rets, total),
            }
        )
    else:
        risk_block["reason"] = (
            f"Needs at least {risk.MIN_HISTORY_DAYS} days and {risk.MIN_OBSERVATIONS} daily "
            f"returns; this portfolio has {len(rets)}."
        )

    report: dict[str, Any] = {
        "meta": {
            "calc_version": CALC_VERSION,
            "valuation_date": valuation_date.isoformat(),
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "benchmark": inp.benchmark_name,
            "data_sources": inp.data_sources,
            "currency": "INR",
        },
        "overview": {
            "current_value": total,
            "cost": cost,
            "unrealized_gain": total - cost,
            "net_invested": -sum(a for _, a in flows),
            "xirr": p_xirr,
            "holdings_count": len(rows),
            "funds_count": sum(1 for r in rows if r["type"] in ("mutual_fund", "etf")),
            "stocks_count": sum(1 for r in rows if r["type"] == "stock"),
            "liquid_weight": liquid / total if total else 0.0,
            "first_investment": min(t.date for t in txns).isoformat() if txns else None,
        },
        "holdings": rows,
        "allocation": {
            "asset_class": [{"name": k, "weight": v, "value": v * total} for k, v in asset.items()],
            "sector": {"reliable": lt.is_reliable, "items": sector_items},
            "market_cap": mcap_items,
            "top_companies": top_companies,
            "lookthrough": {
                "coverage": lt.coverage,
                "reliable": lt.is_reliable,
                "covered_fund_value": lt.covered_fund_value,
                "eligible_fund_value": lt.eligible_fund_value,
                "excluded": lt.excluded_funds,
                "data_dates": lt.data_dates,
            },
        },
        "overlap": overlap_rows,
        "performance": {
            "series": perf_series,
            "twr_annualized": twr,
            "benchmark_annualized": bench_ann,
            "benchmark_name": inp.benchmark_name,
            "benchmark_compatible": bench_compatible,
            "period_start": perf_series[0]["date"] if perf_series else None,
            "period_end": perf_series[-1]["date"] if perf_series else None,
        },
        "risk": risk_block,
        "data_quality": quality,
    }
    # ---- What helped and what hurt ---------------------------------------------------------
    report["contribution"] = contributions(
        txns,
        values,
        inp.instruments,
        valuation_date,
        inp.benchmark_prices,
        {r["instrument_id"]: r["xirr"] for r in rows},
        compare_with_index=bool(inp.benchmark_prices),
    )

    # ---- Risk profile and goals (wealth planning) ---------------------------------------------
    report["planning"] = build_planning(inp.plan, asset, total, valuation_date)

    # ---- Review flags, options to discuss, plain-English summary ----------------------------
    findings = [f.to_dict() for f in evaluate_rules(report)]
    ctx = ActionContext(
        total=total,
        valuation_date=valuation_date,
        holdings={r["instrument_id"]: r for r in rows},
        instruments=inp.instruments,
        lots=fifo_lots(txns, valuation_date),
        constituents={i: inp.constituents[i] for i in lt.data_dates},
        contribution={c["instrument_id"]: c for c in report["contribution"]["items"]},
        equity_exposure=equity_exposure,
    )
    report["findings"] = attach_options(findings, ctx)
    report["summary"] = build_summary(report)
    return report
