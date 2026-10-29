from datetime import date
from decimal import Decimal

import pytest

from app.portfolio.parsers.base import ParseError
from app.portfolio.parsers.cas import convert_cas
from app.portfolio.parsers.csv_formats import parse_generic_csv, parse_zerodha_tradebook

ZERODHA = """symbol,isin,trade_date,exchange,segment,series,trade_type,auction,quantity,price,trade_id,order_id,order_execution_time
INFY,INE009A01021,2024-03-11,NSE,EQ,EQ,buy,false,10,1600.5,111,1,2024-03-11T10:00:00
INFY,INE009A01021,2024-06-11,NSE,EQ,EQ,sell,false,4,1500,112,2,2024-06-11T10:00:00
NIFTY24MARFUT,,2024-03-11,NFO,FO,,buy,false,50,22000,113,3,2024-03-11T10:00:00
"""


def test_zerodha_tradebook():
    s = parse_zerodha_tradebook(ZERODHA.encode())
    assert [(t.type, t.units, t.amount) for t in s.transactions] == [
        ("buy", Decimal("10"), Decimal("16005.00")),
        ("sell", Decimal("4"), Decimal("6000.00")),
    ]
    assert s.transactions[0].raw_identifier == "INE009A01021"
    assert "not supported" in s.warnings[0]


def test_zerodha_rejects_other_files():
    with pytest.raises(ParseError, match="Not a Zerodha tradebook"):
        parse_zerodha_tradebook(b"a,b\n1,2\n")


def test_generic_csv_validation():
    with pytest.raises(ParseError, match="unknown type"):
        parse_generic_csv(b"date,isin,type,units,amount\n2024-01-01,X,gift,1,1\n")
    with pytest.raises(ParseError, match="must not be negative"):
        parse_generic_csv(b"date,isin,type,units,amount\n2024-01-01,X,buy,-1,1\n")


def test_cas_conversion_folds_stamp_duty_and_maps_types():
    cas = {
        "cas_type": "DETAILED",
        "folios": [
            {
                "schemes": [
                    {
                        "scheme": "Example Flexi Cap Fund - Direct Growth",
                        "isin": "INF000000001",
                        "close": 148.5,
                        "transactions": [
                            {
                                "date": "2024-01-05",
                                "type": "PURCHASE_SIP",
                                "units": 100.0,
                                "nav": 49.995,
                                "amount": 4999.5,
                            },
                            {
                                "date": "2024-01-05",
                                "type": "STAMP_DUTY_TAX",
                                "units": None,
                                "nav": None,
                                "amount": 0.5,
                            },
                            {
                                "date": "2024-02-05",
                                "type": "PURCHASE",
                                "units": 50.0,
                                "nav": 50,
                                "amount": 2500,
                            },
                            {
                                "date": "2024-03-05",
                                "type": "REDEMPTION",
                                "units": -1.5,
                                "nav": 52,
                                "amount": -78,
                            },
                            {"date": "2024-03-06", "type": "SEGREGATION", "units": 1, "nav": 0, "amount": 0},
                        ],
                    }
                ]
            }
        ],
    }
    s = convert_cas(cas)
    assert [t.type for t in s.transactions] == ["buy", "buy", "sell"]
    assert s.transactions[0].amount == Decimal("5000.00")  # 4,999.50 + 0.50 stamp duty
    assert s.transactions[2].units == Decimal("1.5")
    assert s.closing_units == {"INF000000001": Decimal("148.5")}
    assert s.transactions[0].date == date(2024, 1, 5)
    assert any("SEGREGATION" in w for w in s.warnings)


def test_summary_cas_is_rejected():
    with pytest.raises(ParseError, match="detailed"):
        convert_cas({"cas_type": "SUMMARY", "folios": []})


def test_depository_cas_is_rejected():
    with pytest.raises(ParseError, match="NSDL/CDSL"):
        convert_cas({"cas_type": "DETAILED", "file_type": "NSDL", "folios": []})


def test_real_casparser_model_converts():
    """casparser returns a pydantic model; make sure our conversion path handles it."""
    from casparser.types import CASData

    raw = {
        "statement_period": {"from": "01-Jan-2024", "to": "31-Mar-2024"},
        "file_type": "CAMS",
        "cas_type": "DETAILED",
        "investor_info": {"name": "Test", "email": "t@example.com", "address": "x", "mobile": "1"},
        "folios": [
            {
                "folio": "1",
                "amc": "Example AMC",
                "PAN": "ABCDE1234F",
                "KYC": "OK",
                "PANKYC": "OK",
                "schemes": [
                    {
                        "scheme": "Example Fund - Growth",
                        "advisor": None,
                        "rta_code": "X",
                        "rta": "CAMS",
                        "type": "EQUITY",
                        "isin": "INF000000002",
                        "amfi": "1",
                        "nominees": [],
                        "open": 0,
                        "close": 10,
                        "close_calculated": 10,
                        "valuation": {"date": "2024-03-31", "nav": 12, "value": 120, "cost": 100},
                        "transactions": [
                            {
                                "date": "2024-01-05",
                                "description": "Purchase",
                                "amount": 100,
                                "units": 10,
                                "nav": 10,
                                "balance": 10,
                                "type": "PURCHASE",
                                "dividend_rate": None,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    model = CASData.model_validate(raw)
    s = convert_cas(model.model_dump(mode="json", by_alias=True))
    assert [(t.type, t.units, t.amount) for t in s.transactions] == [
        ("buy", Decimal("10"), Decimal("100.00"))
    ]
    assert s.statement_period == (date(2024, 1, 1), date(2024, 3, 31))


def test_two_schemes_with_the_same_isin_are_not_merged():
    def scheme(name):
        return {
            "scheme": name,
            "isin": "INF000000003",
            "close": 10,
            "transactions": [
                {"date": "2024-01-05", "type": "PURCHASE", "units": 10, "nav": 10, "amount": 100}
            ],
        }

    s = convert_cas(
        {
            "cas_type": "DETAILED",
            "folios": [{"schemes": [scheme("Fund One - Growth"), scheme("Fund Two - Growth")]}],
        }
    )
    assert len(s.closing_units) == 2
    assert s.closing_units["INF000000003"] == Decimal("10")
    assert any("also assigned" in w for w in s.warnings)
