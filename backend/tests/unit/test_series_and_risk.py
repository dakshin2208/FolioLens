from datetime import date

import pandas as pd
import pytest

from app.analytics import risk
from app.analytics.series import annualized_return, daily_returns, value_series, wealth_index
from app.analytics.types import LedgerTxn as T


def test_contribution_is_not_counted_as_return():
    prices = {"a": {date(2024, 1, 1): 10.0, date(2024, 1, 2): 11.0, date(2024, 1, 3): 11.0}}
    txns = [
        T("a", date(2024, 1, 1), "buy", 100, 1000),
        T("a", date(2024, 1, 3), "buy", 100, 1100),
    ]
    vs = value_series(txns, prices, date(2024, 1, 3))
    assert vs["value"].tolist() == [1000, 1100, 2200]
    r = daily_returns(vs)
    assert r.tolist() == pytest.approx([0.10, 0.0])  # the 1,100 top-up is not a gain


def test_days_without_a_price_are_excluded_not_zero():
    prices = {
        "a": {date(2024, 1, 1): 10.0, date(2024, 1, 2): 10.5},
        "b": {date(2024, 1, 2): 20.0},
    }
    txns = [T("a", date(2024, 1, 1), "buy", 10, 100), T("b", date(2024, 1, 1), "buy", 5, 100)]
    vs = value_series(txns, prices, date(2024, 1, 2))
    assert vs["complete"].tolist() == [False, True]
    assert daily_returns(vs).empty


def _wealth(values):
    idx = pd.date_range("2024-01-01", periods=len(values))
    return pd.Series(values, index=idx, dtype=float)


def test_max_drawdown_known_series():
    dd = risk.max_drawdown(_wealth([100, 120, 90, 95, 130, 80]))
    assert dd.max_drawdown == pytest.approx(80 / 130 - 1)
    assert dd.peak_date == "2024-01-05"
    assert dd.trough_date == "2024-01-06"


def test_volatility_and_beta():
    idx = pd.bdate_range("2023-01-02", periods=300)
    rm = pd.Series([0.01, -0.01] * 150, index=idx)
    rp = rm * 0.5
    assert risk.beta(rp, rm) == pytest.approx(0.5)
    assert risk.annualized_volatility(rp) == pytest.approx(rp.std(ddof=1) * 252**0.5)
    assert risk.beta(rp.iloc[:10], rm.iloc[:10]) is None  # too few observations


def test_historical_var_is_a_positive_loss():
    idx = pd.bdate_range("2023-01-02", periods=100)
    r = pd.Series([-0.03] * 10 + [0.01] * 90, index=idx)
    assert risk.historical_var(r, 100000) == pytest.approx(3000)
    assert risk.parametric_var(r, 100000) > 0


def test_history_requirement():
    short = pd.Series(0.001, index=pd.bdate_range("2024-01-01", periods=100))
    assert not risk.has_enough_history(short)
    long = pd.Series(0.001, index=pd.bdate_range("2023-01-02", periods=270))
    assert risk.has_enough_history(long)


def test_annualized_return_and_wealth():
    r = pd.Series(0.0, index=pd.date_range("2023-01-01", "2024-01-01"))
    r.iloc[-1] = 0.10
    assert annualized_return(r) == pytest.approx(0.10)
    assert wealth_index(r).iloc[-1] == pytest.approx(1.10)


def test_drawdown_counts_a_fall_from_the_first_day():
    r = pd.Series([-0.10, -0.10], index=pd.bdate_range("2024-01-02", periods=2))
    assert risk.max_drawdown(wealth_index(r)).max_drawdown == pytest.approx(-0.19)
    assert wealth_index(r).iloc[0] == 1.0
