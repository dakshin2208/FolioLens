import { AlertCircle, ArrowRight, Flag, FileUp, Plus, Search, Users, Wallet } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Kpi } from "../components/ReportView";
import {
  Avatar,
  Button,
  EmptyState,
  Field,
  Modal,
  Notice,
  PageHeader,
  Skeleton,
  StatusBadge,
  cx,
  inputCls,
  useDocumentTitle,
  useToast,
} from "../components/ui";
import { api } from "../lib/api";
import { date, inr, inrShort, pct, relativeTime } from "../lib/format";
import type { PortfolioSummary } from "../lib/types";

export function PortfoliosPage() {
  useDocumentTitle("Clients");
  const navigate = useNavigate();
  const toast = useToast();
  const [items, setItems] = useState<PortfolioSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [client, setClient] = useState("");
  const [name, setName] = useState("Core portfolio");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.portfolios().then(setItems).catch((e) => setError(e.message));
  }, []);

  async function create(e?: FormEvent) {
    e?.preventDefault();
    if (!client.trim()) return;
    setBusy(true);
    try {
      const p = await api.createPortfolio(name.trim() || "Core portfolio", client.trim());
      window.dispatchEvent(new Event("foliolens:portfolios"));
      toast("success", `Created ${p.client_name}. Upload a statement to build the first report.`);
      navigate(`/app/p/${p.id}?upload=1`);
    } catch (err) {
      toast("error", (err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const filtered = useMemo(
    () => (items ?? []).filter((p) => !q || `${p.client_name} ${p.name}`.toLowerCase().includes(q.toLowerCase())),
    [items, q],
  );
  const totals = useMemo(() => {
    const list = items ?? [];
    return {
      aum: list.reduce((s, p) => s + (p.current_value ?? 0), 0),
      flags: list.reduce((s, p) => s + (p.findings ?? 0), 0),
      attention: list.filter((p) => p.last_upload_status === "needs_review" || p.last_upload_status === "failed").length,
    };
  }, [items]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="My clients"
        subtitle="Every client you review, with their latest report. Click a client to open it."
        actions={<Button icon={Plus} onClick={() => setOpen(true)}>New client</Button>}
      />

      {error && <Notice level="error">{error}</Notice>}

      {!items && !error && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}</div>
          <Skeleton className="h-72 rounded-2xl" />
        </div>
      )}

      {items && items.length === 0 && (
        <div className="space-y-6">
          <EmptyState icon={Users} title="Add your first client" action={<Button icon={Plus} onClick={() => setOpen(true)}>New client</Button>}>
            Create a client, upload their CAS or broker export, and FolioLens builds the full review automatically.
          </EmptyState>
          <div className="grid gap-4 md:grid-cols-3">
            {[
              { icon: Users, t: "1. Create a client", d: "One portfolio per client. Use a name or an internal label." },
              { icon: FileUp, t: "2. Upload a statement", d: "CAMS/KFintech CAS PDF, Zerodha tradebook or our CSV template." },
              { icon: Flag, t: "3. Review and share", d: "A plain-English summary, options with tax estimates, and a client-ready report." },
            ].map((s) => (
              <div key={s.t} className="rounded-2xl border border-line bg-surface p-5 shadow-card">
                <s.icon size={18} className="text-accent" />
                <div className="mt-3 font-semibold text-ink">{s.t}</div>
                <p className="mt-1 text-[13px] text-muted">{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {items && items.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Kpi label="Money under review" icon={Wallet} value={inrShort(totals.aum)} sub={inr(totals.aum)} />
            <Kpi label="Clients" icon={Users} value={items.length} sub={`${items.filter((p) => p.current_value != null).length} with a report`} />
            <Kpi label="Points to discuss" icon={Flag} value={totals.flags} sub="Across all clients" />
            <Kpi label="Needs your attention" icon={AlertCircle} value={totals.attention} sub="Imports to check or retry" tone={totals.attention ? "bad" : undefined} />
          </div>

          <section className="overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4">
              <div className="relative w-full sm:w-80">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
                <input className={cx(inputCls, "h-9 pl-9")} placeholder="Search clients" value={q} onChange={(e) => setQ(e.target.value)} />
              </div>
              <span className="text-xs text-muted">{filtered.length} of {items.length}</span>
            </div>
            <div className="scroll-thin overflow-x-auto">
              <table className="w-full min-w-[760px] text-[13px]">
                <thead className="bg-surface-2 text-left text-[12.5px] text-muted">
                  <tr>
                    <th className="px-4 py-3 font-medium">Client</th>
                    <th className="px-4 py-3 text-right font-medium">Value</th>
                    <th className="px-4 py-3 text-right font-medium">Annual return</th>
                    <th className="px-4 py-3 text-right font-medium">To discuss</th>
                    <th className="px-4 py-3 font-medium">Last import</th>
                    <th className="px-4 py-3 font-medium">Valued as of</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="tabular divide-y divide-[var(--border)]">
                  {filtered.map((p) => (
                    <tr key={p.id} className="group cursor-pointer hover:bg-surface-2/50" onClick={() => navigate(`/app/p/${p.id}`)}>
                      <td className="px-4 py-3">
                        <Link to={`/app/p/${p.id}`} className="flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
                          <Avatar name={p.client_name} size={36} />
                          <div className="min-w-0">
                            <div className="truncate font-medium text-ink">{p.client_name}</div>
                            <div className="truncate text-xs text-muted">{p.name}</div>
                          </div>
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-ink">{p.current_value != null ? inr(p.current_value) : <span className="text-faint">No report</span>}</td>
                      <td className={cx("px-4 py-3 text-right font-medium", p.xirr != null && p.xirr < 0 ? "text-bad" : "text-ink")}>{pct(p.xirr)}</td>
                      <td className="px-4 py-3 text-right">
                        {p.findings ? <span className="inline-flex min-w-6 justify-center rounded-full bg-warn-soft px-1.5 text-xs font-semibold text-warn">{p.findings}</span> : <span className="text-faint">{p.findings ?? "–"}</span>}
                      </td>
                      <td className="px-4 py-3">{p.last_upload_status ? <StatusBadge status={p.last_upload_status} /> : <span className="text-xs text-faint">No uploads</span>}</td>
                      <td className="px-4 py-3 text-xs text-muted">{p.valuation_date ? date(p.valuation_date) : `Created ${relativeTime(p.created_at)}`}</td>
                      <td className="px-4 py-3 text-right">
                        <ArrowRight size={16} className="inline text-faint transition group-hover:translate-x-0.5 group-hover:text-ink" />
                      </td>
                    </tr>
                  ))}
                  {filtered.length === 0 && (
                    <tr><td colSpan={7} className="px-4 py-10 text-center text-muted">No clients match “{q}”.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="New client"
        description="One portfolio per client. You'll upload a statement next."
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button loading={busy} disabled={!client.trim()} onClick={() => create()}>Create and upload</Button>
          </>
        }
      >
        <form onSubmit={create} className="space-y-4">
          <Field label="Client name or label" hint="Avoid PAN or account numbers; a name or internal code is enough.">
            <input className={inputCls} required maxLength={120} value={client} onChange={(e) => setClient(e.target.value)} placeholder="e.g. R. Sharma" />
          </Field>
          <Field label="Portfolio name">
            <input className={inputCls} required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <button type="submit" className="hidden" />
        </form>
      </Modal>
    </div>
  );
}
