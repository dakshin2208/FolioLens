"""Loaders for reference and market data.

Sources (verify each source's current terms before production use, PRD section 5):
- AMFI NAV files (latest NAVAll.txt and the historical NAV report) -> mutual fund master + NAVs
- NSE equity bhavcopy CSV (UDiFF or legacy layout) -> stock master + closing prices
- Index history CSV (e.g. Nifty 50 TRI export) -> benchmark prices
- Fund constituents CSV, prepared from AMC monthly portfolio disclosures
- Stock metadata CSV -> sector and market-cap classification
"""

import csv
import io
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.market_data.models import FundConstituent, Price
from app.portfolio.models import AssetClass, Instrument, InstrumentType

BATCH = 5000


def _asset_class_from_category(category: str, name: str) -> tuple[AssetClass, bool]:
    c, n = category.lower(), name.lower()
    liquid = any(k in c for k in ("liquid", "overnight", "money market"))
    if "gold" in c or "gold" in n:
        return AssetClass.GOLD, False
    if "equity" in c or "elss" in c:
        return AssetClass.EQUITY, False
    if "debt" in c or "income" in c or "gilt" in c:
        return AssetClass.DEBT, liquid
    if "hybrid" in c or "balanced" in c or "arbitrage" in c:
        return AssetClass.HYBRID, False
    if "index" in c or "etf" in c:
        return AssetClass.EQUITY, False
    return AssetClass.OTHER, liquid


def _parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%d/%m/%Y", "%d-%B-%Y", "%d %B %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date: {value}")


def _upsert_instruments(db: Session, rows: list[dict[str, Any]]) -> dict[str, uuid.UUID]:
    """Insert or update instruments by ISIN; return ISIN -> id."""
    out: dict[str, uuid.UUID] = {}
    for i in range(0, len(rows), BATCH):
        chunk = rows[i : i + BATCH]
        stmt = insert(Instrument).values(chunk)
        update_cols = {k: stmt.excluded[k] for k in chunk[0] if k not in ("id", "isin")}
        stmt = stmt.on_conflict_do_update(index_elements=["isin"], set_=update_cols)
        db.execute(stmt)
    isins = [r["isin"] for r in rows]
    for i in range(0, len(isins), BATCH):
        for isin, iid in db.execute(
            select(Instrument.isin, Instrument.id).where(Instrument.isin.in_(isins[i : i + BATCH]))
        ):
            if isin:
                out[isin] = iid
    return out


def _upsert_prices(db: Session, rows: list[dict[str, Any]]) -> int:
    for i in range(0, len(rows), BATCH):
        stmt = insert(Price).values(rows[i : i + BATCH])
        stmt = stmt.on_conflict_do_update(
            index_elements=["instrument_id", "date"],
            set_={"close": stmt.excluded.close, "source": stmt.excluded.source},
        )
        db.execute(stmt)
    return len(rows)


