# ruff: noqa: S311, E501  (benchmark script: seeded random data, long shell commands in the docstring)
"""Benchmark: random portfolios through the report engine, and the AI-number validator under attack.

    cd backend && python -m benchmarks.engine_and_validator 200

1. Builds N random portfolios (2-12 holdings, SIPs, lump sums, partial sales, random risk answers and
   goals) on the synthetic demo market data, runs build_report() on each, checks invariants (values
   and weights reconcile, per-holding profits add up to total profit, every flag has options) and
   times the engine.
2. Takes every explanation and summary those reports produce (all correct by construction), checks
   the validator accepts them, then injects one error at a time (a digit changed, a number x10, a
   fraction written as a percent, an invented figure, an invented date, a trade instruction) and
   counts how many the validator catches. Mutations that do not change the value are skipped.
"""

import json
import random
import re
import statistics
import sys
import time
from dataclasses import replace
from datetime import date, timedelta

from app.analytics.planning import Goal, PlanInput
from app.analytics.types import LedgerTxn
from app.demo.data import build_demo_input
from app.insights.llm import _summary_evidence
from app.insights.templates import template_explanation
from app.insights.validation import validate_explanation
from app.reports.engine import build_report

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
base = build_demo_input()
tradable = [i for i, x in base.instruments.items() if base.prices.get(i)]
rng = random.Random(7)


def on_or_after(iid, d):
    p = base.prices[iid]
    while d not in p:
        d += timedelta(days=1)
        if d > base.valuation_date:
            return None
    return d


def random_portfolio():
    picks = rng.sample(tradable, rng.randint(2, min(12, len(tradable))))
    txns = []
    for iid in picks:
        start = date(2023, 4, 3) + timedelta(days=rng.randint(0, 700))
        if rng.random() < 0.6:  # SIP
            amt = rng.choice([2000, 5000, 10000, 25000])
            d = start
            while d < base.valuation_date - timedelta(days=5):
                dd = on_or_after(iid, d)
                if dd:
                    txns.append(LedgerTxn(iid, dd, "buy", round(amt / base.prices[iid][dd], 4), amt))
                d += timedelta(days=rng.choice([28, 30, 31]))
        else:  # lump sums
            for _ in range(rng.randint(1, 4)):
                dd = on_or_after(iid, start + timedelta(days=rng.randint(0, 600)))
                if dd:
                    amt = rng.randint(20, 500) * 1000
                    txns.append(LedgerTxn(iid, dd, "buy", round(amt / base.prices[iid][dd], 4), amt))
        held = sum(t.units for t in txns if t.instrument_id == iid)
        if held and rng.random() < 0.3:  # partial sale
            dd = on_or_after(iid, base.valuation_date - timedelta(days=rng.randint(30, 300)))
            prior = sum(t.units for t in txns if t.instrument_id == iid and t.date < dd) if dd else 0
            if dd and prior > 0:
                u = round(prior * rng.uniform(0.1, 0.5), 4)
                txns.append(LedgerTxn(iid, dd, "sell", u, round(u * base.prices[iid][dd], 2)))
    txns.sort(key=lambda t: t.date)
    answers = {q: rng.randint(0, 4) for q in ["age", "horizon", "income", "drop", "experience", "cushion"]}
    goals, left = [], 1.0
    for k in range(rng.randint(0, 3)):
        share = round(rng.uniform(0, left), 2)
        left -= share
        goals.append(
            Goal(
                f"g{k}",
                f"Goal {k}",
                rng.randint(5, 300) * 100000,
                date(2027 + rng.randint(0, 25), 4, 1),
                rng.choice([0, 5000, 15000, 40000]),
                share,
            )
        )
    return replace(base, transactions=txns, plan=PlanInput(answers, goals))


times, ok, fails, metrics_cnt = [], 0, [], []
texts = []
for _ in range(N):
    inp = random_portfolio()
    if not inp.transactions:
        continue
    t0 = time.perf_counter()
    try:
        r = build_report(inp)
    except Exception as e:
        fails.append(repr(e))
        continue
    times.append(time.perf_counter() - t0)
    o = r["overview"]
    tot = o["current_value"]
    assert abs(sum(h["value"] for h in r["holdings"]) - tot) < 1e-6 * max(tot, 1)
    assert abs(sum(h["weight"] for h in r["holdings"]) - 1) < 1e-9
    assert abs(r["contribution"]["total_profit"] - (tot - o["net_invested"])) < 1e-6 * max(tot, 1)
    for f in r["findings"]:
        assert f["options"], f["type"]
        f["explanation"] = template_explanation(f)
        texts.append((f["explanation"], f))
    texts.append((r["summary"]["text"], _summary_evidence(r["summary"]["facts"])))
    ok += 1

# ---- validator: originals must pass; mutated copies must be caught
NUM = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|(?<![\w.])\d+(?:\.\d+)?")


def mutations(text):
    out = []
    nums = list(NUM.finditer(text))
    big = [m for m in nums if len(m.group().replace(",", "").split(".")[0]) >= 2 or "." in m.group()]
    if big:
        m = rng.choice(big)
        s = m.group()
        last = [i for i, ch in enumerate(s) if ch.isdigit()][-1]
        d = str((int(s[last]) + rng.randint(1, 8)) % 10)
        new = s[:last] + d + s[last + 1 :]
        if float(new.replace(",", "")) != float(s.replace(",", "")):
            out.append(("digit changed", text[: m.start()] + new + text[m.end() :]))
        m2 = rng.choice(big)
        v = float(m2.group().replace(",", ""))
        if v != 0:
            out.append(("number scaled x10", text[: m2.start()] + f"{v * 10:g}" + text[m2.end() :]))
    pm = re.search(r"(\d+)\.(\d)%", text)
    if pm and float(pm.group(1) + "." + pm.group(2)) >= 1:
        frac = f"0.{pm.group(1).zfill(2)[:2]}%"
        out.append(("fraction written as percent", text[: pm.start()] + frac + text[pm.end() :]))
    out.append(
        (
            "invented figure added",
            text + f" It could rise another {rng.randint(11, 97)}.{rng.randint(1, 9)}% next year.",
        )
    )
    out.append(
        (
            "invented date added",
            text + f" This was last checked on {rng.randint(1, 28)} March 20{rng.randint(10, 22)}.",
        )
    )
    out.append(("trade instruction added", text + " You should sell this fund now."))
    return out


fp, caught, total = 0, {}, {}
for text, ev in texts:
    if not validate_explanation(text, ev)[0]:
        fp += 1
    for kind, mtext in mutations(text):
        total[kind] = total.get(kind, 0) + 1
        if not validate_explanation(mtext, ev)[0]:
            caught[kind] = caught.get(kind, 0) + 1

print(
    json.dumps(
        {
            "portfolios_ok": ok,
            "failures": len(fails),
            "fail_examples": fails[:3],
            "engine_seconds_median": statistics.median(times),
            "engine_seconds_p95": sorted(times)[int(len(times) * 0.95)],
            "engine_seconds_max": max(times),
            "texts": len(texts),
            "false_rejections": fp,
            "mutations": {k: f"{caught.get(k, 0)}/{v}" for k, v in total.items()},
            "mutations_total": f"{sum(caught.values())}/{sum(total.values())}",
        },
        indent=1,
    )
)
