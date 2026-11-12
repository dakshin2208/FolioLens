# ruff: noqa: S311, E501  (benchmark script: seeded random data, long shell commands in the docstring)
"""Benchmark: FolioLens XIRR against a spreadsheet's XIRR() on random cash flows.

    cd backend && python -m benchmarks.xirr_vs_spreadsheet make 500 /tmp/xirr   # writes xirr_cases.xlsx
    soffice --headless --calc --convert-to csv:"Text - txt - csv (StarCalc)":44,34,76,1,,0,false,true,false,false,false,-1 \
        /tmp/xirr/xirr_cases.xlsx --outdir /tmp/xirr                          # LibreOffice computes XIRR()
    python -m benchmarks.xirr_vs_spreadsheet compare /tmp/xirr

The .xlsx can also be opened in Microsoft Excel: save the "Out" sheet as CSV (case, xirr) under the
name xirr_cases-Out.csv and run `compare` to check against Excel itself.
"""

import csv
import json
import random
import sys
from datetime import date, timedelta

from app.analytics.xirr import XirrError, xirr


def make(n: int, out: str) -> None:
    import openpyxl

    rng = random.Random(42)
    cases: list[dict] = []
    while len(cases) < n:
        d = date(2015, 1, 1) + timedelta(days=rng.randint(0, 3000))
        flows = []
        for _ in range(rng.randint(2, 120)):
            d += timedelta(days=rng.randint(1, 60))
            amt = -round(rng.uniform(500, 50000), 2)
            if rng.random() < 0.08:
                amt = round(rng.uniform(1000, 30000), 2)  # a partial sale or dividend
            flows.append((d, amt))
        invested = -sum(a for _, a in flows if a < 0)
        flows.append((d + timedelta(days=rng.randint(1, 400)), round(invested * rng.uniform(0.6, 2.5), 2)))
        try:
            r = xirr(flows)
        except XirrError:
            continue
        if -0.9 < r < 5:
            cases.append({"flows": [(x.isoformat(), a) for x, a in flows], "foliolens": r})
    wb = openpyxl.Workbook()
    sheet_out = wb.active
    sheet_out.title = "Out"
    data = wb.create_sheet("Data")
    row = 1
    for i, c in enumerate(cases):
        first = row
        for d_iso, a in c["flows"]:
            data.cell(row=row, column=1, value=date.fromisoformat(d_iso))
            data.cell(row=row, column=2, value=a)
            row += 1
        sheet_out.cell(row=i + 1, column=1, value=i)
        sheet_out.cell(row=i + 1, column=2, value=f"=XIRR(Data!B{first}:B{row - 1},Data!A{first}:A{row - 1})")
    wb.save(f"{out}/xirr_cases.xlsx")
    with open(f"{out}/xirr_cases.json", "w") as fh:
        json.dump(cases, fh)
    print(len(cases), "cases,", sum(len(c["flows"]) for c in cases), "cash flows")


def compare(out: str) -> None:
    with open(f"{out}/xirr_cases.json") as fh:
        cases = json.load(fh)
    sheet: dict[int, float] = {}
    with open(f"{out}/xirr_cases-Out.csv") as fh:
        for row in csv.reader(fh):
            sheet[int(row[0])] = float(row[1])
    pp = sorted(abs(sheet[i] - c["foliolens"]) * 100 for i, c in enumerate(cases) if i in sheet)
    print(f"compared {len(pp)} of {len(cases)}; largest difference {pp[-1]:.2e} percentage points")
    print(f"within 0.0001 pp: {sum(d <= 1e-4 for d in pp)}")


if __name__ == "__main__":
    if sys.argv[1] == "make":
        make(int(sys.argv[2]), sys.argv[3])
    else:
        compare(sys.argv[2])
