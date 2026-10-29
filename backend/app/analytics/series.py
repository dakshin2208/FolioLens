"""Daily portfolio value, external cash flows and time-weighted returns."""

from datetime import date

import numpy as np
import pandas as pd

from app.analytics.types import LedgerTxn, signed_units

MAX_STALE_ROWS = 5  # a price may be carried forward at most 5 rows (about a trading week)


def external_flow(t: LedgerTxn) -> float:
    """Money entering (+) or leaving (-) the portfolio. Internal moves are zero."""
    if t.type == "buy":
        return t.amount
    if t.type in ("sell", "dividend_payout"):
        return -t.amount
    return 0.0


def value_series(
    transactions: list[LedgerTxn],
    prices: dict[str, dict[date, float]],
    end: date,
) -> pd.DataFrame:
    """Return a frame indexed by date with columns: value, flow, complete.

    `complete` is False on days where a held instrument has no usable price; those days
    are excluded from return calculations instead of being valued at zero.
    """
    if not transactions:
        return pd.DataFrame(columns=["value", "flow", "complete"])
    start = min(t.date for t in transactions)
    ids = sorted({t.instrument_id for t in transactions})

    dates: set[date] = {t.date for t in transactions if t.date <= end}
    for i in ids:
        dates.update(d for d in prices.get(i, {}) if start <= d <= end)
    index = pd.DatetimeIndex(sorted(pd.Timestamp(d) for d in dates))

    price_df = pd.DataFrame(index=index, columns=ids, dtype=float)
    for i in ids:
        series = pd.Series({pd.Timestamp(d): v for d, v in prices.get(i, {}).items()}, dtype=float)
        if not series.empty:
            # Include the last price before `start` so day one can be valued.
            series = series.sort_index()
            price_df[i] = series.reindex(series.index.union(index)).ffill(limit=MAX_STALE_ROWS).reindex(index)

    unit_changes = pd.DataFrame(0.0, index=index, columns=ids)
    flows = pd.Series(0.0, index=index)
    for t in transactions:
        if t.date > end:
            continue
        ts = pd.Timestamp(t.date)
        unit_changes.loc[ts, t.instrument_id] += signed_units(t)
        flows.loc[ts] += external_flow(t)
    units = unit_changes.cumsum()
    units = units.mask(units.abs() < 1e-9, 0.0)

    held = units > 0
    missing = held & price_df.isna()
    value = (units * price_df.fillna(0.0)).sum(axis=1)
    out = pd.DataFrame({"value": value, "flow": flows, "complete": ~missing.any(axis=1)})
    return out


def daily_returns(series: pd.DataFrame) -> pd.Series:
    """Time-weighted daily return, removing the effect of contributions and withdrawals:

    R_t = (V_t - F_t) / V_{t-1} - 1
    """
    if series.empty:
        return pd.Series(dtype=float)
    v = series["value"]
    prev = v.shift(1)
    ok = series["complete"] & series["complete"].shift(1, fill_value=False) & (prev > 0)
    r = (v - series["flow"]) / prev - 1.0
    return r[ok].replace([np.inf, -np.inf], np.nan).dropna()


def wealth_index(returns: pd.Series, start: pd.Timestamp | None = None) -> pd.Series:
    """Growth of 1 rupee invested at the start (time-weighted).

    The series begins with 1.0 on `start` (the day before the first return), so a loss on the
    very first day is measured from the starting value, e.g. for drawdown.
    """
    if returns.empty:
        return returns
    if start is None:
        start = returns.index[0] - pd.Timedelta(days=1)
    growth = (1.0 + returns).cumprod()
    return pd.concat([pd.Series([1.0], index=[start]), growth])


def annualized_return(returns: pd.Series) -> float | None:
    if len(returns) < 2:
        return None
    days = (returns.index[-1] - returns.index[0]).days
    if days < 30:
        return None
    growth = float((1.0 + returns).prod())
    return growth ** (365.0 / days) - 1.0
