"""Risk profiling and goal planning: the "wealth management" layer on top of the analysis.

Pure functions only (no database, network or LLM), like the rest of the engine.

1. Risk profile: six questions, each answered 1-5. The average maps to a score from 0 to 100
   and a band with a suggested equity range. This is a simple, transparent starting model; an
   advisor regulated by SEBI should still use their firm's own risk-profiling process.
2. Suitability: the portfolio's equity share (hybrid counts half) against that range.
3. Goals: each goal has a target in today's rupees, a date, a monthly SIP and a share of the
   current portfolio set aside for it. FolioLens grows the target with inflation, projects the
   money with an expected return from the portfolio's own asset mix, and reports how much of the
   goal is funded and the SIP that would close the gap.

All return and inflation figures are ASSUMPTIONS for planning, shown with every result, not
forecasts.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

# --------------------------------------------------------------------------- risk profile

RISK_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "age",
        "text": "How old is the client?",
        "options": ["65 or older", "55 to 64", "45 to 54", "30 to 44", "Under 30"],
    },
    {
        "id": "horizon",
        "text": "When will most of this money be needed?",
        "options": ["Within 3 years", "3 to 5 years", "5 to 7 years", "7 to 10 years", "More than 10 years"],
    },
    {
        "id": "income",
        "text": "How stable is the client's income?",
        "options": [
            "Irregular or retired with no pension",
            "Somewhat irregular",
            "Stable salary or pension",
            "Stable, with some savings each month",
            "Very stable, with other income too",
        ],
    },
    {
        "id": "drop",
        "text": "If the portfolio fell 20% in a few months, the client would…",
        "options": [
            "Sell everything",
            "Sell some to stop the loss",
            "Do nothing and wait",
            "Hold and keep the SIPs going",
            "Invest more while prices are low",
        ],
    },
    {
        "id": "experience",
        "text": "How much investing experience does the client have?",
        "options": [
            "None",
            "Only deposits or insurance",
            "Mutual funds for under 3 years",
            "Mutual funds or stocks for 3+ years",
            "Has invested through a full market fall",
        ],
    },
    {
        "id": "cushion",
        "text": "Emergency savings and dependants",
        "options": [
            "No emergency savings, several dependants",
            "Under 3 months saved, dependants",
            "3 to 6 months saved",
            "6+ months saved, few dependants",
            "6+ months saved, no dependants",
        ],
    },
]

# (name, lowest score, equity range as fractions of the portfolio)
RISK_BANDS: list[tuple[str, float, float, float]] = [
    ("Conservative", 0, 0.10, 0.30),
    ("Moderately conservative", 20, 0.25, 0.45),
    ("Moderate", 40, 0.40, 0.60),
    ("Moderately aggressive", 60, 0.55, 0.75),
    ("Aggressive", 80, 0.70, 0.90),
]

# Long-term planning assumptions (yearly). Change them here and bump CALC_VERSION.
EXPECTED_RETURN = {"equity": 0.11, "hybrid": 0.09, "debt": 0.07, "gold": 0.07, "cash": 0.05, "other": 0.06}
INFLATION = 0.06
ON_TRACK = 1.0  # funded ratio at or above this = on track
AT_RISK = 0.8  # between this and ON_TRACK = slightly short; below = off track
SHORT_GOAL_YEARS = 3.0
SHORT_GOAL_MAX_EQUITY = 0.40


def score_risk(answers: dict[str, int]) -> dict[str, Any] | None:
    """Answers are option positions 0-4 (0 = most careful). Returns None if none are answered."""
    valid = {q["id"]: answers[q["id"]] for q in RISK_QUESTIONS if isinstance(answers.get(q["id"]), int)}
    valid = {k: v for k, v in valid.items() if 0 <= v <= 4}
    if not valid:
        return None
    score = sum(valid.values()) / len(valid) / 4 * 100
    name, _, lo, hi = next(b for b in reversed(RISK_BANDS) if score >= b[1])
    return {
        "score": round(score, 1),
        "category": name,
        "equity_min": lo,
        "equity_max": hi,
        "answered": len(valid),
        "questions": len(RISK_QUESTIONS),
    }


def equity_share(asset_weights: dict[str, float]) -> float:
    """Share of the portfolio in equity; hybrid funds count as half equity."""
    return asset_weights.get("equity", 0.0) + 0.5 * asset_weights.get("hybrid", 0.0)


def expected_return(asset_weights: dict[str, float]) -> float:
    total = sum(asset_weights.values())
    if total <= 0:
        return EXPECTED_RETURN["other"]
    return sum(w * EXPECTED_RETURN.get(k, EXPECTED_RETURN["other"]) for k, w in asset_weights.items()) / total


# --------------------------------------------------------------------------------- goals


@dataclass(frozen=True)
class Goal:
    id: str
    name: str
    target_amount: float  # in today's rupees
    target_date: date
    monthly_sip: float = 0.0
    share_of_portfolio: float = 0.0  # fraction of today's portfolio set aside for this goal


@dataclass
class PlanInput:
    risk_answers: dict[str, int] = field(default_factory=dict)
    goals: list[Goal] = field(default_factory=list)


def _years(a: date, b: date) -> float:
    return (b - a).days / 365.25


def _sip_factor(rate: float, months: int) -> float:
    """Future value of ₹1 invested at the start of each month for `months` months."""
    if months <= 0:
        return 0.0
    i = (1 + rate) ** (1 / 12) - 1
    if i == 0:
        return float(months)
    return ((1 + i) ** months - 1) / i * (1 + i)


def project_goal(
    goal: Goal, portfolio_value: float, rate: float, as_of: date, inflation: float = INFLATION
) -> dict[str, Any]:
    years = max(_years(as_of, goal.target_date), 0.0)
    months = round(years * 12)
    set_aside = portfolio_value * goal.share_of_portfolio
    target_future = goal.target_amount * (1 + inflation) ** years
    from_today = set_aside * (1 + rate) ** years
    from_sip = goal.monthly_sip * _sip_factor(rate, months)
    projected = from_today + from_sip
    funded = projected / target_future if target_future > 0 else None
    factor = _sip_factor(rate, months)
    required_sip = max(target_future - from_today, 0.0) / factor if factor > 0 else None
    if years == 0:
        status = "due"
    elif funded is not None and funded >= ON_TRACK:
        status = "on_track"
    elif funded is not None and funded >= AT_RISK:
        status = "at_risk"
    else:
        status = "off_track"
    return {
        "id": goal.id,
        "name": goal.name,
        "target_today": goal.target_amount,
        "target_date": goal.target_date.isoformat(),
        "years": years,
        "target_future": target_future,
        "share_of_portfolio": goal.share_of_portfolio,
        "set_aside": set_aside,
        "monthly_sip": goal.monthly_sip,
        "expected_return": rate,
        "inflation": inflation,
        "projected": projected,
        "funded_ratio": funded,
        "gap": max(target_future - projected, 0.0),
        "required_sip": required_sip,
        "status": status,
    }


def years_to_reach(
    goal: Goal,
    portfolio_value: float,
    rate: float,
    as_of: date,
    inflation: float = INFLATION,
    max_years: int = 40,
) -> float | None:
    """Earliest time (in whole months) at which the projection meets the inflated target."""
    set_aside = portfolio_value * goal.share_of_portfolio
    for m in range(1, max_years * 12 + 1):
        y = m / 12
        if (
            set_aside * (1 + rate) ** y + goal.monthly_sip * _sip_factor(rate, m)
            >= goal.target_amount * (1 + inflation) ** y
        ):
            return y
    return None


def build_planning(
    plan: PlanInput | None, asset_weights: dict[str, float], portfolio_value: float, as_of: date
) -> dict[str, Any]:
    """The `planning` block of a report. Always present; `available` says whether a plan exists."""
    profile = score_risk(plan.risk_answers) if plan else None
    eq = equity_share(asset_weights)
    rate = expected_return(asset_weights)
    goals = [project_goal(g, portfolio_value, rate, as_of) for g in (plan.goals if plan else [])]
    goals.sort(key=lambda g: g["target_date"])
    return {
        "available": bool(profile or goals),
        "profile": profile,
        "equity_share": eq,
        "in_range": (profile["equity_min"] <= eq <= profile["equity_max"]) if profile else None,
        "goals": goals,
        "goals_on_track": sum(1 for g in goals if g["status"] == "on_track"),
        "assumptions": {
            "expected_return": EXPECTED_RETURN,
            "inflation": INFLATION,
            "portfolio_expected_return": rate,
            "note": "Planning assumptions, not forecasts. The expected return comes from the portfolio's "
            "current asset mix; hybrid funds count as half equity.",
        },
    }
