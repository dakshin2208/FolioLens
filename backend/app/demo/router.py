from functools import lru_cache
from typing import Any

from fastapi import APIRouter

from app.config import Settings
from app.demo.data import build_demo_input
from app.insights.llm import explain_findings
from app.reports.engine import build_report

router = APIRouter(prefix="/demo", tags=["demo"])


@lru_cache(maxsize=1)
def _demo_report() -> dict[str, Any]:
    report = build_report(build_demo_input())
    # Demo explanations always use templates: no API cost, no external calls, deterministic.
    report["findings"] = explain_findings(report["findings"], Settings(llm_provider="none"))
    report["status"] = "ok"
    report["meta"]["synthetic"] = True
    report["portfolio"] = {"name": "Demo portfolio", "client_name": "Sample Client (synthetic)"}
    return report


@router.get("/report")
def demo_report() -> dict[str, Any]:
    return _demo_report()
