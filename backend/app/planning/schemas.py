import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.analytics.planning import RISK_QUESTIONS

QUESTION_IDS = {q["id"] for q in RISK_QUESTIONS}


class GoalIn(BaseModel):
    id: str | None = Field(default=None, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    target_amount: float = Field(gt=0, le=1e11)  # today's rupees
    target_date: date
    monthly_sip: float = Field(default=0, ge=0, le=1e9)
    share_of_portfolio: float = Field(default=0, ge=0, le=1)

    @field_validator("target_date")
    @classmethod
    def _sensible_date(cls, v: date) -> date:
        if v.year < 2000 or v.year > 2100:
            raise ValueError("target date must be between 2000 and 2100")
        return v


class PlanIn(BaseModel):
    risk_answers: dict[str, int] = {}
    goals: list[GoalIn] = Field(default=[], max_length=10)

    @field_validator("risk_answers")
    @classmethod
    def _answers(cls, v: dict[str, int]) -> dict[str, int]:
        for k, a in v.items():
            if k not in QUESTION_IDS:
                raise ValueError(f"unknown question {k}")
            if not 0 <= a <= 4:
                raise ValueError("each answer is an option number from 0 to 4")
        return v

    @model_validator(mode="after")
    def _shares(self) -> "PlanIn":
        if sum(g.share_of_portfolio for g in self.goals) > 1 + 1e-9:
            raise ValueError("goals cannot set aside more than 100% of the portfolio in total")
        for g in self.goals:
            g.id = g.id or uuid.uuid4().hex[:12]
        return self


class PlanOut(PlanIn):
    profile: dict[str, Any] | None = None
    updated_at: datetime | None = None
