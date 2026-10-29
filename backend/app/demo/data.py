"""Synthetic demo portfolio.

Every company, fund, price and transaction here is fictional and generated from a fixed
random seed, so the demo is identical on every run and contains no real person's data.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.analytics.planning import Goal, PlanInput
from app.analytics.types import Constituents, InstrumentInfo, LedgerTxn, PortfolioInput

SEED = 3
START = date(2023, 4, 3)
END = date(2026, 10, 9)

# id, name, sector, market cap, annual drift, annual vol, market beta
STOCKS = [
    ("stk-indus", "Indus Software Ltd", "Information Technology", "large", 0.13, 0.26, 0.9),
    ("stk-deccan", "Deccan Infotech Ltd", "Information Technology", "large", 0.12, 0.27, 0.9),
    ("stk-bharatdig", "Bharat Digital Services Ltd", "Information Technology", "mid", 0.15, 0.32, 1.0),
    ("stk-sahyadri", "Sahyadri Bank Ltd", "Financials", "large", 0.14, 0.24, 1.1),
    ("stk-coastal", "Coastal Finance Ltd", "Financials", "mid", 0.16, 0.30, 1.2),
    ("stk-ganga", "Ganga Consumer Products Ltd", "Consumer Staples", "large", 0.10, 0.18, 0.6),
    ("stk-narmada", "Narmada Pharma Ltd", "Health Care", "mid", 0.12, 0.25, 0.7),
    ("stk-vindhya", "Vindhya Energy Ltd", "Energy", "large", 0.11, 0.25, 1.0),
    ("stk-konkan", "Konkan Motors Ltd", "Automobiles", "mid", 0.15, 0.30, 1.1),
    ("stk-aravalli", "Aravalli Cement Ltd", "Materials", "small", 0.14, 0.33, 1.1),
    ("stk-thar", "Thar Telecom Ltd", "Communication Services", "large", 0.12, 0.24, 0.8),
    ("stk-malabar", "Malabar Power Ltd", "Utilities", "small", 0.13, 0.28, 0.9),
]

FUNDS = {
    "mf-bluechip": ("Demo Bluechip Equity Fund", "equity", "Equity - Large Cap"),
    "mf-flexi": ("Demo Flexi Cap Fund", "equity", "Equity - Flexi Cap"),
    "mf-tech": ("Demo Technology Fund", "equity", "Equity - Sectoral (Technology)"),
    "mf-midcap": ("Demo Midcap Opportunities Fund", "equity", "Equity - Mid Cap"),
    "mf-debt": ("Demo Short Duration Fund", "debt", "Debt - Short Duration"),
    "mf-liquid": ("Demo Liquid Fund", "debt", "Debt - Liquid"),
    "etf-gold": ("Demo Gold ETF", "gold", "ETF - Gold"),
}

CONSTITUENTS = {
    "mf-bluechip": {
        "stk-indus": 0.11,
        "stk-deccan": 0.08,
        "stk-sahyadri": 0.12,
        "stk-ganga": 0.09,
        "stk-vindhya": 0.10,
        "stk-thar": 0.08,
        "stk-coastal": 0.06,
        "stk-bharatdig": 0.05,
        "stk-narmada": 0.05,
        "stk-konkan": 0.05,
        "stk-malabar": 0.04,
        "stk-aravalli": 0.03,
    },
    "mf-flexi": {
        "stk-indus": 0.12,
        "stk-deccan": 0.09,
        "stk-sahyadri": 0.11,
        "stk-ganga": 0.08,
        "stk-vindhya": 0.09,
        "stk-thar": 0.07,
        "stk-coastal": 0.07,
        "stk-bharatdig": 0.06,
        "stk-konkan": 0.06,
        "stk-narmada": 0.05,
        "stk-aravalli": 0.04,
        "stk-malabar": 0.03,
    },
    "mf-tech": {"stk-indus": 0.28, "stk-deccan": 0.24, "stk-bharatdig": 0.22, "stk-thar": 0.12},
    "mf-midcap": {
        "stk-coastal": 0.14,
        "stk-bharatdig": 0.13,
        "stk-narmada": 0.13,
        "stk-konkan": 0.14,
        "stk-aravalli": 0.12,
        "stk-malabar": 0.13,
    },
}
CONSTITUENTS_AS_OF = {
    "mf-bluechip": date(2026, 9, 30),
    "mf-flexi": date(2026, 9, 30),
    "mf-tech": date(2026, 9, 30),
    "mf-midcap": date(2026, 4, 30),  # deliberately stale: the report must exclude it
}

BENCHMARK_ID = "idx-synthetic"
BENCHMARK_NAME = "Synthetic Large-Cap Index (TRI)"

# The sample client's risk answers (option 0 = most careful) and goals, all fictional.
DEMO_PLAN = PlanInput(
    risk_answers={"age": 3, "horizon": 3, "income": 2, "drop": 2, "experience": 3, "cushion": 2},
    goals=[
        Goal("home", "Home down payment", 1_500_000, date(2028, 6, 1), 10_000, 0.15),
        Goal("education", "Child's education", 2_500_000, date(2036, 6, 1), 15_000, 0.35),
        Goal("retirement", "Retirement", 15_000_000, date(2050, 4, 1), 30_000, 0.50),
    ],
)


def _business_days() -> pd.DatetimeIndex:
    return pd.bdate_range(START, END)


def _simulate(days: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(SEED)
    n = len(days)
    dt = 1 / 252
    market = rng.normal(0.12 * dt, 0.15 * np.sqrt(dt), n)
    # A sharp correction in mid-2024 so drawdown is meaningful
    market[300:330] -= 0.006
    sector_shock = {s: rng.normal(0, 0.08 * np.sqrt(dt), n) for s in sorted({x[2] for x in STOCKS})}
    rets = {}
    for sid, _, sector, _, mu, vol, b in STOCKS:
        idio = rng.normal(0, np.sqrt(max(vol**2 - (b * 0.15) ** 2 - 0.08**2, 0.01)) * np.sqrt(dt), n)
        rets[sid] = (mu - 0.12 * b) * dt + b * market + sector_shock[sector] + idio
    stock_rets = pd.DataFrame(rets, index=days)
    stock_rets.iloc[0] = 0.0
    bench = pd.Series(market, index=days)
    bench.iloc[0] = 0.0
    return stock_rets, bench


def _prices_from_returns(rets: pd.Series, start_price: float) -> pd.Series:
    return start_price * (1 + rets).cumprod()


def build_demo_input() -> PortfolioInput:
    days = _business_days()
    stock_rets, bench_rets = _simulate(days)
    rng = np.random.default_rng(SEED + 1)
    dt = 1 / 252

    instruments: dict[str, InstrumentInfo] = {}
    prices: dict[str, dict[date, float]] = {}
    start_prices = [1450, 1180, 640, 980, 410, 2350, 860, 290, 720, 1890, 115, 140]
    for (sid, name, sector, mcap, *_), p0 in zip(STOCKS, start_prices, strict=True):
        instruments[sid] = InstrumentInfo(sid, name, "stock", "equity", sector=sector, market_cap=mcap)
        s = _prices_from_returns(stock_rets[sid], p0).round(2)
        prices[sid] = {ts.date(): float(v) for ts, v in s.items()}

    for fid, (name, asset_class, category) in FUNDS.items():
        is_liquid = fid == "mf-liquid"
        ftype = "etf" if fid.startswith("etf") else "mutual_fund"
        instruments[fid] = InstrumentInfo(
            fid, name, ftype, asset_class, category=category, is_liquid=is_liquid
        )
        if fid in CONSTITUENTS:
            w = CONSTITUENTS[fid]
            cash = 1 - sum(w.values())
            r = sum(stock_rets[s] * wt for s, wt in w.items()) + cash * 0.065 * dt
            r = r - 0.01 * dt  # expense ratio
        elif fid == "mf-debt":
            r = pd.Series(rng.normal(0.072 * dt, 0.012 * np.sqrt(dt), len(days)), index=days)
        elif fid == "mf-liquid":
            r = pd.Series(rng.normal(0.066 * dt, 0.002 * np.sqrt(dt), len(days)), index=days)
        else:
            r = pd.Series(rng.normal(0.10 * dt, 0.14 * np.sqrt(dt), len(days)), index=days)
        r.iloc[0] = 0.0
        nav = _prices_from_returns(r, {"etf-gold": 58.0}.get(fid, 100.0)).round(4)
        prices[fid] = {ts.date(): float(v) for ts, v in nav.items()}

    bench = _prices_from_returns(bench_rets, 10000.0).round(2)
    benchmark_prices = {ts.date(): float(v) for ts, v in bench.items()}

    txns = _demo_transactions(prices, days)
    constituents = {fid: Constituents(CONSTITUENTS_AS_OF[fid], dict(w)) for fid, w in CONSTITUENTS.items()}
    return PortfolioInput(
        instruments=instruments,
        transactions=txns,
        prices=prices,
        constituents=constituents,
        benchmark_name=BENCHMARK_NAME,
        benchmark_prices=benchmark_prices,
        valuation_date=END,
        data_sources=["Synthetic demo data (fictional instruments and prices)"],
        plan=DEMO_PLAN,
    )


def _on_or_after(d: date, prices: dict[date, float]) -> date:
    while d not in prices:
        d += timedelta(days=1)
    return d


def _demo_transactions(prices: dict[str, dict[date, float]], days: pd.DatetimeIndex) -> list[LedgerTxn]:
    txns: list[LedgerTxn] = []

    def trade(iid: str, d: date, ttype: str, amount: float) -> None:
        d = _on_or_after(d, prices[iid])
        txns.append(LedgerTxn(iid, d, ttype, round(amount / prices[iid][d], 4), amount))

    sips = {"mf-bluechip": 15000, "mf-flexi": 15000, "mf-tech": 12000, "mf-midcap": 6000, "mf-debt": 10000}
    month = date(2023, 4, 5)
    while month <= END:
        for fid, amt in sips.items():
            if fid == "mf-midcap" and month < date(2024, 1, 1):
                continue
            trade(fid, month, "buy", amt)
        month = (month.replace(day=1) + timedelta(days=32)).replace(day=5)

    trade("stk-indus", date(2023, 5, 15), "buy", 420000)
    trade("stk-indus", date(2024, 8, 12), "buy", 180000)
    trade("stk-sahyadri", date(2023, 9, 4), "buy", 150000)
    trade("stk-narmada", date(2024, 2, 19), "buy", 90000)
    trade("mf-liquid", date(2023, 4, 10), "buy", 60000)
    trade("etf-gold", date(2023, 11, 6), "buy", 75000)

    # Partial sale of the direct stock
    d = _on_or_after(date(2025, 6, 16), prices["stk-sahyadri"])
    units = 40.0
    txns.append(LedgerTxn("stk-sahyadri", d, "sell", units, round(units * prices["stk-sahyadri"][d], 2)))

    # Annual dividends paid out in cash (units unchanged)
    for y in (2024, 2025, 2026):
        d = _on_or_after(date(y, 7, 22), prices["stk-sahyadri"])
        txns.append(LedgerTxn("stk-sahyadri", d, "dividend_payout", 0.0, 1850.0 + 150 * (y - 2024)))

    # Switch: part of the flexi-cap holding moved into the debt fund on the same day
    d = _on_or_after(date(2025, 11, 10), prices["mf-flexi"])
    out_units = 1200.0
    amount = round(out_units * prices["mf-flexi"][d], 2)
    txns.append(LedgerTxn("mf-flexi", d, "switch_out", out_units, amount))
    txns.append(LedgerTxn("mf-debt", d, "switch_in", round(amount / prices["mf-debt"][d], 4), amount))

    return sorted(txns, key=lambda t: t.date)
