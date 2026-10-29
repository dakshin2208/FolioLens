"""Deterministic rules that flag portfolio conditions for an advisor to review.

Findings are review flags, not investment advice. Each one carries its evidence: the
measured value, the threshold, the instruments involved, the data date and limitations.
"""

from dataclasses import asdict, dataclass, field
from typing import Any

from app.analytics.planning import SHORT_GOAL_MAX_EQUITY, SHORT_GOAL_YEARS

DEFAULT_THRESHOLDS: dict[str, float] = {
    "single_stock_max": 0.10,  # of total portfolio value
    "sector_max_of_equity": 0.30,
    "fund_overlap_max": 0.50,
    "max_funds": 12,
    "min_liquid": 0.05,
    "benchmark_lag_max": 0.03,  # annualised, percentage points as a fraction
    "min_equity_for_nifty": 0.65,
}


@dataclass
class Finding:
    id: str
    type: str
    severity: str  # high / medium / low
    title: str
    measured_value: float
    threshold: float | None
    unit: str  # "percent" or "count"
    instruments: list[str]
    data_date: str | None
    calc_version: str
    evidence: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    discussion_prompts: list[str] = field(default_factory=list)
    explanation: str | None = None
    explanation_source: str | None = None  # "llm" or "template"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sev(value: float, threshold: float, high_multiple: float = 1.5) -> str:
    return "high" if value >= threshold * high_multiple else "medium"


