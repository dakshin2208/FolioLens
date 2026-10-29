"""Checks an LLM explanation before it is shown.

Rule 1: every number in the text must come from the finding's own evidence.
        A number written with "%" must equal a fraction from the evidence x 100, so a
        fraction like 0.81 can never appear as "0.8%".
Rule 2: dates are allowed only if they are dates from the finding itself.
Rule 3: the text must not tell anyone to buy, sell or switch a security.
"""

import re
from datetime import date
from typing import Any

NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{2,3})+|\d+)(?:\.(\d+))?\s*(%)?")
ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]
TRADE_INSTRUCTION = re.compile(
    r"\b(you should|we recommend|recommend(?:ed)? (?:to )?|consider)\s+"
    r"(buy|buying|sell|selling|redeem|redeeming|exit|exiting|switch|switching|purchase)\b",
    re.IGNORECASE,
)


def _walk(obj: Any, numbers: list[float], strings: list[str]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, int | float):
        numbers.append(float(obj))
    elif isinstance(obj, str):
        strings.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk(v, numbers, strings)
    elif isinstance(obj, list | tuple):
        for v in obj:
            _walk(v, numbers, strings)


def _evidence(finding: dict[str, Any]) -> tuple[list[float], list[date]]:
    numbers: list[float] = []
    strings: list[str] = []
    _walk(
        [
            finding.get("measured_value"),
            finding.get("threshold"),
            finding.get("evidence", {}),
            finding.get("data_date"),
        ],
        numbers,
        strings,
    )
    dates = []
    for s in strings:
        for y, m, d in ISO_DATE.findall(s):
            try:
                dates.append(date(int(y), int(m), int(d)))
            except ValueError:
                continue
    return numbers, dates


def _date_patterns(d: date) -> list[str]:
    month, short = MONTHS[d.month - 1], MONTHS[d.month - 1][:3]
    return [
        rf"\b{d.isoformat()}\b",
        rf"\b0?{d.day}(?:st|nd|rd|th)?\s+(?:{month}|{short}\.?)\s*,?\s+{d.year}\b",
        rf"\b(?:{month}|{short}\.?)\s+0?{d.day}(?:st|nd|rd|th)?\s*,?\s+{d.year}\b",
    ]


def _strip_allowed_dates(text: str, dates: list[date]) -> str:
    for d in dates:
        for pattern in _date_patterns(d):
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return text


def _matches(value: float, decimals: int, allowed: list[float]) -> bool:
    tol = 0.5 * 10 ** (-decimals) + 1e-9
    return any(abs(value - a) <= tol for a in allowed)


def validate_explanation(text: str, finding: dict[str, Any]) -> tuple[bool, str | None]:
    if not text or len(text) > 1200:
        return False, "empty or too long"
    if TRADE_INSTRUCTION.search(text):
        return False, "contains a trade instruction"
    numbers, dates = _evidence(finding)
    percents = [x * 100 for x in numbers]
    plain = numbers + percents + [0.0, 1.0, 2.0, 3.0]  # "one", "two" written as digits
    for m in NUMBER.finditer(_strip_allowed_dates(text, dates)):
        whole, frac, is_pct = m.group(1).replace(",", ""), m.group(2), m.group(3)
        value = float(f"{whole}.{frac}") if frac else float(whole)
        decimals = len(frac) if frac else 0
        if not _matches(value, decimals, percents if is_pct else plain):
            return False, f"number {m.group(0).strip()} is not in the evidence"
    return True, None
