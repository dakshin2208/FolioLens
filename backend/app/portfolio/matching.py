"""Map identifiers from a statement to the instrument master (PRD D-06).

- Exact ISIN match: automatic.
- Exact symbol match for stocks/ETFs: automatic.
- Name similarity >= 0.90: offered as a suggestion only; the user must confirm.
- Anything else: sent to review. Nothing is guessed.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.portfolio.models import Instrument, InstrumentType

SUGGESTION_THRESHOLD = 0.90


@dataclass
class Suggestion:
    instrument_id: str
    name: str
    score: float


# Words that describe the plan or option, not the scheme. CAS statements print names like
# "X Fund - Direct Plan - Growth", while masters may store "X Fund".
_DROP_WORDS = {
    "fund",
    "plan",
    "option",
    "the",
    "ltd",
    "limited",
    "direct",
    "regular",
    "growth",
    "idcw",
    "dividend",
    "payout",
    "reinvestment",
    "reinvest",
}


def _normalise(name: str) -> str:
    cleaned = name.lower().replace("-", " ").replace("(", " ").replace(")", " ")
    return " ".join(w for w in cleaned.split() if w not in _DROP_WORDS)


def match_identifier(db: Session, identifier: str, symbol: str | None) -> Instrument | None:
    inst = db.scalar(select(Instrument).where(Instrument.isin == identifier.upper()))
    if inst:
        return inst
    sym = (symbol or identifier).upper()
    return db.scalar(
        select(Instrument).where(
            func.upper(Instrument.symbol) == sym,
            Instrument.type.in_([InstrumentType.STOCK, InstrumentType.ETF]),
        )
    )


def suggest(db: Session, raw_name: str | None, limit_candidates: int = 20000) -> Suggestion | None:
    if not raw_name:
        return None
    target = _normalise(raw_name)
    best: Suggestion | None = None
    rows = db.execute(
        select(Instrument.id, Instrument.name)
        .where(Instrument.type != InstrumentType.INDEX)
        .limit(limit_candidates)
    )
    for iid, name in rows:
        score = SequenceMatcher(None, target, _normalise(name)).ratio()
        if score >= SUGGESTION_THRESHOLD and (best is None or score > best.score):
            best = Suggestion(str(iid), name, round(score, 3))
    return best