def evaluate_rules(report: dict[str, Any], thresholds: dict[str, float] | None = None) -> list[Finding]:
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    meta = report["meta"]
    version, vdate = meta["calc_version"], meta["valuation_date"]
    findings: list[Finding] = []
    total = report["overview"]["current_value"] or 0.0
    alloc = report["allocation"]
    lt = alloc["lookthrough"]
    lt_note = (
        [f"Look-through covers {lt['coverage']:.0%} of fund value; uncovered funds are excluded."]
        if lt["coverage"] < 1
        else []
    )

    # 1. Single company concentration (direct + through funds)
    for c in alloc["top_companies"]:
        if total and c["weight"] > t["single_stock_max"]:
            findings.append(
                Finding(
                    id=f"stock-{c['instrument_id']}",
                    type="single_stock_concentration",
                    severity=_sev(c["weight"], t["single_stock_max"]),
                    title=f"High exposure to {c['name']}",
                    measured_value=c["weight"],
                    threshold=t["single_stock_max"],
                    unit="percent",
                    instruments=[c["name"]],
                    data_date=vdate,
                    calc_version=version,
                    evidence={
                        "value": c["value"],
                        "direct_value": c["direct_value"],
                        "via_funds_value": c["via_funds_value"],
                    },
                    limitations=lt_note,
                    discussion_prompts=[f"Is the client aware of the combined exposure to {c['name']}?"],
                )
            )

    # 2. Sector concentration within equity
    sector = alloc["sector"]
    if sector["items"] and lt["reliable"]:
        for s in sector["items"]:
            if s["name"] in ("Unclassified", "Cash & others in funds"):
                continue
            if s["weight_of_equity"] > t["sector_max_of_equity"]:
                findings.append(
                    Finding(
                        id=f"sector-{s['name']}",
                        type="sector_concentration",
                        severity=_sev(s["weight_of_equity"], t["sector_max_of_equity"]),
                        title=f"{s['name']} is a large share of equity",
                        measured_value=s["weight_of_equity"],
                        threshold=t["sector_max_of_equity"],
                        unit="percent",
                        instruments=[],
                        data_date=vdate,
                        calc_version=version,
                        evidence={"sector": s["name"], "value": s["value"]},
                        limitations=lt_note,
                        discussion_prompts=[
                            f"Does a weighting this large in {s['name']} match the client's plan?"
                        ],
                    )
                )

    # 3. Fund overlap
    for o in report["overlap"]:
        if o["overlap"] > t["fund_overlap_max"]:
            findings.append(
                Finding(
                    id=f"overlap-{o['fund_a_id']}-{o['fund_b_id']}",
                    type="fund_overlap",
                    severity=_sev(o["overlap"], t["fund_overlap_max"], 1.3),
                    title="Two funds hold largely the same stocks",
                    measured_value=o["overlap"],
                    threshold=t["fund_overlap_max"],
                    unit="percent",
                    instruments=[o["fund_a"], o["fund_b"]],
                    data_date=o["as_of"],
                    calc_version=version,
                    evidence={"shared_stocks": o["shared_stocks"]},
                    limitations=["Based on the latest monthly portfolio disclosures."],
                    discussion_prompts=["Do both funds serve a distinct purpose in the portfolio?"],
                )
            )

    # 4. Too many funds
    n_funds = report["overview"]["funds_count"]
    if n_funds > t["max_funds"]:
        findings.append(
            Finding(
                id="too-many-funds",
                type="too_many_funds",
                severity="low",
                title="The portfolio holds many funds",
                measured_value=n_funds,
                threshold=t["max_funds"],
                unit="count",
                instruments=[],
                data_date=vdate,
                calc_version=version,
                discussion_prompts=["Could fewer funds achieve the same diversification?"],
            )
        )

    # 5. Low liquid / cash allocation
    liquid = report["overview"]["liquid_weight"]
    if total and liquid < t["min_liquid"]:
        findings.append(
            Finding(
                id="low-liquidity",
                type="low_liquidity",
                severity="low",
                title="Little money in cash or liquid funds",
                measured_value=liquid,
                threshold=t["min_liquid"],
                unit="percent",
                instruments=[],
                data_date=vdate,
                calc_version=version,
                limitations=["Bank balances and deposits outside this portfolio are not visible."],
                discussion_prompts=["Does the client hold an emergency fund elsewhere?"],
            )
        )

    # 6. Underperformance against a compatible benchmark
    perf = report["performance"]
    if (
        perf.get("benchmark_compatible")
        and perf.get("twr_annualized") is not None
        and perf.get("benchmark_annualized") is not None
    ):
        lag = perf["benchmark_annualized"] - perf["twr_annualized"]
        if lag > t["benchmark_lag_max"]:
            findings.append(
                Finding(
                    id="benchmark-lag",
                    type="benchmark_underperformance",
                    severity="medium",
                    title=f"Returns trail {perf['benchmark_name']}",
                    measured_value=lag,
                    threshold=t["benchmark_lag_max"],
                    unit="percent",
                    instruments=[],
                    data_date=vdate,
                    calc_version=version,
                    evidence={
                        "portfolio_annualized": perf["twr_annualized"],
                        "benchmark_annualized": perf["benchmark_annualized"],
                        "period_start": perf["period_start"],
                        "period_end": perf["period_end"],
                    },
                    limitations=["Time-weighted returns; past performance does not predict future results."],
                    discussion_prompts=["Which holdings explain most of the gap?"],
                )
            )

    # 7. Portfolio risk outside the client's risk profile
    planning = report.get("planning") or {}
    prof = planning.get("profile")
    if prof and total:
        eq = planning["equity_share"]
        lo, hi = prof["equity_min"], prof["equity_max"]
        if eq > hi or eq < lo:
            edge = hi if eq > hi else lo
            above = eq > hi
            findings.append(
                Finding(
                    id="risk-profile",
                    type="risk_mismatch",
                    severity="high" if abs(eq - edge) > 0.10 else "medium",
                    title=f"{'More' if above else 'Less'} equity than a "
                    f"{prof['category'].lower()} profile suggests",
                    measured_value=eq,
                    threshold=edge,
                    unit="percent",
                    instruments=[],
                    data_date=vdate,
                    calc_version=version,
                    evidence={
                        "profile": prof["category"],
                        "equity_min": lo,
                        "equity_max": hi,
                        "risk_score": prof["score"],
                        "direction": "above" if above else "below",
                    },
                    limitations=[
                        "Risk profile from a six-question model; hybrid funds count as half equity. "
                        "Use your firm's own risk-profiling process for compliance."
                    ],
                    discussion_prompts=[
                        "Is the client comfortable with this level of risk, or has their situation changed?"
                    ],
                )
            )

    # 8. Goals that the current plan does not fully fund
    for g in planning.get("goals", []):
        if g["status"] in ("off_track", "at_risk") and g["funded_ratio"] is not None:
            off = g["status"] == "off_track"
            findings.append(
                Finding(
                    id=f"goal-{g['id']}",
                    type="goal_shortfall",
                    severity=("high" if g["funded_ratio"] < 0.6 else "medium") if off else "low",
                    title=f"{g['name']} is {'not on track' if off else 'slightly short'}",
                    measured_value=g["funded_ratio"],
                    threshold=1.0,
                    unit="percent",
                    instruments=[],
                    data_date=vdate,
                    calc_version=version,
                    evidence={
                        "goal": g["name"],
                        "target_today": g["target_today"],
                        "target_future": g["target_future"],
                        "projected": g["projected"],
                        "gap": g["gap"],
                        "monthly_sip": g["monthly_sip"],
                        "required_sip": g["required_sip"],
                        "years": g["years"],
                        "target_date": g["target_date"],
                        "expected_return": g["expected_return"],
                        "inflation": g["inflation"],
                        "set_aside": g["set_aside"],
                        "goal_id": g["id"],
                    },
                    limitations=[
                        "Projection uses planning assumptions for returns and inflation, not forecasts."
                    ],
                    discussion_prompts=[f"How important is {g['name']} and its date to the client?"],
                )
            )

    # 9. Money for a near goal held mostly in equity
    for g in planning.get("goals", []):
        eq = planning.get("equity_share", 0.0)
        if 0 < g["years"] < SHORT_GOAL_YEARS and g["set_aside"] > 0 and eq > SHORT_GOAL_MAX_EQUITY:
            findings.append(
                Finding(
                    id=f"goal-near-{g['id']}",
                    type="short_goal_in_equity",
                    severity="medium",
                    title=f"Money for {g['name']} is in equity, with under 3 years to go",
                    measured_value=eq,
                    threshold=SHORT_GOAL_MAX_EQUITY,
                    unit="percent",
                    instruments=[],
                    data_date=vdate,
                    calc_version=version,
                    evidence={
                        "goal": g["name"],
                        "years": g["years"],
                        "set_aside": g["set_aside"],
                        "target_date": g["target_date"],
                        "equity_in_set_aside": g["set_aside"] * eq,
                    },
                    limitations=["Assumes the goal's money has the same mix as the whole portfolio."],
                    discussion_prompts=["Could a market fall just before this date upset the client's plan?"],
                )
            )

    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], -f.measured_value))
    return findings
