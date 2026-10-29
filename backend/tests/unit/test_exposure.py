from datetime import date

import pytest

from app.analytics.exposure import fund_overlap, herfindahl, look_through
from app.analytics.types import Constituents, InstrumentInfo

INSTR = {
    "f1": InstrumentInfo("f1", "Fund One", "mutual_fund", "equity"),
    "f2": InstrumentInfo("f2", "Fund Two", "mutual_fund", "equity"),
    "d1": InstrumentInfo("d1", "Debt Fund", "mutual_fund", "debt"),
    "s1": InstrumentInfo("s1", "Stock One", "stock", "equity", sector="IT"),
    "s2": InstrumentInfo("s2", "Stock Two", "stock", "equity", sector="Banks"),
}
VDATE = date(2026, 10, 1)


def test_look_through_combines_direct_and_indirect_without_double_counting():
    cons = {"f1": Constituents(date(2026, 9, 30), {"s1": 0.5, "s2": 0.3})}
    lt = look_through({"f1": 1000, "s1": 200, "d1": 500}, INSTR, cons, VDATE)
    assert lt.stock_values == pytest.approx({"s1": 700, "s2": 300})
    assert lt.residual_in_funds == pytest.approx(200)
    assert lt.coverage == 1.0 and lt.is_reliable  # debt fund is not eligible for look-through


def test_stale_constituents_are_excluded_and_reported():
    cons = {
        "f1": Constituents(date(2026, 9, 30), {"s1": 1.0}),
        "f2": Constituents(date(2026, 3, 31), {"s2": 1.0}),
    }
    lt = look_through({"f1": 600, "f2": 400}, INSTR, cons, VDATE)
    assert "s2" not in lt.stock_values
    assert lt.coverage == pytest.approx(0.6)
    assert not lt.is_reliable
    assert lt.excluded_funds[0]["instrument_id"] == "f2"


def test_overlap_formula():
    a = Constituents(VDATE, {"x": 0.4, "y": 0.3, "z": 0.3})
    b = Constituents(VDATE, {"x": 0.2, "y": 0.5, "w": 0.3})
    assert fund_overlap(a, b) == pytest.approx(0.2 + 0.3)
    assert fund_overlap(a, a) == pytest.approx(1.0)


def test_herfindahl():
    assert herfindahl([1, 1, 1, 1]) == pytest.approx(0.25)
    assert herfindahl([10]) == pytest.approx(1.0)
    assert herfindahl([]) == 0.0
