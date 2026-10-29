"""Historical risk metrics computed on time-weighted daily returns."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252
MIN_HISTORY_DAYS = 365  # PRD D-05: at least one year of history
MIN_OBSERVATIONS = 200
Z_95 = 1.6448536269514722


@dataclass
class Drawdown:
    max_drawdown: float  # negative fraction, e.g. -0.23
    peak_date: str | None
    trough_date: str | None


def has_enough_history(returns: pd.Series) -> bool:
    if len(returns) < MIN_OBSERVATIONS:
        return False
    return (returns.index[-1] - returns.index[0]).days >= MIN_HISTORY_DAYS


def annualized_volatility(returns: pd.Series) -> float:
    """Sample standard deviation of daily returns x sqrt(252)."""
    return float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def max_drawdown(wealth: pd.Series) -> Drawdown:
    """Largest fall from a running peak. Uses the time-weighted wealth index, not raw
    portfolio value, so a new SIP instalment is never mistaken for a recovery."""
    if wealth.empty:
        return Drawdown(0.0, None, None)
    running_peak = wealth.cummax()
    dd = wealth / running_peak - 1.0
    trough = dd.idxmin()
    peak = wealth.loc[:trough].idxmax()
    return Drawdown(float(dd.min()), str(peak.date()), str(trough.date()))


def beta(portfolio: pd.Series, benchmark: pd.Series, min_obs: int = 60) -> float | None:
    """Cov(Rp, Rm) / Var(Rm) on aligned dates. None if data is insufficient."""
    aligned = pd.concat([portfolio, benchmark], axis=1, join="inner").dropna()
    if len(aligned) < min_obs:
        return None
    rm_var = aligned.iloc[:, 1].var(ddof=1)
    if rm_var == 0 or np.isnan(rm_var):
        return None
    return float(aligned.iloc[:, 0].cov(aligned.iloc[:, 1]) / rm_var)


def historical_var(returns: pd.Series, value: float, confidence: float = 0.95) -> float:
    """1-day historical VaR in rupees: the loss exceeded on only (1 - confidence) of past
    days. It is an estimate from history, not the maximum possible loss."""
    q = float(np.quantile(returns.to_numpy(), 1.0 - confidence))
    return max(-q * value, 0.0)


def parametric_var(returns: pd.Series, value: float) -> float:
    """1-day 95% VaR assuming normally distributed returns (cross-check only)."""
    mu, sigma = float(returns.mean()), float(returns.std(ddof=1))
    return max((Z_95 * sigma - mu) * value, 0.0)
