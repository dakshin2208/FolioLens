"""CAMS / KFintech Consolidated Account Statement (CAS) parser.

Wraps the open-source `casparser` library (MIT licence) and converts its output into
ParsedStatement, so nothing else in the code depends on the library.
"""

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.portfolio.parsers.base import ParsedStatement, ParsedTxn, ParseError

TYPE_MAP = {
    "PURCHASE": "buy",
    "PURCHASE_SIP": "buy",
    "REDEMPTION": "sell",
    "DIVIDEND_PAYOUT": "dividend_payout",
    "DIVIDEND_REINVEST": "dividend_reinvest",
    "SWITCH_IN": "switch_in",
    "SWITCH_IN_MERGER": "switch_in",
    "SWITCH_OUT": "switch_out",
    "SWITCH_OUT_MERGER": "switch_out",
}
# Charges are folded into the matching purchase/redemption amount on the same day, so the
# investor's real cash flow is used for XIRR (D-03).
CHARGE_TYPES = {"STAMP_DUTY_TAX", "STT_TAX", "TDS_TAX"}


def _d(value: Any) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _dec(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def read_cas(data: bytes, password: str) -> dict[str, Any]:
    import io

    import casparser
    from casparser.exceptions import (
        CASIntegrityError,
        CASParseError,
        HeaderParseError,
        IncompleteCASError,
        IncorrectPasswordError,
    )

    try:
        result = casparser.read_cas_pdf(io.BytesIO(data), password)
        # casparser returns a pydantic model; convert it to plain JSON-style data.
        if hasattr(result, "model_dump"):
            return dict(result.model_dump(mode="json", by_alias=True))
        return dict(result)
    except IncorrectPasswordError as e:
        raise ParseError("Incorrect PDF password") from e
    except IncompleteCASError as e:
        raise ParseError("The CAS is incomplete; download a full-history detailed CAS") from e
    except CASIntegrityError as e:
        raise ParseError("The CAS failed its own balance integrity check") from e
    except (CASParseError, HeaderParseError) as e:
        raise ParseError("This PDF is not a supported CAMS/KFintech CAS") from e


def parse_cas(data: bytes, password: str) -> ParsedStatement:
    return convert_cas(read_cas(data, password))


def convert_cas(cas: dict[str, Any]) -> ParsedStatement:
    if str(cas.get("cas_type") or "DETAILED").split(".")[-1] != "DETAILED":
        raise ParseError("Only the detailed CAS (with transactions) is supported")
    if str(cas.get("file_type") or "CAMS").split(".")[-1] in ("NSDL", "CDSL"):
        raise ParseError("NSDL/CDSL depository statements are not supported yet; use a CAMS/KFintech CAS")
    txns: list[ParsedTxn] = []
    closing: dict[str, Decimal] = defaultdict(Decimal)
    names: dict[str, str] = {}
    warnings: list[str] = []

    isin_owner: dict[str, str] = {}
    for folio in cas.get("folios", []):
        for scheme in folio.get("schemes", []):
            isin = scheme.get("isin")
            name = scheme.get("scheme", "Unknown scheme")
            if isin and isin_owner.setdefault(isin, name) != name:
                # Two different schemes resolved to the same ISIN: never merge them.
                warnings.append(
                    f"{name}: ISIN {isin} is also assigned to {isin_owner[isin]}; needs manual mapping"
                )
                isin = None
            if not isin:
                if not any(w.startswith(f"{name}:") for w in warnings):
                    warnings.append(f"{name}: no ISIN in statement; needs manual mapping")
                isin = f"AMFI:{scheme.get('amfi') or name[:40]}"
            names[isin] = name
            closing[isin] += _dec(scheme.get("close"))
            charges: dict[date, Decimal] = defaultdict(Decimal)
            scheme_txns: list[ParsedTxn] = []
            for t in scheme.get("transactions", []):
                ttype = str(t.get("type", "UNKNOWN")).split(".")[-1]
                tdate = _d(t["date"])
                if ttype in CHARGE_TYPES:
                    charges[tdate] += abs(_dec(t.get("amount")))
                    continue
                units, amount = _dec(t.get("units")), _dec(t.get("amount"))
                if ttype == "REVERSAL":
                    # A reversed purchase: units come back out, money is refunded.
                    mapped = "sell" if units < 0 else "buy"
                elif ttype in TYPE_MAP:
                    mapped = TYPE_MAP[ttype]
                else:
                    warnings.append(f"{name}: {ttype} on {tdate} is not supported and was skipped")
                    continue
                nav = t.get("nav")
                scheme_txns.append(
                    ParsedTxn(
                        raw_identifier=isin,
                        raw_name=name,
                        date=tdate,
                        type=mapped,
                        units=abs(units),
                        price=_dec(nav) if nav else None,
                        amount=abs(amount).quantize(Decimal("0.01")),
                    )
                )
            for st in scheme_txns:
                if st.date in charges and st.type == "buy":
                    st.amount += charges.pop(st.date)  # investor paid amount + stamp duty
                elif st.date in charges and st.type == "sell":
                    st.amount -= charges.pop(st.date)  # STT/TDS reduce redemption proceeds
            for d, c in charges.items():
                warnings.append(f"{name}: charge of {c} on {d} had no matching transaction")
            txns.extend(scheme_txns)

    period = cas.get("statement_period") or {}
    sp = None
    if period.get("from") and period.get("to"):
        try:
            sp = (
                datetime.strptime(period["from"], "%d-%b-%Y").date(),
                datetime.strptime(period["to"], "%d-%b-%Y").date(),
            )
        except ValueError:
            sp = None
    warnings.extend(str(w) for w in cas.get("parse_warnings") or [])
    return ParsedStatement("cas_pdf", txns, dict(closing), names, warnings, sp)
