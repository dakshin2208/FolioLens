import { CheckCircle2, Flag, Plus, Save, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../lib/api";
import { inr, pct } from "../lib/format";
import type { GoalInput, RiskProfile, RiskQuestion } from "../lib/types";
import { Badge, Button, Card, Help, Notice, Skeleton, cx, inputCls, useToast } from "./ui";

const EMPTY_GOAL = (): GoalInput => ({
  name: "",
  target_amount: 0,
  target_date: `${new Date().getFullYear() + 5}-04-01`,
  monthly_sip: 0,
  share_of_portfolio: 0,
});

/**
 * The client's risk questionnaire and goals. Saving stores them and rebuilds the report, so the
 * Goals & risk tab, the summary and the options all reflect the plan straight away.
 */
export function PlanEditor({ portfolioId, onSaved }: { portfolioId: string; onSaved: () => Promise<void> }) {
  const toast = useToast();
  const [questions, setQuestions] = useState<RiskQuestion[] | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [goals, setGoals] = useState<GoalInput[]>([]);
  const [profile, setProfile] = useState<RiskProfile | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    Promise.all([api.riskQuestions(), api.plan(portfolioId)])
      .then(([q, p]) => {
        setQuestions(q.questions);
        setAnswers(p.risk_answers);
        setGoals(p.goals);
        setProfile(p.profile);
      })
      .catch((e) => setError((e as Error).message));
  }, [portfolioId]);

  const totalShare = useMemo(() => goals.reduce((s, g) => s + (Number(g.share_of_portfolio) || 0), 0), [goals]);
  const invalidGoal = goals.find((g) => !g.name.trim() || !(g.target_amount > 0) || !g.target_date);

  function edit(i: number, patch: Partial<GoalInput>) {
    setGoals((gs) => gs.map((g, k) => (k === i ? { ...g, ...patch } : g)));
    setDirty(true);
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const saved = await api.savePlan(portfolioId, { risk_answers: answers, goals });
      setProfile(saved.profile);
      setGoals(saved.goals);
      setDirty(false);
      await api.refreshReport(portfolioId).catch(() => undefined);
      await onSaved();
      toast("success", "Plan saved. The report now checks the portfolio against it.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (error && !questions) return <Notice level="error">{error}</Notice>;
  if (!questions) return <Skeleton className="h-96 rounded-2xl" />;
  const answered = questions.filter((q) => answers[q.id] != null).length;

  return (
    <div className="space-y-6">
      <Notice level="info" title="Why this matters">
        Numbers alone can't say if a portfolio is right for a client. With a risk profile and goals, FolioLens checks whether the
        portfolio's risk fits the client and whether each goal is on track, and suggests options when it isn't.
      </Notice>

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Card title="Risk profile" subtitle={`Six quick questions · ${answered} of ${questions.length} answered`} icon={ShieldCheck}>
          <ol className="space-y-5">
            {questions.map((q, qi) => (
              <li key={q.id}>
                <div className="text-[14px] font-medium text-ink">{qi + 1}. {q.text}</div>
                <div className="mt-2 flex flex-wrap gap-2" role="radiogroup" aria-label={q.text}>
                  {q.options.map((o, oi) => {
                    const on = answers[q.id] === oi;
                    return (
                      <button
                        key={o}
                        type="button"
                        role="radio"
                        aria-checked={on}
                        onClick={() => { setAnswers((a) => ({ ...a, [q.id]: oi })); setDirty(true); }}
                        className={cx(
                          "rounded-lg border px-3 py-1.5 text-left text-[13px] transition",
                          on ? "border-accent bg-accent-soft font-medium text-ink ring-2 ring-accent/15" : "border-line text-ink-2 hover:border-line-strong hover:bg-surface-2",
                        )}
                      >
                        {o}
                      </button>
                    );
                  })}
                </div>
              </li>
            ))}
          </ol>
        </Card>

        <div className="space-y-4 xl:sticky xl:top-6">
          <Card title="Result">
            {profile ? (
              <>
                <div className="text-[22px] font-semibold tracking-tight text-ink">{profile.category}</div>
                <div className="mt-1 text-[13px] text-muted">Score {profile.score.toFixed(0)} of 100</div>
                <div className="mt-3 rounded-xl bg-surface-2 p-3 text-[13px] text-ink-2">
                  Suggested equity: <strong className="text-ink">{pct(profile.equity_min, 0)} to {pct(profile.equity_max, 0)}</strong> of the portfolio.
                </div>
                {dirty && <p className="mt-2 text-xs text-warn">Save to update the result.</p>}
              </>
            ) : (
              <p className="text-[13px] text-muted">Answer the questions and save to see the client's risk profile.</p>
            )}
            <p className="mt-3 text-[11.5px] leading-relaxed text-muted">
              A simple six-question model to start the conversation. For SEBI compliance, also use your firm's own risk-profiling process.
            </p>
          </Card>
        </div>
      </div>

      <Card
        title="Goals"
        subtitle="What the client is saving for. Amounts are in today's rupees; FolioLens adds inflation."
        icon={Flag}
        action={<Button size="sm" variant="secondary" icon={Plus} disabled={goals.length >= 10} onClick={() => { setGoals((g) => [...g, EMPTY_GOAL()]); setDirty(true); }}>Add goal</Button>}
      >
        {goals.length === 0 ? (
          <div className="rounded-xl border border-dashed border-line-strong p-6 text-center text-[13.5px] text-muted">
            No goals yet. Add one, for example "Child's education", "Retirement" or "Home down payment".
          </div>
        ) : (
          <div className="space-y-3">
            {goals.map((g, i) => (
              <div key={g.id ?? `new-${i}`} className="grid gap-3 rounded-xl border border-line p-4 md:grid-cols-[1.4fr_1fr_1fr_1fr_0.8fr_auto] md:items-end">
                <GoalField label="Goal">
                  <input className={inputCls} value={g.name} maxLength={80} placeholder="e.g. Retirement" onChange={(e) => edit(i, { name: e.target.value })} />
                </GoalField>
                <GoalField label="Target (today's ₹)">
                  <input className={inputCls} type="number" min={0} step={10000} value={g.target_amount || ""} onChange={(e) => edit(i, { target_amount: Number(e.target.value) })} />
                </GoalField>
                <GoalField label="Needed by">
                  <input className={inputCls} type="date" value={g.target_date} onChange={(e) => edit(i, { target_date: e.target.value })} />
                </GoalField>
                <GoalField label="Monthly SIP (₹)">
                  <input className={inputCls} type="number" min={0} step={1000} value={g.monthly_sip || ""} onChange={(e) => edit(i, { monthly_sip: Number(e.target.value) })} />
                </GoalField>
                <GoalField label={<>Set aside (%) <Help>The share of today's portfolio meant for this goal. All goals together can use up to 100%.</Help></>}>
                  <input className={inputCls} type="number" min={0} max={100} step={5} value={Math.round((g.share_of_portfolio || 0) * 1000) / 10 || ""} onChange={(e) => edit(i, { share_of_portfolio: Math.max(0, Math.min(1, Number(e.target.value) / 100)) })} />
                </GoalField>
                <button className="mb-1 rounded-lg p-2 text-muted hover:bg-bad-soft hover:text-bad" aria-label={`Remove ${g.name || "goal"}`} onClick={() => { setGoals((gs) => gs.filter((_, k) => k !== i)); setDirty(true); }}>
                  <Trash2 size={16} />
                </button>
                {g.target_amount > 0 && <div className="text-xs text-muted md:col-span-6">{inr(g.target_amount)} in today's money</div>}
              </div>
            ))}
            <div className={cx("text-[12.5px]", totalShare > 1 ? "font-medium text-bad" : "text-muted")}>
              Set aside in total: {pct(totalShare, 0)} of the portfolio{totalShare > 1 ? " (must be 100% or less)" : ""}
            </div>
          </div>
        )}
      </Card>

      {error && <Notice level="error">{error}</Notice>}
      <div className="flex flex-wrap items-center justify-end gap-3">
        {!dirty && profile && <Badge tone="good" icon={CheckCircle2}>Saved</Badge>}
        {invalidGoal && <span className="text-xs text-muted">Every goal needs a name, a target and a date.</span>}
        <Button size="lg" icon={Save} loading={busy} disabled={!dirty || totalShare > 1 || Boolean(invalidGoal)} onClick={save}>
          Save and update report
        </Button>
      </div>
    </div>
  );
}

function GoalField({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <label className="block min-w-0">
      <span className="mb-1 flex items-center gap-1 text-[12px] font-medium text-muted">{label}</span>
      {children}
    </label>
  );
}
