from datetime import date

import pytest

from app.analytics.holdings import (
    build_holdings,
    holding_cashflows,
    portfolio_cashflows,
)
from app.analytics.types import LedgerTxn as T


def test_average_cost_after_partial_sale():
    txns = [
        T("a", date(2024, 1, 1), "buy", 100, 1000),
        T("a", date(2024, 2, 1), "buy", 100, 1400),
        T("a", date(2024, 3, 1), "sell", 50, 700),
    ]
    h = build_holdings(txns)["a"]
    assert h.units == pytest.approx(150)
    assert h.cost == pytest.approx(2400 * 0.75)  # a quarter of the cost leaves with the units


def test_full_sale_removes_holding():
    txns = [T("a", date(2024, 1, 1), "buy", 10, 100), T("a", date(2024, 2, 1), "sell", 10, 120)]
    assert build_holdings(txns) == {}


def test_selling_without_units_is_an_error():
    with pytest.raises(ValueError):
        build_holdings([T("a", date(2024, 1, 1), "sell", 1, 10)])


def test_dividend_payout_changes_nothing_but_reinvest_adds_units():
    txns = [
        T("a", date(2024, 1, 1), "buy", 10, 100),
        T("a", date(2024, 6, 1), "dividend_payout", 0, 5),
        T("a", date(2024, 7, 1), "dividend_reinvest", 0.5, 5),
    ]
    h = build_holdings(txns)["a"]
    assert h.units == pytest.approx(10.5)
    assert h.cost == pytest.approx(105)


def test_as_of_date_ignores_later_transactions():
    txns = [T("a", date(2024, 1, 1), "buy", 10, 100), T("a", date(2024, 5, 1), "buy", 10, 100)]
    assert build_holdings(txns, as_of=date(2024, 2, 1))["a"].units == 10


def test_switches_are_internal_for_portfolio_but_count_per_holding():
    txns = [
        T("a", date(2024, 1, 1), "buy", 10, 1000),
        T("a", date(2024, 6, 1), "switch_out", 5, 600),
        T("b", date(2024, 6, 1), "switch_in", 60, 600),
        T("a", date(2024, 7, 1), "dividend_payout", 0, 20),
    ]
    assert portfolio_cashflows(txns) == [(date(2024, 1, 1), -1000), (date(2024, 7, 1), 20)]
    assert holding_cashflows(txns, "b") == [(date(2024, 6, 1), -600)]
    assert holding_cashflows(txns, "a") == [
        (date(2024, 1, 1), -1000),
        (date(2024, 6, 1), 600),
        (date(2024, 7, 1), 20),
    ]
