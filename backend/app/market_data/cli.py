"""Command-line tools for loading data.

Examples:
  python -m app.market_data.cli seed-demo
  python -m app.market_data.cli fetch-amfi
  python -m app.market_data.cli load-amfi data/NAVAll.txt
  python -m app.market_data.cli load-bhavcopy data/BhavCopy_NSE_CM_20261009.csv
  python -m app.market_data.cli load-index data/nifty50_tri.csv --symbol NIFTY50TRI \
      --name "Nifty 50 TRI" --date-col Date --value-col "Total Returns Index"
  python -m app.market_data.cli load-constituents data/constituents.csv --source "AMC disclosure Sep 2026"
  python -m app.market_data.cli load-stock-metadata data/stock_metadata.csv
"""

import argparse
from pathlib import Path

import httpx

from app.db import SessionLocal
from app.market_data import loaders
from app.market_data.demo_seed import demo_transactions_csv, seed_demo

AMFI_LATEST_URL = "https://www.amfiindia.com/spages/NAVAll.txt"


def main() -> None:
    p = argparse.ArgumentParser(prog="foliolens-data")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-demo", help="Load the synthetic demo universe")
    sub.add_parser("seed-demo-account", help="Create a local demo login with an analysed portfolio")
    e = sub.add_parser("export-demo-csv", help="Write the demo ledger as a generic CSV")
    e.add_argument("out", type=Path)
    f = sub.add_parser("fetch-amfi", help="Download and load today's AMFI NAV file")
    f.add_argument("--url", default=AMFI_LATEST_URL)
    for name in ("load-amfi", "load-bhavcopy", "load-stock-metadata"):
        sub.add_parser(name).add_argument("file", type=Path)
    i = sub.add_parser("load-index")
    i.add_argument("file", type=Path)
    i.add_argument("--symbol", required=True)
    i.add_argument("--name", required=True)
    i.add_argument("--date-col", default="Date")
    i.add_argument("--value-col", default="Total Returns Index")
    i.add_argument("--source", default="niftyindices.com export")
    c = sub.add_parser("load-constituents")
    c.add_argument("file", type=Path)
    c.add_argument("--source", required=True)
    a = p.parse_args()

    if a.cmd == "export-demo-csv":
        a.out.write_text(demo_transactions_csv())
        print(f"Wrote {a.out}")
        return
    with SessionLocal() as db:
        if a.cmd == "seed-demo":
            print(seed_demo(db))
        elif a.cmd == "seed-demo-account":
            from app.demo.account import seed_demo_account

            for k, v in seed_demo_account(db).items():
                print(f"{k}: {v}")
        elif a.cmd == "fetch-amfi":
            text = httpx.get(a.url, timeout=60, follow_redirects=True).text
            print("instruments, prices:", loaders.load_amfi_nav(db, text))
        elif a.cmd == "load-amfi":
            print("instruments, prices:", loaders.load_amfi_nav(db, a.file.read_text()))
        elif a.cmd == "load-bhavcopy":
            print("instruments, prices:", loaders.load_nse_bhavcopy(db, a.file.read_text()))
        elif a.cmd == "load-index":
            print(
                "prices:",
                loaders.load_index_history(
                    db, a.file.read_text(), a.symbol, a.name, a.date_col, a.value_col, a.source
                ),
            )
        elif a.cmd == "load-constituents":
            print("rows:", loaders.load_constituents(db, a.file.read_text(), a.source))
        elif a.cmd == "load-stock-metadata":
            print("updated:", loaders.load_stock_metadata(db, a.file.read_text()))


if __name__ == "__main__":
    main()
