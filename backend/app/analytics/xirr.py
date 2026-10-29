"""XIRR: the annual rate r that makes the net present value of dated cash flows zero.

    sum_i  C_i / (1 + r) ** ((d_i - d_0) / 365)  =  0

Convention (same as Excel): money the investor puts in is negative, money received
(including the final portfolio value) is positive. Day count is Actual/365.
"""

from datetime import date

from scipy.optimize import brentq

MIN_RATE = -0.999999
MAX_RATE = 100.0
# Rates scanned for sign changes of the NPV; each bracket is then solved precisely.
# fmt: off
RATE_GRID = [MIN_RATE, -0.99, -0.95, -0.9, -0.8, -0.6, -0.4, -0.2, -0.1, 0.0, 0.05, 0.1, 0.2,
             0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 20.0, 50.0, MAX_RATE]
# fmt: on


class XirrError(ValueError):
    """Raised when XIRR is undefined or cannot be determined reliably."""


def _npv(rate: float, flows: list[tuple[float, float]]) -> float:
    return sum(amount / (1.0 + rate) ** years for years, amount in flows)


def _dnpv(rate: float, flows: list[tuple[float, float]]) -> float:
    return sum(-years * amount / (1.0 + rate) ** (years + 1.0) for years, amount in flows)


def xirr(cashflows: list[tuple[date, float]], guess: float = 0.1) -> float:
    """Return XIRR as a fraction (0.1234 = 12.34% a year).

    Raises XirrError if the inputs are invalid, no root exists, or several different
    rates satisfy the equation (which happens with some patterns of in and out flows).
    """
    flows_in = [(d, float(a)) for d, a in cashflows if a != 0]
    if len(flows_in) < 2:
        raise XirrError("At least two non-zero cash flows are required")
    if not any(a < 0 for _, a in flows_in) or not any(a > 0 for _, a in flows_in):
        raise XirrError("Cash flows need at least one negative and one positive amount")

    flows_in.sort(key=lambda x: x[0])
    d0 = flows_in[0][0]
    flows = [((d - d0).days / 365.0, a) for d, a in flows_in]
    if flows[-1][0] == 0:
        raise XirrError("All cash flows fall on the same date")

    roots = _find_roots(flows)
    if not roots:
        raise XirrError("No rate makes the net present value zero")
    if len(roots) > 1:
        raise XirrError(f"Ambiguous: several rates fit these cash flows ({roots})")

    # Polish the bracketed root with Newton's method for full precision.
    rate = roots[0]
    for _ in range(50):
        f, df = _npv(rate, flows), _dnpv(rate, flows)
        if df == 0:
            break
        step = f / df
        rate -= step
        if abs(step) < 1e-12:
            break
    return rate


def _find_roots(flows: list[tuple[float, float]]) -> list[float]:
    """Scan a grid of rates for sign changes, then solve each bracket with Brent's method."""
    grid = RATE_GRID
    values = [_npv(r, flows) for r in grid]
    roots: list[float] = []
    for i in range(len(grid) - 1):
        a, b, fa, fb = grid[i], grid[i + 1], values[i], values[i + 1]
        if fa == 0:
            roots.append(a)
        elif fa * fb < 0:
            roots.append(float(brentq(_npv, a, b, args=(flows,), xtol=1e-14, maxiter=200)))
    if values[-1] == 0:
        roots.append(grid[-1])
    distinct: list[float] = []
    for r in sorted(roots):
        if not distinct or abs(r - distinct[-1]) > 1e-6:
            distinct.append(r)
    return distinct


def cagr(start_value: float, end_value: float, start: date, end: date) -> float:
    """Compound annual growth rate between two values. Not a substitute for XIRR when
    money was added or withdrawn in between."""
    years = (end - start).days / 365.0
    if years <= 0:
        raise ValueError("End date must be after start date")
    if start_value <= 0 or end_value < 0:
        raise ValueError("Values must be positive")
    return (end_value / start_value) ** (1.0 / years) - 1.0
