"""The portfolio in plain English: a short story an advisor can read in 20 seconds.

Built only from numbers already in the report (no LLM here). The LLM may later rewrite the
same facts more naturally; its text is validated against `facts` exactly like findings are.
"""

from typing import Any

from app.insights.templates import inr, pct


def build_summary(report: dict[str, Any]) -> dict[str, Any]:
    o = report["overview"]
    perf = report["performance"]
    contrib = report.get("contribution", {})
    items = {i["instrument_id"]: i for i in contrib.get("items", [])}
    findings = report.get("findings", [])

    gain = o["current_value"] - o["net_invested"]
    facts: dict[str, Any] = {
        "current_value": o["current_value"],
        "net_invested": o["net_invested"],
        "gain_on_net_invested": gain,
        "xirr": o["xirr"],
        "holdings_count": o["holdings_count"],
        "flags": len(findings),
        "high_flags": sum(1 for f in findings if f["severity"] == "high"),
    }
    points: list[dict[str, str]] = []

    head = f"The portfolio is worth {inr(o['current_value'])}"
    if o["net_invested"] > 0:
        head += f", {'up' if gain >= 0 else 'down'} {inr(abs(gain))} on the {inr(o['net_invested'])} put in"
    head += "."
    if o["xirr"] is not None:
        head += f" That is an annual return of {pct(o['xirr'])} (XIRR)."
    points.append({"kind": "headline", "text": head})

    twr, bench = perf.get("twr_annualized"), perf.get("benchmark_annualized")
    if perf.get("benchmark_compatible") and twr is not None and bench is not None:
        facts.update(
            {"twr": twr, "benchmark": bench, "gap": twr - bench, "benchmark_name": perf["benchmark_name"]}
        )
        word = "ahead of" if twr >= bench else "behind"
        points.append(
            {
                "kind": "good" if twr >= bench else "bad",
                "text": f"The investments grew {pct(twr)} a year, {word} the "
                f"{perf['benchmark_name']} at {pct(bench)} a year "
                f"({abs(twr - bench) * 100:.1f} percentage points).",
            }
        )

    helped = [items[i] for i in contrib.get("helped", []) if i in items]
    if helped and contrib.get("total_profit", 0) > 0:
        top = helped[0]
        facts.update(
            {"top_name": top["name"], "top_profit": top["profit"], "top_share": top["share_of_profit"]}
        )
        points.append(
            {
                "kind": "good",
                "text": f"{top['name']} helped most: it made {inr(top['profit'])}, "
                f"{pct(top['share_of_profit'])} of all profit.",
            }
        )
    hurt = [items[i] for i in contrib.get("hurt", []) if i in items]
    if hurt:
        h = hurt[0]
        if h["profit"] < 0:
            facts.update({"hurt_name": h["name"], "hurt_profit": h["profit"]})
            points.append({"kind": "bad", "text": f"{h['name']} lost {inr(-h['profit'])}."})
        elif h["vs_index"] is not None:
            facts.update({"hurt_name": h["name"], "hurt_gap": h["vs_index"]})
            points.append(
                {
                    "kind": "bad",
                    "text": f"{h['name']} held back returns most: with the same money on the same dates, "
                    f"the index did {abs(h['vs_index']) * 100:.1f} percentage points a year better.",
                }
            )

    planning = report.get("planning") or {}
    prof = planning.get("profile")
    if prof:
        eq = planning["equity_share"]
        facts.update(
            {
                "profile": prof["category"],
                "equity_share": eq,
                "equity_min": prof["equity_min"],
                "equity_max": prof["equity_max"],
            }
        )
        fits = prof["equity_min"] <= eq <= prof["equity_max"]
        points.append(
            {
                "kind": "good" if fits else "bad",
                "text": f"The client is {prof['category'].lower()}, which suggests "
                f"{prof['equity_min'] * 100:.0f}% to "
                f"{prof['equity_max'] * 100:.0f}% in equity; the portfolio has {pct(eq)}"
                + (
                    ", which fits."
                    if fits
                    else f", which is {'too much' if eq > prof['equity_max'] else 'too little'}."
                ),
            }
        )
    goals = planning.get("goals", [])
    if goals:
        on = planning["goals_on_track"]
        facts.update({"goals_total": len(goals), "goals_on_track": on})
        points.append(
            {
                "kind": "good" if on == len(goals) else "warn",
                "text": f"{on} of {len(goals)} goal{'s' if len(goals) != 1 else ''} on track.",
            }
        )

    if findings:
        hi = facts["high_flags"]
        text = f"{len(findings)} thing{'s' if len(findings) != 1 else ''} to discuss"
        text += f", {hi} of them important." if hi else "."
        biggest = "; ".join(f["title"] for f in findings[:2])
        text += f" The biggest: {biggest}."
        points.append({"kind": "warn", "text": text})
    else:
        points.append({"kind": "good", "text": "Nothing crossed a review limit."})

    return {
        "points": points,
        "text": " ".join(p["text"] for p in points),
        "source": "template",
        "facts": facts,
    }
