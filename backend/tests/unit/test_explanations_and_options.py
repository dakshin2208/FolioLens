"""V1.1: what helped / hurt, tax estimates, options to discuss and the plain-English summary."""

from datetime import date

import pytest

from app.analytics.attribution import index_equivalent_xirr
from app.analytics.tax import EQUITY_LTCG_EXEMPTION, estimate_sale, fifo_lots
from app.analytics.types import LedgerTxn
from app.config import Settings
from app.demo.data import build_demo_input
from app.insights.llm import _summary_evidence, explain_summary
from app.insights.validation import validate_explanation
from app.reports.engine import build_report


@pytest.fixture(scope="module")
def report():
    return build_report(build_demo_input())


# ------------------------------------------------------------------------------------- tax


def test_fifo_sells_oldest_units_first():
    txns = [
        LedgerTxn("f", date(2024, 1, 1), "buy", 100, 1000),  # 10 per unit
        LedgerTxn("f", date(2025, 6, 1), "buy", 100, 2000),  # 20 per unit
        LedgerTxn("f", date(2025, 7, 1), "sell", 50, 1250),
    ]
    lots = fifo_lots(txns)["f"]
    assert [(lot.bought, lot.units) for lot in lots] == [(date(2024, 1, 1), 50), (date(2025, 6, 1), 100)]


def test_equity_sale_splits_short_and_long_term():
    txns = [
        LedgerTxn("f", date(2024, 1, 1), "buy", 100, 1000),
        LedgerTxn("f", date(2026, 6, 1), "buy", 100, 2000),
    ]
    est = estimate_sale(fifo_lots(txns)["f"], 200, 30.0, date(2026, 10, 1), "equity")
    assert est.long_term_gain == pytest.approx(100 * 30 - 1000)  # held > 12 months
    assert est.short_term_gain == pytest.approx(100 * 30 - 2000)
    assert est.tax_if_exemption_used == pytest.approx(1000 * 0.20 + 2000 * 0.125)
    # 2,000 of long-term gain is below the 1.25 lakh exemption
    assert est.tax_if_exemption_unused == pytest.approx(1000 * 0.20)


def test_large_long_term_gain_uses_exemption_once():
    txns = [LedgerTxn("f", date(2020, 1, 1), "buy", 1000, 100_000)]
    est = estimate_sale(fifo_lots(txns)["f"], 1000, 400.0, date(2026, 10, 1), "equity")
    assert est.long_term_gain == pytest.approx(300_000)
    assert est.tax_if_exemption_unused == pytest.approx((300_000 - EQUITY_LTCG_EXEMPTION) * 0.125)


def test_non_equity_shows_gain_but_never_guesses_a_rate():
    txns = [LedgerTxn("d", date(2024, 1, 1), "buy", 100, 1000)]
    est = estimate_sale(fifo_lots(txns)["d"], 100, 12.0, date(2026, 10, 1), "debt")
    assert est.gain == pytest.approx(200)
    assert est.tax_if_exemption_unused is None and est.tax_if_exemption_used is None


def test_loss_means_no_tax():
    txns = [LedgerTxn("f", date(2024, 1, 1), "buy", 100, 1000)]
    est = estimate_sale(fifo_lots(txns)["f"], 100, 8.0, date(2026, 10, 1), "equity")
    assert est.gain == pytest.approx(-200)
    assert est.tax_if_exemption_used == 0


# ------------------------------------------------------------------------------ attribution


def test_index_equivalent_matches_index_return_for_one_purchase():
    prices = {date(2024, 1, 1): 100.0, date(2025, 1, 1): 110.0}
    r = index_equivalent_xirr([(date(2024, 1, 1), -1000.0)], prices, date(2025, 1, 1))
    assert r == pytest.approx(0.10 * 365 / 366 + 0.10 * (1 - 365 / 366), abs=2e-3)  # 2024 is a leap year


def test_profit_contributions_add_up_to_total_profit(report):
    c = report["contribution"]
    o = report["overview"]
    assert c["total_profit"] == pytest.approx(o["current_value"] - o["net_invested"], rel=1e-9)
    shares = [i["share_of_profit"] for i in c["items"]]
    assert sum(shares) == pytest.approx(1.0)


def test_helped_and_hurt_are_ordered(report):
    items = {i["instrument_id"]: i for i in report["contribution"]["items"]}
    helped = [items[i]["profit"] for i in report["contribution"]["helped"]]
    assert helped == sorted(helped, reverse=True)
    for iid in report["contribution"]["hurt"]:
        assert items[iid]["profit"] < 0 or items[iid]["vs_index"] < 0


# --------------------------------------------------------------------------------- options


def test_every_finding_has_options_with_numbers(report):
    for f in report["findings"]:
        assert f["options"], f["type"]
        for o in f["options"]:
            assert o["title"] and o["summary"] and o["impact"]


def test_overlap_option_moves_the_lower_return_fund(report):
    f = next(x for x in report["findings"] if x["type"] == "fund_overlap")
    merge = f["options"][0]
    holdings = {h["name"]: h for h in report["holdings"]}
    a, b = (holdings[n] for n in f["instruments"])
    keep = a if a["xirr"] >= b["xirr"] else b
    assert keep["name"] in merge["title"]
    assert merge["tax"]["proceeds"] == pytest.approx((b if keep is a else a)["value"])


def test_trimming_a_stock_never_sells_more_than_is_held(report):
    f = next(x for x in report["findings"] if x["type"] == "single_stock_concentration")
    trim = f["options"][0]
    amount = next(i["value"] for i in trim["impact"] if i["label"] == "Amount to sell")
    assert amount <= f["evidence"]["direct_value"] + 1e-6


# --------------------------------------------------------------------------------- summary


def test_template_summary_passes_the_llm_validator(report):
    """The template must satisfy the same number check the LLM text has to pass."""
    s = report["summary"]
    ok, reason = validate_explanation(s["text"], _summary_evidence(s["facts"]))
    assert ok, reason


def test_summary_falls_back_to_template_without_llm(report):
    out = explain_summary(report["summary"], Settings(llm_provider="none"))
    assert out["source"] == "template"
    assert out["text"] == report["summary"]["text"]


def test_summary_rejects_invented_numbers(report):
    bad = "The portfolio is worth Rs 99,99,999 and returned 42.0% a year."
    ok, _ = validate_explanation(bad, _summary_evidence(report["summary"]["facts"]))
    assert not ok
