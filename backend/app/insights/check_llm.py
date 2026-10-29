"""Checks the LLM settings in .env with one small request. Never prints the API key.

docker compose run --rm api python -m app.insights.check_llm
"""

import sys

import httpx

from app.config import get_settings
from app.demo.data import build_demo_input
from app.insights import llm
from app.insights.llm import explain_findings
from app.reports.engine import build_report


def main() -> int:
    s = get_settings()
    print(f"Provider: {s.llm_provider!r}   Model: {s.llm_model!r}")
    if s.llm_provider == "none":
        print("LLM is switched off (LLM_PROVIDER=none). Reports use template explanations.")
        return 0
    if s.llm_provider not in llm.PROVIDERS:
        print(f"Unknown LLM_PROVIDER. Use one of: none, {', '.join(llm.PROVIDERS)}")
        return 1
    key = s.llm_api_key or ""
    if not key or not s.llm_model:
        print("LLM_API_KEY and LLM_MODEL must both be set.")
        return 1
    expected = {"openai": "sk-", "anthropic": "sk-ant-"}.get(s.llm_provider)
    note = ""
    if expected:
        note = f", {'expected' if key.startswith(expected) else 'UNEXPECTED'} prefix"
    print(f"API key: set, {len(key)} characters{note}")
    if s.llm_provider == "azure_openai":
        print(f"Endpoint: {s.llm_endpoint}  Deployment: {s.llm_model}  API version: {s.llm_api_version}")

    finding = build_report(build_demo_input())["findings"][0]
    try:
        text = llm.PROVIDERS[s.llm_provider](s, llm._payload([finding]))
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("error", {})
            detail = detail.get("message", detail) if isinstance(detail, dict) else detail
        except ValueError:
            detail = e.response.text[:200]
        code = e.response.status_code
        print(f"FAILED: HTTP {code}: {detail}")
        hints = {
            401: "The API key is wrong. In Azure use 'Key 1' from your resource's Keys and Endpoint page.",
            403: "The key is valid but not allowed to use this resource or deployment.",
            404: "The deployment (LLM_MODEL) or endpoint (LLM_ENDPOINT) does not exist. "
            "Copy the exact deployment name from the Azure portal.",
            429: "Rate limit or quota reached. Wait a minute or raise the quota in Azure.",
        }
        if code in hints:
            print("HINT: " + hints[code])
        elif code == 400:
            print("HINT: check LLM_API_VERSION, or whether this model supports JSON output.")
        return 1
    except ValueError as e:
        print(f"FAILED: {e}")
        return 1
    except httpx.HTTPError as e:
        print(f"FAILED: could not reach the provider ({type(e).__name__}). Check your internet.")
        return 1

    try:
        llm._parse(text)
    except (ValueError, KeyError):
        print("FAILED: the model replied, but not in the expected JSON format.")
        return 1
    print("Connection OK. Now explaining every demo finding exactly as the app does...")

    findings = build_report(build_demo_input())["findings"]
    explain_findings(findings, s)
    ai = sum(1 for f in findings if f["explanation_source"] == "llm")
    for f in findings:
        label = "AI " if f["explanation_source"] == "llm" else "TPL"
        print(f"  [{label}] {f['title']}: {f['explanation']}")
    if ai == len(findings):
        print(f"PASSED: all {ai} findings have AI explanations that passed number validation.")
    elif ai:
        print(
            f"PASSED (partly): {ai} of {len(findings)} AI explanations accepted; "
            "the rest safely use templates."
        )
    else:
        print("AI replies were all rejected by validation; the app uses templates (still correct).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
