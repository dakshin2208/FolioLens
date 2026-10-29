import { useCallback, useState } from "react";

import { inr, pct } from "./format";
import type { ActionOption } from "./types";

/**
 * The options an advisor ticks ("include in the client report"), remembered per client in this
 * browser. They are a working choice, not part of the calculated report, so they never change
 * any number.
 */
const key = (k: string) => `foliolens.plan.${k}`;

export function readPlan(storageKey: string): string[] {
  try {
    const raw = localStorage.getItem(key(storageKey));
    const v = raw ? JSON.parse(raw) : [];
    return Array.isArray(v) ? v.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function usePlan(storageKey: string) {
  const [selected, setSelected] = useState<string[]>(() => readPlan(storageKey));
  const toggle = useCallback(
    (id: string) => {
      setSelected((cur) => {
        const next = cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id];
        try {
          localStorage.setItem(key(storageKey), JSON.stringify(next));
        } catch {
          /* storage unavailable: the choice lasts until the page is closed */
        }
        return next;
      });
    },
    [storageKey],
  );
  return { selected, toggle };
}

/** Format one "impact" value of an option for display. */
export function impactText(i: ActionOption["impact"][number]): string {
  const v = i.value;
  if (v == null) return "–";
  if (typeof v === "string") return v;
  switch (i.unit) {
    case "inr":
      return inr(v);
    case "percent":
      return pct(v);
    case "percent_points":
      return `${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(1)} pts a year`;
    case "count":
      return String(Math.round(v));
    case "years":
      return `${v.toFixed(1)} years`;
    default:
      return String(v);
  }
}

/** One line for the tax estimate: "About ₹7,601 tax (₹23,226 if the ₹1.25 lakh exemption is used up)". */
export function taxLine(t: NonNullable<ActionOption["tax"]>): string {
  if (t.gain <= 0) return `No tax expected: this sale would be at a loss of ${inr(-t.gain)}.`;
  if (!t.equity_rules || t.tax_if_exemption_unused == null) return `Gain of about ${inr(t.gain)}, taxed by fund-type rules (often the client's slab rate).`;
  const a = t.tax_if_exemption_unused;
  const b = t.tax_if_exemption_used ?? a;
  return a === b
    ? `Estimated tax about ${inr(a)} on a gain of ${inr(t.gain)}.`
    : `Estimated tax about ${inr(a)} on a gain of ${inr(t.gain)} (up to ${inr(b)} if the client's ₹1.25 lakh yearly exemption is already used).`;
}
