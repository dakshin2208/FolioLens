"""CSV parsers: Zerodha Console tradebook and FolioLens's own generic template."""

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.portfolio.parsers.base import ParsedStatement, ParsedTxn, ParseError

GENERIC_COLUMNS = ["date", "isin", "symbol", "name", "type", "units", "price", "amount"]
GENERIC_TYPES = {"buy", "sell", "dividend_payout", "dividend_reinvest", "switch_in", "switch_out"}
ZERODHA_REQUIRED = {"symbol", "isin", "trade_date", "trade_type", "quantity", "price"}


def _rows(data: bytes) -> list[dict[str, str]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise ParseError("The file is not UTF-8 text") from e
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ParseError("The CSV file has no header row")
    reader.fieldnames = [f.strip().lower() for f in reader.fieldnames]
    return [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]


def _date(value: str, line: int) -> date:
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ParseError(f"Line {line}: unrecognised date '{value}'")


def _num(value: str, line: int, field: str) -> Decimal:
    try:
        d = Decimal(value.replace(",", ""))
    except InvalidOperation as e:
        raise ParseError(f"Line {line}: '{field}' is not a number") from e
    if d < 0:
        raise ParseError(f"Line {line}: '{field}' must not be negative")
    return d


def parse_zerodha_tradebook(data: bytes) -> ParsedStatement:
    rows = _rows(data)
    if rows and not rows[0].keys() >= ZERODHA_REQUIRED:
        missing = ZERODHA_REQUIRED - rows[0].keys()
        raise ParseError(f"Not a Zerodha tradebook: missing columns {sorted(missing)}")
    txns, warnings = [], []
    for n, r in enumerate(rows, start=2):
        if r.get("segment", "EQ").upper() not in ("EQ", ""):
            warnings.append(f"Line {n}: segment {r['segment']} is not supported and was skipped")
            continue
        side = r["trade_type"].lower()
        if side not in ("buy", "sell"):
            raise ParseError(f"Line {n}: unknown trade_type '{r['trade_type']}'")
        qty, price = _num(r["quantity"], n, "quantity"), _num(r["price"], n, "price")
        txns.append(
            ParsedTxn(
                raw_identifier=r["isin"] or r["symbol"],
                raw_name=r["symbol"],
                symbol=r["symbol"],
                date=_date(r["trade_date"], n),
                type=side,
                units=qty,
                price=price,
                amount=(qty * price).quantize(Decimal("0.01")),
                external_ref=r.get("trade_id") or None,
            )
        )
    if not txns:
        raise ParseError("No equity trades found in the file")
    return ParsedStatement("zerodha_tradebook", txns, warnings=warnings)


def parse_generic_csv(data: bytes) -> ParsedStatement:
    rows = _rows(data)
    if rows and not {"date", "type", "units", "amount"} <= rows[0].keys():
        raise ParseError(f"Generic CSV needs columns: {', '.join(GENERIC_COLUMNS)}")
    txns = []
    for n, r in enumerate(rows, start=2):
        ttype = r["type"].lower()
        if ttype not in GENERIC_TYPES:
            raise ParseError(f"Line {n}: unknown type '{r['type']}'")
        ident = r.get("isin") or r.get("symbol")
        if not ident:
            raise ParseError(f"Line {n}: an isin or symbol is required")
        price = _num(r["price"], n, "price") if r.get("price") else None
        txns.append(
            ParsedTxn(
                raw_identifier=ident,
                raw_name=r.get("name") or None,
                symbol=r.get("symbol") or None,
                date=_date(r["date"], n),
                type=ttype,
                units=_num(r["units"], n, "units"),
                price=price,
                amount=_num(r["amount"], n, "amount"),
            )
        )
    if not txns:
        raise ParseError("The file has no transactions")
    return ParsedStatement("generic_csv", txns)
