"""Options to discuss: for each review flag, a few concrete choices with their numbers.

These are *options for the advisor to weigh*, not recommendations from FolioLens. Every number
is calculated here from the same data as the report (no LLM), so it can be checked:

- how much money is involved,
- what the measured value would become,
- an estimate of capital-gains tax if a sale is involved (see app/analytics/tax.py),
- the trade-offs, written in plain English.

The advisor decides; the client report only shows the options the advisor ticks.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.analytics.planning import Goal, years_to_reach
from app.analytics.tax import Lot, combine, estimate_sale
from app.analytics.types import Constituents, InstrumentInfo

PAST_RETURNS_NOTE = "Past returns are not a promise of future returns."


@dataclass
class ActionContext:
    total: float
    valuation_date: date
    holdings: dict[str, dict[str, Any]]  # instrument id -> holding row from the report
    instruments: dict[str, InstrumentInfo]
    lots: dict[str, list[Lot]]
    constituents: dict[str, Constituents]  # only funds whose look-through data is in use
    contribution: dict[str, dict[str, Any]]  # instrument id -> contribution item
    equity_exposure: float


def _impact(label: str, value: float | str | None, unit: str) -> dict[str, Any]:
    return {"label": label, "value": value, "unit": unit}


def _sale(ctx: ActionContext, iid: str, amount: float) -> dict[str, Any] | None:
    """Tax estimate for selling about `amount` rupees of a holding (FIFO)."""
    h = ctx.holdings.get(iid)
    if not h or not h["price"] or iid not in ctx.lots:
        return None
    units = min(amount / h["price"], h["units"])
    est = estimate_sale(ctx.lots[iid], units, h["price"], ctx.valuation_date, h["asset_class"])
    return est.to_dict()


def _find_holding(ctx: ActionContext, name: str) -> str | None:
    for iid, h in ctx.holdings.items():
        if h["name"] == name:
            return iid
    return None


def _ret(ctx: ActionContext, iid: str) -> float | None:
    return ctx.holdings[iid]["xirr"] if iid in ctx.holdings else None


def _sources(ctx: ActionContext, stock_ids: set[str]) -> list[tuple[str, float]]:
    """Which holdings give the exposure to these stocks: direct shares and each fund (rupees)."""
    out: dict[str, float] = {}
    for iid, h in ctx.holdings.items():
        if iid in stock_ids:
            out[iid] = out.get(iid, 0.0) + h["value"]
        cons = ctx.constituents.get(iid)
        if cons:
            v = sum(h["value"] * w for s, w in cons.weights.items() if s in stock_ids)
            if v > 0:
                out[iid] = out.get(iid, 0.0) + v
    return sorted(out.items(), key=lambda kv: -kv[1])


def _fund_equity_value(ctx: ActionContext, iid: str) -> float:
    """Equity exposure a holding brings: a stock's value, or a covered fund's full value."""
    h = ctx.holdings[iid]
    if h["type"] == "stock" or iid in ctx.constituents:
        return float(h["value"])
    return 0.0


# --------------------------------------------------------------------------------- per type


def _overlap(f: dict[str, Any], ctx: ActionContext) -> list[dict[str, Any]]:
    a, b = (_find_holding(ctx, n) for n in f["instruments"][:2])
    if not a or not b:
        return []
    ra, rb = _ret(ctx, a), _ret(ctx, b)
    # Keep the one with the higher return since purchase; say clearly that this is the basis.
    keep, move = (a, b) if (-1.0 if ra is None else ra) >= (-1.0 if rb is None else rb) else (b, a)
    hk, hm = ctx.holdings[keep], ctx.holdings[move]
    tax = _sale(ctx, move, hm["value"])
    return [
        {
            "id": f"{f['id']}-merge",
            "kind": "reduce",
            "title": f"Combine into {hk['name']}",
            "summary": (
                f"Move the money in {hm['name']} into {hk['name']}, so the client holds one of the "
                f"two similar funds. {hk['name']} has the higher annual return since purchase."
            ),
            "impact": [
                _impact("Money to move", hm["value"], "inr"),
                _impact(f"{hk['name']} annual return", hk["xirr"], "percent"),
                _impact(f"{hm['name']} annual return", hm["xirr"], "percent"),
                _impact("Funds after the change", "One fund instead of two similar ones", "text"),
            ],
            "tax": tax,
            "tradeoffs": [
                "Selling may trigger capital-gains tax (estimate below) and an exit load if units are "
                "less than a year old.",
                PAST_RETURNS_NOTE,
            ],
        },
        {
            "id": f"{f['id']}-redirect",
            "kind": "redirect",
            "title": f"Keep both, send new SIPs only to {hk['name']}",
            "summary": (
                f"Leave the current money where it is (no tax now) and direct future SIPs to "
                f"{hk['name']} only. The overlap shrinks slowly over time."
            ),
            "impact": [_impact("Tax now", 0, "inr"), _impact("Speed", "Slow, over months", "text")],
            "tax": None,
            "tradeoffs": ["The duplication stays for now; it only fades as new money goes in."],
        },
        {
            "id": f"{f['id']}-keep",
            "kind": "keep",
            "title": "Keep both as they are",
            "summary": "Reasonable only if the two funds have different roles in the client's plan.",
            "impact": [_impact("Change", "None", "text")],
            "tax": None,
            "tradeoffs": ["The client pays two sets of fees for largely the same stocks."],
        },
    ]


def _single_stock(f: dict[str, Any], ctx: ActionContext) -> list[dict[str, Any]]:
    name = f["instruments"][0]
    ev = f["evidence"]
    excess = (f["measured_value"] - f["threshold"]) * ctx.total
    direct_id = _find_holding(ctx, name)
    opts: list[dict[str, Any]] = []
    if direct_id and ev.get("direct_value", 0) > 0:
        sell = min(excess, ev["direct_value"])
        after = (ev["value"] - sell) / ctx.total if ctx.total else None
        opts.append(
            {
                "id": f"{f['id']}-trim",
                "kind": "reduce",
                "title": f"Trim the directly held {name} shares",
                "summary": (
                    f"Sell part of the {name} shares held directly and invest the money in a "
                    "diversified fund that does not already hold much of it."
                ),
                "impact": [
                    _impact("Amount to sell", sell, "inr"),
                    _impact("Exposure now", f["measured_value"], "percent"),
                    _impact("Exposure after", after, "percent"),
                    _impact("Review limit", f["threshold"], "percent"),
                ],
                "tax": _sale(ctx, direct_id, sell),
                "tradeoffs": [
                    "If the company keeps doing well, the client gains less from it.",
                    *(
                        [
                            "Trimming the direct shares alone does not reach the limit, because part "
                            "of the exposure comes through funds."
                        ]
                        if after is not None and after > f["threshold"]
                        else []
                    ),
                ],
            }
        )
    sid = next((i for i, info in ctx.instruments.items() if info.name == name and info.type == "stock"), None)
    funds = [(i, v) for i, v in _sources(ctx, {sid} if sid else set()) if i != direct_id][:2]
    if funds:
        opts.append(
            {
                "id": f"{f['id']}-funds",
                "kind": "redirect",
                "title": "Check the funds that also hold it",
                "summary": (
                    "These funds add to the same company exposure. Choosing other funds for new money "
                    "lowers the total without selling anything."
                ),
                "impact": [_impact(ctx.holdings[i]["name"], v, "inr") for i, v in funds],
                "tax": None,
                "tradeoffs": ["Works slowly; the existing exposure stays."],
            }
        )
    opts.append(
        {
            "id": f"{f['id']}-keep",
            "kind": "keep",
            "title": "Keep it, with the client's agreement",
            "summary": "Fine if the client understands and accepts the risk of one company.",
            "impact": [_impact("Change", "None", "text")],
            "tax": None,
            "tradeoffs": ["A fall in this one company would hit several holdings at once."],
        }
    )
    return opts


def _sector(f: dict[str, Any], ctx: ActionContext) -> list[dict[str, Any]]:
    sector = f["evidence"]["sector"]
    stock_ids = {i for i, info in ctx.instruments.items() if info.type == "stock" and info.sector == sector}
    sources = _sources(ctx, stock_ids)
    excess = (f["measured_value"] - f["threshold"]) * ctx.equity_exposure
    sector_value = float(f["evidence"]["value"])
    opts: list[dict[str, Any]] = []
    if sources:
        top_id, top_v = sources[0]
        h = ctx.holdings[top_id]
        eq_v = _fund_equity_value(ctx, top_id)
        denom = ctx.equity_exposure - eq_v
        after = (sector_value - top_v) / denom if denom > 0 else None
        opts.append(
            {
                "id": f"{f['id']}-biggest",
                "kind": "reduce",
                "title": f"Reduce {h['name']}, the biggest source",
                "summary": (
                    f"{h['name']} brings the most {sector} exposure. Without it, {sector} would be a "
                    "smaller share of the client's equity."
                ),
                "impact": [
                    _impact(f"{sector} exposure from it", top_v, "inr"),
                    _impact("Share of equity now", f["measured_value"], "percent"),
                    _impact("Share without this holding", after, "percent"),
                    _impact("Review limit", f["threshold"], "percent"),
                ],
                "tax": _sale(ctx, top_id, h["value"]),
                "tradeoffs": [
                    "Selling may trigger capital-gains tax (estimate below).",
                    f"If {sector} keeps outperforming, the client gains less.",
                ],
            }
        )
    opts.append(
        {
            "id": f"{f['id']}-redirect",
            "kind": "redirect",
            "title": "Send new money to other sectors",
            "summary": (
                f"Direct new SIPs to diversified funds with less {sector}. No tax now; the share falls "
                "as new money goes in."
            ),
            "impact": [
                _impact(f"{sector} above the limit", excess, "inr"),
                _impact(
                    "Main sources", ", ".join(ctx.holdings[i]["name"] for i, _ in sources[:3]) or "-", "text"
                ),
            ],
            "tax": None,
            "tradeoffs": ["Slow: depends on how much new money the client adds."],
        }
    )
    return opts


def _liquidity(f: dict[str, Any], ctx: ActionContext) -> list[dict[str, Any]]:
    gap = max((f["threshold"] - f["measured_value"]) * ctx.total, 0.0)
    return [
        {
            "id": f"{f['id']}-add",
            "kind": "add",
            "title": "Build a cash cushion in a liquid fund",
            "summary": "Put new money into a liquid fund until it reaches the target, so emergencies "
            "never force a sale of long-term investments at a bad time.",
            "impact": [
                _impact("Amount to reach the target", gap, "inr"),
                _impact("In cash or liquid funds now", f["measured_value"], "percent"),
                _impact("Target", f["threshold"], "percent"),
            ],
            "tax": None,
            "tradeoffs": ["Liquid funds earn less than equity over long periods."],
        },
        {
            "id": f"{f['id']}-elsewhere",
            "kind": "keep",
            "title": "Confirm the client has an emergency fund elsewhere",
            "summary": "Bank savings or deposits outside this portfolio may already cover this.",
            "impact": [_impact("Change", "None, if covered elsewhere", "text")],
            "tax": None,
            "tradeoffs": [],
        },
    ]


def _benchmark(f: dict[str, Any], ctx: ActionContext) -> list[dict[str, Any]]:
    lagging = sorted(
        (
            c
            for c in ctx.contribution.values()
            if c["held"] and c["vs_index"] is not None and c["vs_index"] < 0
        ),
        key=lambda c: c["vs_index"],
    )[:3]
    opts: list[dict[str, Any]] = []
    if lagging:
        opts.append(
            {
                "id": f"{f['id']}-review",
                "kind": "reduce",
                "title": "Review the holdings that trailed the index",
                "summary": (
                    "With the same money on the same dates, the index did better than these holdings. "
                    "Check whether each still has a clear reason to stay."
                ),
                "impact": [_impact(c["name"], c["vs_index"], "percent_points") for c in lagging],
                "tax": None,
                "tradeoffs": [
                    PAST_RETURNS_NOTE,
                    "Short periods of underperformance are normal for active funds.",
                ],
            }
        )
    opts.append(
        {
            "id": f"{f['id']}-index",
            "kind": "redirect",
            "title": "Use a low-cost index fund for the core",
            "summary": "Send new large-cap money to an index fund that tracks the benchmark, so this part "
            "of the portfolio cannot trail the index by much.",
            "impact": [_impact("Return vs the index now", -f["measured_value"], "percent_points")],
            "tax": None,
            "tradeoffs": ["An index fund will never beat the index either."],
        }
    )
    return opts


def _too_many(f: dict[str, Any], ctx: ActionContext) -> list[dict[str, Any]]:
    return [
        {
            "id": f"{f['id']}-simplify",
            "kind": "reduce",
            "title": "Simplify to fewer funds",
            "summary": "Start with the most overlapping pairs: they add the least diversification.",
            "impact": [
                _impact("Funds now", f["measured_value"], "count"),
                _impact("Guide", f["threshold"], "count"),
            ],
            "tax": None,
            "tradeoffs": ["Each sale may trigger tax; spread changes over time if needed."],
        }
    ]


# ------------------------------------------------------------------- planning (v1.2)


def _tax_aware_sale(
    ctx: ActionContext, classes: set[str], amount: float
) -> tuple[dict[str, Any] | None, list[tuple[str, float]]]:
    """Sell about `amount` from holdings in these asset classes, lowest gain first (least tax).

    Holdings whose value is mostly gain cost the most tax to sell, so they are used last.
    """
    cands = [h for h in ctx.holdings.values() if h["asset_class"] in classes and h["value"] > 0]
    cands.sort(key=lambda h: (h["gain"] / h["value"]) if h["value"] else 0.0)
    left, picks, ests = amount, [], []
    for h in cands:
        if left <= 1:
            break
        take = min(left, h["value"])
        iid = h["instrument_id"]
        if iid in ctx.lots and h["price"]:
            ests.append(
                estimate_sale(
                    ctx.lots[iid], take / h["price"], h["price"], ctx.valuation_date, h["asset_class"]
                )
            )
        picks.append((h["name"], take))
        left -= take
    est = combine(ests)
    return (est.to_dict() if est else None), picks


def _risk(f: dict[str, Any], ctx: ActionContext) -> list[dict[str, Any]]:
    ev = f["evidence"]
    eq, edge = f["measured_value"], f["threshold"]
    above = ev["direction"] == "above"
    move = abs(eq - edge) * ctx.total
    opts: list[dict[str, Any]] = []
    if above:
        tax, picks = _tax_aware_sale(ctx, {"equity"}, move)
        opts.append(
            {
                "id": f"{f['id']}-rebalance",
                "kind": "reduce",
                "title": "Rebalance: move money from equity to debt",
                "summary": (
                    f"Move about this much from equity into debt or liquid funds to bring equity back to "
                    f"the top of the {ev['profile'].lower()} range. FolioLens picks the holdings with the "
                    "smallest gains first, to keep the tax low."
                ),
                "impact": [
                    _impact("Amount to move", move, "inr"),
                    _impact("Equity now", eq, "percent"),
                    _impact("Equity after", edge, "percent"),
                    *[_impact(f"Sell from {n}", v, "inr") for n, v in picks[:3]],
                ],
                "tax": tax,
                "tradeoffs": ["Lower expected long-term return in exchange for a steadier ride."],
            }
        )
        new_money = eq * ctx.total / edge - ctx.total if edge > 0 else None
        if new_money and new_money > 0:
            opts.append(
                {
                    "id": f"{f['id']}-newmoney",
                    "kind": "redirect",
                    "title": "Rebalance with new money only",
                    "summary": "Put new money into debt funds until equity falls back into the range. "
                    "No tax now.",
                    "impact": [
                        _impact("New money into debt", new_money, "inr"),
                        _impact("Equity after", edge, "percent"),
                    ],
                    "tax": None,
                    "tradeoffs": ["Takes longer and needs the client to add this much."],
                }
            )
    else:
        tax, picks = _tax_aware_sale(ctx, {"debt", "cash"}, move)
        opts.append(
            {
                "id": f"{f['id']}-rebalance",
                "kind": "add",
                "title": "Rebalance: move money from debt to equity",
                "summary": (
                    f"Move about this much from debt into diversified equity funds to reach the bottom of "
                    f"the {ev['profile'].lower()} range, ideally in instalments over a few months."
                ),
                "impact": [
                    _impact("Amount to move", move, "inr"),
                    _impact("Equity now", eq, "percent"),
                    _impact("Equity after", edge, "percent"),
                    *[_impact(f"Sell from {n}", v, "inr") for n, v in picks[:3]],
                ],
                "tax": tax,
                "tradeoffs": ["More ups and downs; best spread over time rather than in one go."],
            }
        )
        new_money = (edge * ctx.total - eq * ctx.total) / (1 - edge) if edge < 1 else None
        if new_money and new_money > 0:
            opts.append(
                {
                    "id": f"{f['id']}-newmoney",
                    "kind": "redirect",
                    "title": "Rebalance with new money only",
                    "summary": "Put new money into diversified equity funds until equity reaches the range.",
                    "impact": [
                        _impact("New money into equity", new_money, "inr"),
                        _impact("Equity after", edge, "percent"),
                    ],
                    "tax": None,
                    "tradeoffs": ["Takes longer and needs the client to add this much."],
                }
            )
    opts.append(
        {
            "id": f"{f['id']}-review",
            "kind": "keep",
            "title": "Review the risk profile with the client",
            "summary": "If the client is comfortable with the current mix, update the questionnaire "
            "to match.",
            "impact": [
                _impact("Profile now", ev["profile"], "text"),
                _impact(
                    "Suggested equity", f"{ev['equity_min'] * 100:.0f}–{ev['equity_max'] * 100:.0f}%", "text"
                ),
            ],
            "tax": None,
            "tradeoffs": [
                "The profile should reflect the client's real ability and willingness to take risk."
            ],
        }
    )
    return opts


def _goal(f: dict[str, Any], ctx: ActionContext) -> list[dict[str, Any]]:
    ev = f["evidence"]
    rate, infl = ev["expected_return"], ev["inflation"]
    share = ev["set_aside"] / ctx.total if ctx.total else 0.0
    goal = Goal(
        ev["goal_id"],
        ev["goal"],
        ev["target_today"],
        date.fromisoformat(ev["target_date"]),
        ev["monthly_sip"],
        share,
    )
    opts: list[dict[str, Any]] = []
    req = ev["required_sip"]
    if req is not None and req > ev["monthly_sip"]:
        opts.append(
            {
                "id": f"{f['id']}-sip",
                "kind": "add",
                "title": f"Raise the monthly SIP to {_inr_word(req)}",
                "summary": "Invest more each month until the goal date, so the projection meets the target.",
                "impact": [
                    _impact("SIP now", ev["monthly_sip"], "inr"),
                    _impact("SIP needed", req, "inr"),
                    _impact("Extra each month", req - ev["monthly_sip"], "inr"),
                ],
                "tax": None,
                "tradeoffs": ["Needs room in the client's monthly budget."],
            }
        )
    yrs = years_to_reach(goal, ctx.total, rate, ctx.valuation_date, infl)
    if yrs is not None and yrs > ev["years"]:
        later = yrs - ev["years"]
        opts.append(
            {
                "id": f"{f['id']}-later",
                "kind": "keep",
                "title": f"Move the goal about {later:.1f} years later",
                "summary": "Keep the same SIP and give the money more time to grow.",
                "impact": [
                    _impact("Years to go now", ev["years"], "years"),
                    _impact("Years needed", yrs, "years"),
                ],
                "tax": None,
                "tradeoffs": ["Only works if the date can move."],
            }
        )
    reachable_today = ev["projected"] / (1 + infl) ** ev["years"] if ev["years"] > 0 else ev["projected"]
    opts.append(
        {
            "id": f"{f['id']}-target",
            "kind": "keep",
            "title": "Lower the target to what the plan can reach",
            "summary": "Keep the date and SIP, and agree a smaller target with the client.",
            "impact": [
                _impact("Target now (today's ₹)", ev["target_today"], "inr"),
                _impact("Reachable (today's ₹)", reachable_today, "inr"),
            ],
            "tax": None,
            "tradeoffs": ["The client gets less than they hoped for."],
        }
    )
    if ev["gap"] > 0 and ev["years"] > 0:
        lump = ev["gap"] / (1 + rate) ** ev["years"]
        opts.append(
            {
                "id": f"{f['id']}-lump",
                "kind": "add",
                "title": "Add a one-time amount now",
                "summary": "A lump sum invested today that would grow to cover the gap by the goal date.",
                "impact": [
                    _impact("One-time amount", lump, "inr"),
                    _impact("Gap at goal date", ev["gap"], "inr"),
                ],
                "tax": None,
                "tradeoffs": ["Needs spare money now, for example a bonus."],
            }
        )
    return opts


def _near_goal(f: dict[str, Any], ctx: ActionContext) -> list[dict[str, Any]]:
    ev = f["evidence"]
    move = ev["equity_in_set_aside"]
    tax, picks = _tax_aware_sale(ctx, {"equity"}, move)
    return [
        {
            "id": f"{f['id']}-derisk",
            "kind": "reduce",
            "title": f"Move the money for {ev['goal']} to safer funds",
            "summary": "Shift the equity part of this goal's money into debt or liquid funds, so a "
            "market fall "
            "close to the date cannot hurt it. Holdings with the smallest gains are used first.",
            "impact": [
                _impact("Amount to move", move, "inr"),
                _impact("Years to go", ev["years"], "years"),
                *[_impact(f"Sell from {n}", v, "inr") for n, v in picks[:3]],
            ],
            "tax": tax,
            "tradeoffs": ["Lower expected return on this money for the last few years."],
        },
        {
            "id": f"{f['id']}-gradual",
            "kind": "redirect",
            "title": "Move it gradually over the next 12 months",
            "summary": "Shift a twelfth each month, which spreads both the market timing and the tax.",
            "impact": [_impact("Each month", move / 12, "inr")],
            "tax": None,
            "tradeoffs": ["The money stays exposed to equity for a while longer."],
        },
    ]


def _inr_word(x: float) -> str:
    n = str(round(abs(x)))
    head, tail = n[:-3], n[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join([*groups, tail])


BUILDERS = {
    "fund_overlap": _overlap,
    "single_stock_concentration": _single_stock,
    "sector_concentration": _sector,
    "low_liquidity": _liquidity,
    "benchmark_underperformance": _benchmark,
    "too_many_funds": _too_many,
    "risk_mismatch": _risk,
    "goal_shortfall": _goal,
    "short_goal_in_equity": _near_goal,
}


def attach_options(findings: list[dict[str, Any]], ctx: ActionContext) -> list[dict[str, Any]]:
    for f in findings:
        builder = BUILDERS.get(f["type"])
        f["options"] = builder(f, ctx) if builder else []
    return findings
