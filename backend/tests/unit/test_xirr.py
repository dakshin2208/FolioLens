"""Reference tests for XIRR. Expected values were checked against Excel's XIRR()."""

from datetime import date, timedelta

import pytest

from app.analytics.xirr import XirrError, cagr, xirr


def test_excel_documentation_example():
    # The worked example from Microsoft's XIRR documentation: result 0.373362535
    flows = [
        (date(2008, 1, 1), -10000),
        (date(2008, 3, 1), 2750),
        (date(2008, 10, 30), 4250),
        (date(2009, 2, 15), 3250),
        (date(2009, 4, 1), 2750),
    ]
    assert xirr(flows) == pytest.approx(0.373362535, abs=1e-6)  # within 0.0001 pp


def test_one_year_ten_percent():
    assert xirr([(date(2023, 1, 1), -1000), (date(2024, 1, 1), 1100)]) == pytest.approx(0.10)


def test_order_of_input_does_not_matter():
    a = [(date(2023, 1, 1), -1000), (date(2023, 6, 1), -500), (date(2024, 3, 1), 1700)]
    assert xirr(a) == pytest.approx(xirr(list(reversed(a))))


def test_negative_return():
    r = xirr([(date(2023, 1, 1), -1000), (date(2024, 1, 1), 900)])
    assert r == pytest.approx(-0.10)


def _npv(rate, flows):
    d0 = min(d for d, _ in flows)
    return sum(a / (1 + rate) ** ((d - d0).days / 365) for d, a in flows)


def _bisect(flows, lo=-0.99, hi=10.0):
    """Independent, deliberately simple solver used to cross-check the production one."""
    for _ in range(200):
        mid = (lo + hi) / 2
        if _npv(lo, flows) * _npv(mid, flows) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def test_monthly_sip_matches_independent_solver():
    start = date(2022, 1, 5)
    flows = [(start + timedelta(days=30 * i), -10000) for i in range(36)]
    flows.append((date(2025, 1, 10), 450000))
    assert xirr(flows) == pytest.approx(_bisect(flows), abs=1e-6)
    assert abs(_npv(xirr(flows), flows)) < 1e-4


@pytest.mark.parametrize(
    "flows",
    [
        [(date(2023, 1, 1), -100)],
        [(date(2023, 1, 1), -100), (date(2024, 1, 1), -50)],
        [(date(2023, 1, 1), 100), (date(2024, 1, 1), 50)],
        [(date(2023, 1, 1), -100), (date(2023, 1, 1), 110)],
    ],
)
def test_invalid_inputs_raise(flows):
    with pytest.raises(XirrError):
        xirr(flows)


def test_multiple_roots_are_reported_not_guessed():
    # -100, +230, -132 has two valid rates: 10% and 20%
    flows = [(date(2021, 1, 1), -100), (date(2022, 1, 1), 230), (date(2023, 1, 1), -132)]
    with pytest.raises(XirrError, match="Ambiguous"):
        xirr(flows)


def test_cagr():
    assert cagr(100, 121, date(2023, 1, 1), date(2025, 1, 1)) == pytest.approx(0.1, abs=2e-4)
    with pytest.raises(ValueError):
        cagr(100, 120, date(2024, 1, 1), date(2024, 1, 1))
