from app.config import Settings
from app.demo.data import build_demo_input
from app.insights import llm
from app.insights.llm import explain_findings
from app.insights.templates import template_explanation
from app.insights.validation import validate_explanation
from app.reports.engine import build_report

FINDING = {
    "id": "sector-IT",
    "type": "sector_concentration",
    "title": "IT is large",
    "measured_value": 0.3412,
    "threshold": 0.30,
    "unit": "percent",
    "instruments": [],
    "data_date": "2026-10-09",
    "evidence": {"sector": "IT", "value": 812345.67},
}


def test_accepts_numbers_from_evidence():
    ok, _ = validate_explanation("IT is 34.1% of equity, above the 30% guide.", FINDING)
    assert ok


def test_rejects_invented_numbers():
    ok, reason = validate_explanation("IT is 34.1% and could fall 25% next year.", FINDING)
    assert not ok and "25%" in reason


def test_rejects_trade_instructions():
    ok, reason = validate_explanation("You should sell some IT funds at 34.1%.", FINDING)
    assert not ok and "trade" in reason


def test_templates_pass_their_own_validation():
    report = build_report(build_demo_input())
    for f in report["findings"]:
        ok, reason = validate_explanation(template_explanation(f), f)
        assert ok, (f["type"], reason)


def test_without_llm_everything_uses_templates():
    report = build_report(build_demo_input())
    out = explain_findings(report["findings"], Settings(llm_provider="none"))
    assert all(f["explanation_source"] == "template" and f["explanation"] for f in out)


def test_invalid_llm_output_falls_back(monkeypatch):
    finding = dict(FINDING)
    fake = '{"explanations": [{"id": "sector-IT", "text": "IT is 99% of everything."}]}'
    monkeypatch.setitem(llm.PROVIDERS, "anthropic", lambda s, u: fake)
    s = Settings(llm_provider="anthropic", llm_api_key="k" * 20, llm_model="m")
    [f] = explain_findings([finding], s)
    assert f["explanation_source"] == "template"


def test_valid_llm_output_is_used(monkeypatch):
    finding = dict(FINDING)
    fake = '{"explanations": [{"id": "sector-IT", "text": "IT is 34.1% of equity."}]}'
    monkeypatch.setitem(llm.PROVIDERS, "anthropic", lambda s, u: fake)
    s = Settings(llm_provider="anthropic", llm_api_key="k" * 20, llm_model="m")
    [f] = explain_findings([finding], s)
    assert f["explanation_source"] == "llm"


def test_provider_error_falls_back(monkeypatch):
    def boom(s, u):
        raise TimeoutError

    monkeypatch.setitem(llm.PROVIDERS, "openai", boom)
    s = Settings(llm_provider="openai", llm_api_key="k" * 20, llm_model="m")
    [f] = explain_findings([dict(FINDING)], s)
    assert f["explanation_source"] == "template"


def test_azure_openai_request_shape(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            text = '{"explanations": [{"id": "sector-IT", "text": "IT is 34.1% of equity."}]}'
            return {"choices": [{"message": {"content": text}}]}

    def fake_post(url, headers, json, timeout):
        captured.update(url=url, headers=headers, body=json)
        return FakeResponse()

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    s = Settings(
        llm_provider="azure_openai",
        llm_api_key="k" * 30,
        llm_model="my-deploy",
        llm_endpoint="https://res.openai.azure.com/",
    )
    [f] = explain_findings([dict(FINDING)], s)
    assert f["explanation_source"] == "llm"
    assert captured["url"] == (
        "https://res.openai.azure.com/openai/deployments/my-deploy/chat/completions?api-version=2024-10-21"
    )
    assert captured["headers"] == {"api-key": "k" * 30}


OVERLAP = {
    "id": "overlap-a-b",
    "type": "fund_overlap",
    "title": "Two funds overlap",
    "measured_value": 0.81,
    "threshold": 0.5,
    "unit": "percent",
    "instruments": ["Fund A", "Fund B"],
    "data_date": "2026-09-30",
    "evidence": {"shared_stocks": 12},
}


def test_fraction_written_as_percent_is_rejected():
    # The real failure seen with a live model: 0.81 written as "0.8%".
    ok, reason = validate_explanation("The funds overlap by 0.8%, above 0.5%.", OVERLAP)
    assert not ok and "0.8%" in reason


def test_correct_percentages_and_dates_from_the_finding_pass():
    text = (
        "Fund A and Fund B overlap by 81.0%, above the 50.0% threshold, with 12 shared "
        "stocks as of 2026-09-30 (30 September 2026)."
    )
    assert validate_explanation(text, OVERLAP) == (True, None)


def test_dates_not_in_the_finding_are_rejected():
    ok, _ = validate_explanation("Overlap was 81.0% on 2025-01-31.", OVERLAP)
    assert not ok


def test_payload_sends_formatted_facts_not_raw_fractions():
    import json

    [item] = json.loads(llm._payload([OVERLAP]))
    assert item["facts"]["measured"] == "81.0%"
    assert item["facts"]["review_threshold"] == "50.0%"
    assert "measured_value" not in item
    assert llm._indian_rupees(716229.4) == "Rs 7,16,229"


def test_rejected_reply_is_retried_with_feedback(monkeypatch):
    calls = []

    def fake(s, user):
        calls.append(user)
        if len(calls) == 1:  # first answer repeats the real live mistake
            return '{"explanations": [{"id": "overlap-a-b", "text": "Overlap is 0.8%."}]}'
        return (
            '{"explanations": [{"id": "overlap-a-b", "text": '
            '"Fund A and Fund B overlap by 81.0%, above the 50.0% threshold."}]}'
        )

    monkeypatch.setitem(llm.PROVIDERS, "openai", fake)
    s = Settings(llm_provider="openai", llm_api_key="k" * 20, llm_model="m")
    [f] = explain_findings([dict(OVERLAP)], s)
    assert f["explanation_source"] == "llm" and "81.0%" in f["explanation"]
    assert len(calls) == 2 and "0.8%" in calls[1] and "rejected" in calls[1]


def test_still_wrong_after_retry_uses_template(monkeypatch):
    monkeypatch.setitem(
        llm.PROVIDERS,
        "openai",
        lambda s, u: '{"explanations": [{"id": "overlap-a-b", "text": "Overlap is 0.8%."}]}',
    )
    s = Settings(llm_provider="openai", llm_api_key="k" * 20, llm_model="m")
    [f] = explain_findings([dict(OVERLAP)], s)
    assert f["explanation_source"] == "template" and "81.0%" in f["explanation"]
