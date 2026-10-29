"""Client risk profile and goals. Saving a plan does not rebuild the report by itself; the
frontend asks for a refresh right after, so the advisor sees the update happen."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics.planning import EXPECTED_RETURN, INFLATION, RISK_BANDS, RISK_QUESTIONS, score_risk
from app.audit.service import record_audit
from app.db import get_db
from app.identity.deps import get_current_user
from app.identity.models import User
from app.planning.models import ClientPlan
from app.planning.schemas import PlanIn, PlanOut
from app.portfolio.models import Portfolio
from app.portfolio.router import get_owned_portfolio

router = APIRouter(tags=["planning"])


@router.get("/risk-questions")
def risk_questions() -> dict[str, Any]:
    return {
        "questions": RISK_QUESTIONS,
        "bands": [
            {"name": n, "from_score": s, "equity_min": lo, "equity_max": hi} for n, s, lo, hi in RISK_BANDS
        ],
        "assumptions": {"expected_return": EXPECTED_RETURN, "inflation": INFLATION},
    }


def _out(plan: ClientPlan | None) -> PlanOut:
    if plan is None:
        return PlanOut()
    return PlanOut(
        risk_answers=plan.risk_answers,
        goals=plan.goals,
        profile=score_risk(plan.risk_answers),
        updated_at=plan.updated_at,
    )


@router.get("/portfolios/{portfolio_id}/plan", response_model=PlanOut)
def get_plan(p: Portfolio = Depends(get_owned_portfolio), db: Session = Depends(get_db)) -> PlanOut:
    return _out(db.get(ClientPlan, p.id))


@router.put("/portfolios/{portfolio_id}/plan", response_model=PlanOut)
def save_plan(
    body: PlanIn,
    p: Portfolio = Depends(get_owned_portfolio),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanOut:
    plan = db.get(ClientPlan, p.id) or ClientPlan(portfolio_id=p.id)
    plan.risk_answers = dict(body.risk_answers)
    plan.goals = [g.model_dump(mode="json") for g in body.goals]
    db.add(plan)
    record_audit(db, user.id, "plan.save", "portfolio", p.id)
    db.commit()
    db.refresh(plan)
    return _out(plan)
