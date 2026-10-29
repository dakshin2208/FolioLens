"""V1.2: risk profile, suitability, goal projections and their options."""

from datetime import date

import pytest

from app.analytics.planning import (
    INFLATION,
    RISK_QUESTIONS,
    Goal,
    PlanInput,
    _sip_factor,
    build_planning,
    equity_share,
    expected_return,
    project_goal,
    score_risk,
    years_to_reach,
)
from app.demo.data import build_demo_input
from app.insights.llm import _summary_evidence
from app.insights.validation import validate_explanation
from app.reports.engine import build_report

AS_OF = date(2026, 10, 9)


@pytest.fixture(scope="module")
def report():
    return build_report(build_demo_input())


# ------------------------------------------------------------------------- risk profile


def test_all_careful_answers_are_conservative():
    p = score_risk({q["id"]: 0 for q in RISK_QUESTIONS})
    assert p["score"] == 0 and p["category"] == "Conservative"
    assert (p["equity_min"], p["equity_max"]) == (0.10, 0.30)


def test_all_bold_answers_are_aggressive():
    p = score_risk({q["id"]: 4 for q in RISK_QUESTIONS})
    assert p["score"] == 100 and p["category"] == "Aggressive"


def test_band_edges_are_inclusive_from_below():
    # average 1.6 of 4 = score 40 -> Moderate, not Moderately conservative
    p = score_risk({"age": 2, "horizon": 2, "income": 2, "drop": 1, "experience": 1})
    assert p["score"] == pytest.approx(40) and p["category"] == "Moderate"


def test_no_answers_means_no_profile_and_bad_answers_are_ignored():
    assert score_risk({}) is None
    assert score_risk({"age": 9, "unknown": 2}) is None


def test_hybrid_counts_half_equity():
    assert equity_share({"equity": 0.5, "hybrid": 0.2, "debt": 0.3}) == pytest.approx(0.6)


def test_expected_return_is_the_weighted_mix():
    assert expected_return({"equity": 0.5, "debt": 0.5}) == pytest.approx((0.11 + 0.07) / 2)


# -------------------------------------------------------------------------------- goals


def test_sip_factor_matches_a_hand_calculation():
    # 12 monthly payments of 1 at the start of each month, 12% a year compounded yearly
    i = 1.12 ** (1 / 12) - 1
    assert _sip_factor(0.12, 12) == pytest.approx(sum((1 + i) ** k for k in range(1, 13)))
    assert _sip_factor(0.0, 24) == 24


def test_goal_with_only_a_lump_sum():
    g = Goal("g", "Car", 100_000, date(2031, 10, 9), 0, 0.5)
    out = project_goal(g, 200_000, 0.10, date(2026, 10, 9), inflation=0.0)
    years = out["years"]
    assert out["projected"] == pytest.approx(100_000 * 1.10**years)
    assert out["status"] == "on_track"


def test_required_sip_exactly_closes_the_gap():
    g = Goal("g", "House", 2_000_000, date(2033, 10, 9), 5_000, 0.1)
    out = project_goal(g, 1_000_000, 0.09, AS_OF)
    fixed = Goal("g", "House", 2_000_000, date(2033, 10, 9), out["required_sip"], 0.1)
    again = project_goal(fixed, 1_000_000, 0.09, AS_OF)
    assert again["funded_ratio"] == pytest.approx(1.0, abs=1e-9)


def test_target_grows_with_inflation():
    g = Goal("g", "Trip", 100_000, date(2036, 10, 9), 0, 0)
    out = project_goal(g, 0, 0.1, AS_OF)
    assert out["target_future"] == pytest.approx(100_000 * (1 + INFLATION) ** out["years"])


def test_years_to_reach_is_later_for_a_short_goal():
    g = Goal("g", "Home", 1_500_000, date(2028, 6, 1), 10_000, 0.15)
    out = project_goal(g, 4_378_102, 0.10, AS_OF)
    yrs = years_to_reach(g, 4_378_102, 0.10, AS_OF)
    assert out["status"] == "off_track" and yrs is not None and yrs > out["years"]


def test_planning_block_is_present_but_unavailable_without_a_plan():
    block = build_planning(None, {"equity": 1.0}, 100.0, AS_OF)
    assert block["available"] is False and block["goals"] == []
    assert build_planning(PlanInput(), {"equity": 1.0}, 100.0, AS_OF)["available"] is False


# ---------------------------------------------------------------------- in the report


def test_demo_report_flags_risk_and_goals(report):
    types = {f["type"] for f in report["findings"]}
    assert {"risk_mismatch", "goal_shortfall", "short_goal_in_equity"} <= types
    pl = report["planning"]
    assert pl["profile"]["category"] == "Moderately aggressive"
    assert pl["in_range"] is False and pl["equity_share"] > pl["profile"]["equity_max"]


def test_rebalance_brings_equity_to_the_edge_of_the_range(report):
    f = next(x for x in report["findings"] if x["type"] == "risk_mismatch")
    total = report["overview"]["current_value"]
    move = next(i["value"] for i in f["options"][0]["impact"] if i["label"] == "Amount to move")
    eq_value = f["measured_value"] * total
    assert (eq_value - move) / total == pytest.approx(f["threshold"])
    assert f["options"][0]["tax"] is not None


def test_goal_options_include_the_required_sip(report):
    f = next(x for x in report["findings"] if x["type"] == "goal_shortfall" and x["severity"] != "low")
    sip = next(o for o in f["options"] if o["id"].endswith("-sip"))
    needed = next(i["value"] for i in sip["impact"] if i["label"] == "SIP needed")
    assert needed == pytest.approx(f["evidence"]["required_sip"])


def test_summary_with_planning_still_passes_the_validator(report):
    s = report["summary"]
    assert any("goals on track" in p["text"] for p in s["points"])
    ok, reason = validate_explanation(s["text"], _summary_evidence(s["facts"]))
    assert ok, reason
