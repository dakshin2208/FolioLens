"""Loads a portfolio's data from the database, runs the engine and saves a snapshot."""

import logging
import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.planning import Goal, PlanInput
from app.analytics.types import Constituents, InstrumentInfo, LedgerTxn, PortfolioInput
from app.config import CALC_VERSION, get_settings
from app.insights.llm import explain_findings, explain_summary
from app.market_data.models import FundConstituent, Price
from app.planning.models import ClientPlan
from app.portfolio.models import Instrument, InstrumentType, Transaction
from app.reports.engine import build_report
from app.reports.models import AnalyticsSnapshot

log = logging.getLogger(__name__)


def _info(i: Instrument) -> InstrumentInfo:
    return InstrumentInfo(
        id=str(i.id),
        name=i.name,
        type=i.type.value,
        asset_class=i.asset_class.value,
        isin=i.isin,
        sector=i.sector,
        market_cap=i.market_cap,
        is_liquid=i.is_liquid,
        category=i.category,
    )


def _benchmark(db: Session) -> Instrument | None:
    symbol = get_settings().benchmark_symbol
    inst = db.scalar(
        select(Instrument).where(Instrument.type == InstrumentType.INDEX, Instrument.symbol == symbol)
    )
    return inst or db.scalar(select(Instrument).where(Instrument.type == InstrumentType.INDEX))


def plan_from_row(answers: dict[str, Any], goals: list[dict[str, Any]]) -> PlanInput:
    return PlanInput(
        risk_answers={k: int(v) for k, v in (answers or {}).items()},
        goals=[
            Goal(
                id=str(g["id"]),
                name=str(g["name"]),
                target_amount=float(g["target_amount"]),
                target_date=date.fromisoformat(str(g["target_date"])),
                monthly_sip=float(g.get("monthly_sip") or 0),
                share_of_portfolio=float(g.get("share_of_portfolio") or 0),
            )
            for g in goals or []
        ],
    )


def load_input(db: Session, portfolio_id: uuid.UUID) -> tuple[PortfolioInput, int]:
    rows = db.scalars(select(Transaction).where(Transaction.portfolio_id == portfolio_id)).all()
    unmatched = sum(1 for t in rows if t.instrument_id is None)
    matched = [t for t in rows if t.instrument_id is not None]
    ids = {t.instrument_id for t in matched}

    instruments = (
        {str(i.id): _info(i) for i in db.scalars(select(Instrument).where(Instrument.id.in_(ids)))}
        if ids
        else {}
    )
    prices: dict[str, dict[date, float]] = {k: {} for k in instruments}
    if ids:
        for p in db.scalars(select(Price).where(Price.instrument_id.in_(ids))):
            prices[str(p.instrument_id)][p.date] = float(p.close)

    constituents: dict[str, Constituents] = {}
    fund_ids = [i for i in ids if instruments[str(i)].type in ("mutual_fund", "etf")]
    if fund_ids:
        latest = (
            select(FundConstituent.fund_id, func.max(FundConstituent.as_of).label("as_of"))
            .where(FundConstituent.fund_id.in_(fund_ids))
            .group_by(FundConstituent.fund_id)
            .subquery()
        )
        cons_rows = db.scalars(
            select(FundConstituent).join(
                latest,
                (FundConstituent.fund_id == latest.c.fund_id) & (FundConstituent.as_of == latest.c.as_of),
            )
        ).all()
        grouped: dict[str, dict[str, float]] = {}
        as_of: dict[str, date] = {}
        stock_ids = {c.stock_id for c in cons_rows}
        for c in cons_rows:
            grouped.setdefault(str(c.fund_id), {})[str(c.stock_id)] = float(c.weight)
            as_of[str(c.fund_id)] = c.as_of
        constituents = {f: Constituents(as_of[f], w) for f, w in grouped.items()}
        for s in db.scalars(select(Instrument).where(Instrument.id.in_(stock_ids - ids))):
            instruments[str(s.id)] = _info(s)

    bench = _benchmark(db)
    bench_prices = {}
    if bench:
        bench_prices = {
            p.date: float(p.close) for p in db.scalars(select(Price).where(Price.instrument_id == bench.id))
        }
    sources = (
        sorted(
            {p for (p,) in db.execute(select(Price.source).where(Price.instrument_id.in_(ids)).distinct())}
        )
        if ids
        else []
    )

    plan_row = db.get(ClientPlan, portfolio_id)
    plan = plan_from_row(plan_row.risk_answers, plan_row.goals) if plan_row else None

    ledger = [
        LedgerTxn(str(t.instrument_id), t.date, t.type.value, float(t.units), float(t.amount))
        for t in matched
    ]
    return PortfolioInput(
        instruments=instruments,
        transactions=ledger,
        prices=prices,
        constituents=constituents,
        benchmark_name=bench.name if bench else None,
        benchmark_prices=bench_prices,
        data_sources=sources,
        plan=plan,
    ), unmatched


def refresh_report(db: Session, portfolio_id: uuid.UUID) -> AnalyticsSnapshot:
    inp, unmatched = load_input(db, portfolio_id)
    if not inp.transactions:
        report: dict[str, Any] = {
            "status": "empty",
            "message": "No matched transactions yet. Upload a statement.",
        }
    else:
        try:
            report = build_report(inp)
            report["findings"] = explain_findings(report["findings"])
            report["summary"] = explain_summary(report["summary"])
            report["status"] = "ok"
        except ValueError as e:
            log.warning("Report failed for %s: %s", portfolio_id, e)
            report = {"status": "error", "message": f"Report could not be built: {e}"}
    if unmatched and report.get("status") == "ok":
        report["data_quality"].insert(
            0,
            {
                "level": "warning",
                "message": f"{unmatched} "
                "transactions are not matched to an instrument and "
                "are excluded. Resolve them in Import & review.",
            },
        )
    vdate = report.get("meta", {}).get("valuation_date")
    snap = AnalyticsSnapshot(
        portfolio_id=portfolio_id,
        calc_version=CALC_VERSION,
        valuation_date=date.fromisoformat(vdate) if vdate else None,
        report=report,
    )
    db.add(snap)
    db.commit()
    return snap


def latest_snapshot(db: Session, portfolio_id: uuid.UUID) -> AnalyticsSnapshot | None:
    return db.scalar(
        select(AnalyticsSnapshot)
        .where(AnalyticsSnapshot.portfolio_id == portfolio_id)
        .order_by(AnalyticsSnapshot.created_at.desc())
        .limit(1)
    )