def load_amfi_nav(db: Session, text: str, source: str = "AMFI") -> tuple[int, int]:
    """Parse AMFI's semicolon-separated NAV text (latest or historical report).

    Category headers such as 'Open Ended Schemes(Equity Scheme - Large Cap Fund)' set the
    category of the scheme lines that follow them.
    """
    header: list[str] | None = None
    category = ""
    instruments: dict[str, dict[str, Any]] = {}
    navs: list[tuple[str, date, Decimal]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ";" not in line:
            if "Scheme" in line and "(" in line:
                category = line[line.find("(") + 1 : line.rfind(")")] or line
            continue
        parts = [p.strip() for p in line.split(";")]
        if header is None and parts[0].lower().startswith("scheme code"):
            header = [p.lower() for p in parts]
            continue
        if header is None:
            continue
        row = dict(zip(header, parts, strict=False))
        name = row.get("scheme name", "")
        nav_raw = row.get("net asset value", "")
        try:
            nav = Decimal(nav_raw)
            nav_date = _parse_date(row.get("date", ""))
        except (InvalidOperation, ValueError):
            continue  # "N.A." NAVs and malformed lines are skipped
        asset_class, liquid = _asset_class_from_category(category, name)
        isin_cols = [k for k in header if k.startswith("isin")]
        for col in isin_cols:
            isin = row.get(col, "")
            if len(isin) == 12 and isin.startswith("IN"):
                instruments[isin] = {
                    "id": uuid.uuid4(),
                    "type": InstrumentType.MUTUAL_FUND,
                    "isin": isin,
                    "amfi_code": row.get("scheme code"),
                    "name": name[:255],
                    "asset_class": asset_class,
                    "category": category[:120] or None,
                    "is_liquid": liquid,
                }
                navs.append((isin, nav_date, nav))
    ids = _upsert_instruments(db, list(instruments.values())) if instruments else {}
    count = _upsert_prices(
        db,
        [{"instrument_id": ids[i], "date": d, "close": n, "source": source} for i, d, n in navs if i in ids],
    )
    db.commit()
    return len(instruments), count


def load_nse_bhavcopy(db: Session, text: str, source: str = "NSE bhavcopy") -> tuple[int, int]:
    """Equity closing prices. Supports the UDiFF layout and the legacy CM bhavcopy layout."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    cols = {c.strip().lower(): c for c in reader.fieldnames or []}

    def col(*names: str) -> str | None:
        return next((cols[n] for n in names if n in cols), None)

    c_sym, c_isin = col("tckrsymb", "symbol"), col("isin")
    c_series, c_close = col("sctysrs", "series"), col("clspric", "close")
    c_date, c_name = col("traddt", "timestamp", "date1"), col("fininstrmnm")
    if not (c_sym and c_isin and c_close and c_date):
        raise ValueError("Unrecognised bhavcopy layout (need symbol, ISIN, close and date)")
    instruments: dict[str, dict[str, Any]] = {}
    prices = []
    for r in reader:
        if c_series and r[c_series].strip() not in ("EQ", "BE", "BZ"):
            continue
        isin = r[c_isin].strip()
        if len(isin) != 12:
            continue
        instruments[isin] = {
            "id": uuid.uuid4(),
            "type": InstrumentType.STOCK,
            "isin": isin,
            "symbol": r[c_sym].strip(),
            "name": (r[c_name].strip() if c_name else r[c_sym].strip())[:255],
            "asset_class": AssetClass.EQUITY,
        }
        prices.append((isin, _parse_date(r[c_date]), Decimal(r[c_close].strip())))
    if not instruments:
        return 0, 0
    # Keep sector/market cap that may already be loaded: only update symbol and name.
    rows = list(instruments.values())
    stmt = insert(Instrument).values(rows)
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["isin"], set_={"symbol": stmt.excluded.symbol, "name": stmt.excluded.name}
        )
    )
    ids = dict(
        db.execute(select(Instrument.isin, Instrument.id).where(Instrument.isin.in_(list(instruments)))).all()
    )
    count = _upsert_prices(
        db, [{"instrument_id": ids[i], "date": d, "close": c, "source": source} for i, d, c in prices]
    )
    db.commit()
    return len(instruments), count


def load_index_history(
    db: Session,
    text: str,
    symbol: str,
    name: str,
    date_col: str,
    value_col: str,
    source: str,
) -> int:
    inst = db.scalar(
        select(Instrument).where(Instrument.type == InstrumentType.INDEX, Instrument.symbol == symbol)
    )
    if inst is None:
        inst = Instrument(type=InstrumentType.INDEX, symbol=symbol, name=name, asset_class=AssetClass.EQUITY)
        db.add(inst)
        db.flush()
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    rows = []
    for r in reader:
        r = {k.strip(): v for k, v in r.items() if k}
        try:
            rows.append(
                {
                    "instrument_id": inst.id,
                    "date": _parse_date(r[date_col]),
                    "close": Decimal(r[value_col].replace(",", "").strip()),
                    "source": source,
                }
            )
        except (KeyError, ValueError, InvalidOperation):
            continue
    count = _upsert_prices(db, rows)
    db.commit()
    return count


def load_constituents(db: Session, text: str, source: str) -> int:
    """CSV columns: fund_isin, stock_isin, weight, as_of. Weight may be a fraction (0.084)
    or a percentage (8.4); values above 1 are treated as percentages."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    isins: set[str] = set()
    raw = []
    for r in reader:
        w = Decimal(r["weight"].strip())
        raw.append(
            (
                r["fund_isin"].strip(),
                r["stock_isin"].strip(),
                w / 100 if w > 1 else w,
                _parse_date(r["as_of"]),
            )
        )
        isins.update((r["fund_isin"].strip(), r["stock_isin"].strip()))
    ids = dict(db.execute(select(Instrument.isin, Instrument.id).where(Instrument.isin.in_(isins))).all())
    missing = isins - ids.keys()
    if missing:
        raise ValueError(f"Unknown ISINs (load the instrument master first): {sorted(missing)[:10]}")
    rows = [
        {"fund_id": ids[f], "stock_id": ids[s], "as_of": d, "weight": w, "source": source}
        for f, s, w, d in raw
    ]
    for i in range(0, len(rows), BATCH):
        stmt = insert(FundConstituent).values(rows[i : i + BATCH])
        db.execute(
            stmt.on_conflict_do_update(
                index_elements=["fund_id", "stock_id", "as_of"],
                set_={"weight": stmt.excluded.weight, "source": stmt.excluded.source},
            )
        )
    db.commit()
    return len(rows)


def load_stock_metadata(db: Session, text: str) -> int:
    """CSV columns: isin, sector, market_cap (large / mid / small)."""
    n = 0
    for r in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        inst = db.scalar(select(Instrument).where(Instrument.isin == r["isin"].strip()))
        if inst:
            inst.sector = r.get("sector", "").strip() or None
            inst.market_cap = r.get("market_cap", "").strip().lower() or None
            n += 1
    db.commit()
    return n
