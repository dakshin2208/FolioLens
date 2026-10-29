"""Deterministic explanations. Used when the LLM is off, unavailable or fails validation."""

from typing import Any


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def inr(x: float) -> str:
    """₹7,16,229 (Indian digit grouping)."""
    n = str(round(abs(x)))
    head, tail = n[:-3], n[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ("-" if x < 0 else "") + "₹" + ",".join([*groups, tail])


def template_explanation(f: dict[str, Any]) -> str:
    t, v, th = f["type"], f["measured_value"], f["threshold"]
    ev = f.get("evidence", {})
    names = f.get("instruments", [])
    if t == "single_stock_concentration":
        return (
            f"{names[0]} makes up {pct(v)} of the portfolio, above the {pct(th)} review "
            f"threshold. Of this, {inr(ev.get('direct_value', 0))} is held directly and "
            f"{inr(ev.get('via_funds_value', 0))} through mutual funds, so a fall in this one "
            "company would affect several holdings at once."
        )
    if t == "sector_concentration":
        return (
            f"{ev.get('sector')} accounts for {pct(v)} of equity exposure, above the {pct(th)} "
            "review threshold, after looking through the funds to the stocks they hold. "
            "Events that hit this sector would move a large part of the portfolio together."
        )
    if t == "fund_overlap":
        return (
            f"{names[0]} and {names[1]} overlap by {pct(v)} based on their latest disclosed "
            f"holdings ({ev.get('shared_stocks')} stocks in common), above the {pct(th)} review "
            "threshold. Holding both adds less diversification than it appears."
        )
    if t == "too_many_funds":
        return (
            f"The portfolio holds {int(v)} funds, more than the {int(th)} used as a review "
            "guide. Many funds can overlap heavily and make the portfolio harder to monitor."
        )
    if t == "low_liquidity":
        return (
            f"Only {pct(v)} of this portfolio is in cash or liquid funds, below the {pct(th)} "
            "review threshold. Check whether the client keeps emergency money elsewhere."
        )
    if t == "benchmark_underperformance":
        return (
            f"Over the measured period the portfolio returned {pct(ev['portfolio_annualized'])} "
            f"a year (time-weighted) against {pct(ev['benchmark_annualized'])} for the "
            f"benchmark, a gap of {v * 100:.1f} percentage points a year. "
            "Past performance does not predict future results."
        )
    if t == "risk_mismatch":
        return (
            f"Equity is {pct(v)} of the portfolio (hybrid funds count as half). The client's "
            f"{ev.get('profile', '').lower()} risk profile suggests {pct(ev['equity_min'])} to "
            f"{pct(ev['equity_max'])}, so the portfolio is "
            f"{'riskier' if ev.get('direction') == 'above' else 'more cautious'} "
            "than the client's answers suggest."
        )
    if t == "goal_shortfall":
        return (
            f"{ev['goal']} needs about {inr(ev['target_future'])} by {ev['target_date']} "
            f"({inr(ev['target_today'])} in today's money, grown with {pct(ev['inflation'])} inflation). "
            f"With the money set aside and the {inr(ev['monthly_sip'])} monthly SIP, the projection is "
            f"{inr(ev['projected'])}, which covers {pct(v)} of it."
        )
    if t == "short_goal_in_equity":
        return (
            f"{ev['goal']} is due on {ev['target_date']}, but the money set aside for it sits in a portfolio "
            f"that is {pct(v)} equity. A market fall close to the date could leave too little time "
            "to recover."
        )
    return f"{f['title']}: measured {pct(v) if f['unit'] == 'percent' else v}."
