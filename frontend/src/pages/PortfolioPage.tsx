import {
  AlertTriangle,
  BarChart3,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  EyeOff,
  FileSpreadsheet,
  FileText,
  FileUp,
  History,
  Loader2,
  Lock,
  MoreHorizontal,
  Printer,
  ReceiptText,
  RefreshCw,
  Search,
  Send,
  Target,
  ShieldCheck,
  Trash2,
  UploadCloud,
  X,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { Breadcrumbs } from "../components/Layout";
import { PlanEditor } from "../components/PlanEditor";
import { ReportView } from "../components/ReportView";
import {
  Avatar,
  Badge,
  Button,
  Card,
  Checkbox,
  EmptyState,
  Field,
  Modal,
  Notice,
  PageHeader,
  PageSkeleton,
  Segmented,
  Skeleton,
  StatusBadge,
  Stepper,
  Tabs,
  buttonCls,
  cx,
  inputCls,
  useDocumentTitle,
  useToast,
} from "../components/ui";
import { api, ApiError } from "../lib/api";
import { date, inr, num, relativeTime, titleCase } from "../lib/format";
import type { Instrument, Portfolio, Report, Transaction, Upload } from "../lib/types";

type Tab = "report" | "plan" | "statements" | "ledger";

/** Remount per client so tabs, filters and polling never leak between clients. */
export function PortfolioPage() {
  const { id = "" } = useParams();
  return <ClientPortfolio key={id} id={id} />;
}

function ClientPortfolio({ id }: { id: string }) {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [tab, setTab] = useState<Tab>(params.get("upload") ? "statements" : "report");
  const [error, setError] = useState<string | null>(null);
  const [menu, setMenu] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const prevStatus = useRef<Record<string, string>>({});
  useDocumentTitle(portfolio?.client_name ?? "Client");

  const load = useCallback(async () => {
    try {
      const [p, u] = await Promise.all([api.portfolio(id), api.uploads(id)]);
      setPortfolio(p);
      setUploads(u);
      try {
        setReport(await api.report(id));
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) setReport(null);
        else throw e;
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while a statement is being processed in the background.
  const busy = uploads.some((u) => u.status === "queued" || u.status === "processing");
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(load, 1500);
    return () => clearInterval(t);
  }, [busy, load]);

  // Toast when a background import finishes.
  useEffect(() => {
    for (const u of uploads) {
      const before = prevStatus.current[u.id];
      if (before && (before === "queued" || before === "processing") && before !== u.status) {
        if (u.status === "completed") {
          toast("success", `${u.filename} imported. The report is up to date.`);
          setTab("report");
        } else if (u.status === "needs_review") toast("info", `${u.filename} needs a quick review before it's included.`);
        else if (u.status === "failed") toast("error", `${u.filename} could not be imported.`);
        window.dispatchEvent(new Event("foliolens:portfolios"));
      }
      prevStatus.current[u.id] = u.status;
    }
  }, [uploads, toast]);

  useEffect(() => {
    if (portfolio && !report && uploads.length === 0) setTab("statements");
  }, [portfolio, report, uploads.length]);

  function changeTab(t: Tab) {
    setTab(t);
    if (params.get("upload")) setParams({}, { replace: true });
  }

  async function remove() {
    await api.deletePortfolio(id);
    window.dispatchEvent(new Event("foliolens:portfolios"));
    toast("success", "Client data deleted.");
    navigate("/app");
  }

  if (error)
    return (
      <div className="space-y-6">
        <Breadcrumbs items={[{ label: "My clients", to: "/app" }, { label: "Not found" }]} />
        <EmptyState icon={XCircle} title="This client isn't available" action={<Button variant="secondary" onClick={() => navigate("/app")}>Back to clients</Button>}>
          {error}
        </EmptyState>
      </div>
    );
  if (!portfolio) return <PageSkeleton />;

  const needsReview = uploads.find((u) => u.status === "needs_review");
  const latest = uploads[0];
  const ready = report?.status === "ok";
  const hasPlan = Boolean(report?.planning?.available);
  const steps = [
    { label: "Profile & goals", hint: hasPlan ? "Saved" : "Optional, recommended", state: hasPlan ? "done" : tab === "plan" ? "current" : "todo", onClick: () => changeTab("plan") },
    { label: "Add a statement", hint: uploads.length ? `${uploads.length} uploaded` : "CAS PDF or broker CSV", state: uploads.length ? "done" : "current", onClick: () => changeTab("statements") },
    { label: "Check the import", hint: needsReview ? "Needs your confirmation" : busy ? "Reading…" : uploads.length ? "Nothing to fix" : "Automatic", state: needsReview || busy ? "current" : uploads.some((u) => u.status === "completed") ? "done" : "todo", onClick: needsReview ? () => changeTab("statements") : undefined },
    { label: "Review the report", hint: ready ? "Summary, risks and options" : "Built automatically", state: ready ? "current" : "todo", onClick: ready ? () => changeTab("report") : undefined },
    { label: "Share with the client", hint: "Report + ready email", state: "todo", onClick: ready ? () => navigate(`/app/p/${id}/share`) : undefined },
  ] as const;

  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: "My clients", to: "/app" }, { label: portfolio.client_name }]} />
      <PageHeader
        leading={<Avatar name={portfolio.client_name} size={52} />}
        title={portfolio.client_name}
        subtitle={`${portfolio.name} · client since ${date(portfolio.created_at.slice(0, 10))}`}
        meta={
          <>
            {report?.status === "ok" && <Badge tone="good" icon={CheckCircle2}>Report ready</Badge>}
            {needsReview && <Badge tone="warn" icon={AlertTriangle}>Import needs review</Badge>}
            {busy && <Badge tone="info" icon={Loader2}>Processing statement</Badge>}
            {latest && <span className="text-xs text-muted">Last import {relativeTime(latest.created_at)}</span>}
          </>
        }
        actions={
          <>
            {ready && tab === "report" && (
              <Button variant="secondary" icon={Printer} onClick={() => window.print()}>Print</Button>
            )}
            <Button variant={ready ? "secondary" : "primary"} icon={FileUp} onClick={() => changeTab("statements")}>Upload statement</Button>
            {ready && <Link to={`/app/p/${id}/share`} className={buttonCls("primary")}><Send size={16} />Client report</Link>}
            <div className="relative">
              <Button variant="secondary" aria-label="More actions" onClick={() => setMenu((m) => !m)} className="!px-2.5"><MoreHorizontal size={16} /></Button>
              {menu && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setMenu(false)} />
                  <div className="pop-in absolute right-0 z-20 mt-2 w-56 rounded-xl border border-line bg-surface p-1.5 shadow-float">
                    <button className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[13px] text-ink hover:bg-surface-2"
                      onClick={async () => { setMenu(false); await api.refreshReport(id).catch(() => undefined); await load(); toast("success", "Report recalculated."); }}>
                      <RefreshCw size={15} /> Recalculate report
                    </button>
                    <button className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[13px] text-bad hover:bg-bad-soft"
                      onClick={() => { setMenu(false); setConfirmDelete(true); }}>
                      <Trash2 size={15} /> Delete client data
                    </button>
                  </div>
                </>
              )}
            </div>
          </>
        }
      />

      <div className="no-print"><Stepper steps={steps.map((x) => ({ ...x }))} /></div>

      <Tabs<Tab>
        value={tab}
        onChange={changeTab}
        className="no-print"
        tabs={[
          { id: "report", label: "Report", icon: BarChart3 },
          { id: "plan", label: "Profile & goals", icon: Target },
          { id: "statements", label: "Statements", icon: FileUp, count: uploads.length, dot: Boolean(needsReview) },
          { id: "ledger", label: "Transactions", icon: ReceiptText },
        ]}
      />

      <div key={tab} className="fade-in">
        {tab === "report" && (
          <div className="space-y-5">
            {needsReview && (
              <Notice level="warning" title="A statement needs your review"
                action={<Button size="sm" variant="secondary" onClick={() => changeTab("statements")}>Review now</Button>}>
                Some transactions are excluded until you confirm how they map.
              </Notice>
            )}
            {busy && <ProcessingBanner upload={uploads.find((u) => u.status === "queued" || u.status === "processing")!} />}
            {report ? (
              <ReportView
                report={report}
                storageKey={id}
                shareHref={`/app/p/${id}/share`}
                onRefresh={async () => { await api.refreshReport(id); await load(); window.dispatchEvent(new Event("foliolens:portfolios")); toast("success", "Report updated."); }}
                onEditPlan={() => changeTab("plan")}
              />
            ) : (
              !busy && (
                <EmptyState icon={BarChart3} title="No report yet" action={<Button icon={FileUp} onClick={() => changeTab("statements")}>Upload a statement</Button>}>
                  Upload {portfolio.client_name}'s CAS or broker export. The report is built automatically.
                </EmptyState>
              )
            )}
          </div>
        )}
        {tab === "statements" && (
          <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
            <div className="space-y-5">
              {needsReview && <ReviewPanel key={needsReview.id} upload={needsReview} onDone={async () => { await load(); window.dispatchEvent(new Event("foliolens:portfolios")); setTab("report"); toast("success", "Review saved. The report now includes every mapped scheme."); }} />}
              {busy && <ProcessingBanner upload={uploads.find((u) => u.status === "queued" || u.status === "processing")!} />}
              <UploadWizard portfolioId={id} onUploaded={load} collapsed={Boolean(needsReview) || busy} />
            </div>
            <div className="space-y-5">
              <UploadHistory uploads={uploads} />
              <PrivacyCard />
            </div>
          </div>
        )}
        {tab === "ledger" && <Ledger portfolioId={id} />}
        {tab === "plan" && <PlanEditor portfolioId={id} onSaved={async () => { await load(); window.dispatchEvent(new Event("foliolens:portfolios")); }} />}
      </div>

      <DeleteModal open={confirmDelete} name={portfolio.client_name} onClose={() => setConfirmDelete(false)} onConfirm={remove} />
    </div>
  );
}

/* ------------------------------------------------------------- Processing */

const STEPS = ["Uploaded", "Reading statement", "Matching & reconciling", "Building report"];

function ProcessingBanner({ upload }: { upload: Upload }) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((x) => x + 1), 900);
    return () => clearInterval(t);
  }, []);
  const active = upload.status === "queued" ? 1 : Math.min(3, 1 + Math.floor(tick / 2));
  return (
    <div className="rounded-2xl border border-accent/20 bg-accent-soft p-5 shadow-card">
      <div className="flex items-center gap-3">
        <Loader2 size={18} className="animate-spin text-accent" />
        <div className="text-sm font-semibold text-ink">Analysing {upload.filename}</div>
      </div>
      <ol className="mt-4 grid gap-2 sm:grid-cols-4">
        {STEPS.map((s, i) => (
          <li key={s} className="flex items-center gap-2 text-[13px]">
            <span className={cx("grid h-5 w-5 shrink-0 place-items-center rounded-full text-[10px] font-bold",
              i < active ? "bg-accent text-accent-ink" : i === active ? "bg-accent/15 text-accent ring-2 ring-accent/30" : "bg-surface-3 text-faint")}>
              {i < active ? <Check size={12} strokeWidth={3} /> : i + 1}
            </span>
            <span className={i <= active ? "text-ink" : "text-faint"}>{s}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/* --------------------------------------------------------------- Uploader */

const TYPES: { id: string; icon: LucideIcon; title: string; desc: string; ext: string; accept: string }[] = [
  { id: "cas_pdf", icon: FileText, title: "Mutual fund CAS", desc: "CAMS / KFintech detailed statement", ext: "PDF", accept: ".pdf,application/pdf" },
  { id: "zerodha_tradebook", icon: FileSpreadsheet, title: "Zerodha tradebook", desc: "Console › Reports › Tradebook", ext: "CSV", accept: ".csv,text/csv" },
  { id: "generic_csv", icon: FileSpreadsheet, title: "FolioLens CSV", desc: "Any other source, via our template", ext: "CSV", accept: ".csv,text/csv" },
];

const TEMPLATE =
  "date,isin,symbol,name,type,units,price,amount\n2024-01-05,INF000000000,,Example Equity Fund - Direct Growth,buy,100.000,50.00,5000.00\n";

function UploadWizard({ portfolioId, onUploaded, collapsed }: { portfolioId: string; onUploaded: () => void; collapsed?: boolean }) {
  const toast = useToast();
  const [expanded, setExpanded] = useState(false);
  const [fileType, setFileType] = useState("cas_pdf");
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [consent, setConsent] = useState(false);
  const [consentText, setConsentText] = useState("");
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const type = TYPES.find((t) => t.id === fileType)!;

  useEffect(() => {
    api.consentText().then((c) => setConsentText(c.text)).catch(() => undefined);
  }, []);

  function pick(f: File | undefined | null) {
    setError(null);
    if (!f) return;
    const ext = f.name.toLowerCase().split(".").pop();
    if (ext !== type.ext.toLowerCase()) {
      setError(`${type.title} must be a .${type.ext.toLowerCase()} file.`);
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      setError("The file is larger than 10 MB.");
      return;
    }
    setFile(f);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDrag(false);
    pick(e.dataTransfer.files?.[0]);
  }

  async function submit() {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("file_type", fileType);
    form.append("consent", String(consent));
    if (fileType === "cas_pdf") form.append("password", password);
    setBusy(true);
    setError(null);
    try {
      await api.createUpload(portfolioId, form);
      setFile(null);
      setPassword("");
      setConsent(false);
      toast("info", "Statement uploaded. Analysing in the background…");
      onUploaded();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function downloadTemplate() {
    const url = URL.createObjectURL(new Blob([TEMPLATE], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "foliolens_template.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const ready = file && consent && (fileType !== "cas_pdf" || password.length > 0);

  if (collapsed && !expanded)
    return (
      <button onClick={() => setExpanded(true)} className="flex w-full items-center justify-between rounded-2xl border border-dashed border-line-strong bg-surface px-5 py-4 text-left text-sm hover:bg-surface-2/50">
        <span className="flex items-center gap-3 font-medium text-ink"><UploadCloud size={18} className="text-accent" />Upload another statement</span>
        <ChevronRight size={16} className="text-muted" />
      </button>
    );

  return (
    <Card title="Upload a statement" subtitle="Files are deleted as soon as they're parsed. Passwords are never stored." icon={UploadCloud}>
      <div className="space-y-5">
        <div>
          <div className="mb-2 text-[13px] font-medium text-ink">1. Statement type</div>
          <div className="grid gap-3 sm:grid-cols-3" role="radiogroup">
            {TYPES.map((t) => {
              const active = t.id === fileType;
              return (
                <button
                  key={t.id}
                  role="radio"
                  aria-checked={active}
                  onClick={() => { setFileType(t.id); setFile(null); setError(null); }}
                  className={cx(
                    "relative rounded-xl border p-3.5 text-left transition",
                    active ? "border-accent bg-accent-soft/50 ring-4 ring-accent/10" : "border-line hover:border-line-strong hover:bg-surface-2/50",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <t.icon size={18} className={active ? "text-accent" : "text-muted"} />
                    <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-muted">{t.ext}</span>
                  </div>
                  <div className="mt-2.5 text-[13px] font-semibold text-ink">{t.title}</div>
                  <div className="mt-0.5 text-xs text-muted">{t.desc}</div>
                  {active && <CheckCircle2 size={16} className="absolute -right-1.5 -top-1.5 rounded-full bg-surface text-accent" />}
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between text-[13px]">
            <span className="font-medium text-ink">2. File</span>
            {fileType === "generic_csv" && (
              <button onClick={downloadTemplate} className="inline-flex items-center gap-1.5 font-medium text-accent hover:underline"><Download size={14} />Template</button>
            )}
          </div>
          {file ? (
            <div className="flex items-center gap-3 rounded-xl border border-line bg-surface-2/50 p-3.5">
              <span className="grid h-10 w-10 place-items-center rounded-lg bg-accent-soft text-accent"><type.icon size={18} /></span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-medium text-ink">{file.name}</div>
                <div className="text-xs text-muted">{(file.size / 1024).toFixed(0)} KB · ready</div>
              </div>
              <button className="rounded-lg p-1.5 text-muted hover:bg-surface-3 hover:text-ink" onClick={() => setFile(null)} aria-label="Remove file"><X size={16} /></button>
            </div>
          ) : (
            <div
              onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={onDrop}
              onClick={() => input.current?.click()}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
              role="button"
              tabIndex={0}
              className={cx(
                "flex cursor-pointer flex-col items-center rounded-xl border-2 border-dashed px-6 py-9 text-center transition",
                drag ? "border-accent bg-accent-soft/60" : "border-line-strong hover:border-accent/50 hover:bg-surface-2/50",
              )}
            >
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-surface shadow-pop ring-1 ring-line"><UploadCloud size={20} className="text-accent" /></span>
              <div className="mt-3 text-sm font-medium text-ink">Drop the {type.ext} here, or <span className="text-accent">browse</span></div>
              <div className="mt-1 text-xs text-muted">{type.title} · up to 10 MB</div>
            </div>
          )}
          <input ref={input} type="file" className="hidden" accept={type.accept} onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
        </div>

        {fileType === "cas_pdf" && (
          <Field label="3. PDF password" hint="For CAMS / KFintech CAS this is usually the investor's PAN in capital letters. Held in memory for 10 minutes, never saved.">
            <div className="relative">
              <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
              <input className={cx(inputCls, "pl-9 pr-10")} type={showPw ? "text" : "password"} autoComplete="off" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Type the PDF password" />
              <button type="button" className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-faint hover:text-ink" onClick={() => setShowPw((s) => !s)} aria-label={showPw ? "Hide password" : "Show password"}>
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </Field>
        )}
        {fileType === "generic_csv" && (
          <p className="rounded-lg bg-surface-2 px-3 py-2.5 font-mono text-[11.5px] leading-relaxed text-ink-2">
            date, isin, symbol, name, type, units, price, amount
            <span className="mt-1 block font-sans text-muted">type: buy · sell · dividend_payout · dividend_reinvest · switch_in · switch_out</span>
          </p>
        )}

        <div className="rounded-xl border border-line p-3.5">
          <Checkbox checked={consent} onChange={setConsent}>{consentText || "I confirm I am authorised to process this client's statement."}</Checkbox>
        </div>

        {error && <Notice level="error">{error}</Notice>}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-xs text-muted"><ShieldCheck size={14} className="text-good" /> Encrypted in transit · deleted after parsing</span>
          <div className="flex items-center gap-3">
            {!ready && <span className="text-xs text-muted">{!file ? "Add a file" : fileType === "cas_pdf" && !password ? "Enter the password" : !consent ? "Tick the consent box" : ""}</span>}
            <Button size="lg" icon={BarChart3} loading={busy} disabled={!ready} onClick={submit}>Upload and analyse</Button>
          </div>
        </div>
      </div>
    </Card>
  );
}

/* ----------------------------------------------------------------- Review */

function ReviewPanel({ upload, onDone }: { upload: Upload; onDone: () => void }) {
  const unmatched = upload.review.unmatched ?? [];
  const recon = upload.review.reconciliation ?? [];
  const bad = recon.filter((r) => !r.ok);
  const [choices, setChoices] = useState<Record<string, { id: string; name: string }>>(() =>
    Object.fromEntries(unmatched.filter((u) => u.suggestion).map((u) => [u.raw_identifier, { id: u.suggestion!.instrument_id, name: u.suggestion!.name }])),
  );
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mapped = unmatched.filter((u) => choices[u.raw_identifier]).length;

  async function save() {
    setError(null);
    setBusy(true);
    try {
      await api.review(upload.id, {
        mappings: Object.entries(choices).map(([raw_identifier, inst]) => ({ raw_identifier, instrument_id: inst.id })),
        acknowledge_reconciliation: ack,
      });
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-warn/30 bg-surface shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-warn/20 bg-warn-soft/60 px-5 py-4">
        <div className="flex items-start gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-warn-soft text-warn ring-1 ring-warn/20"><AlertTriangle size={18} /></span>
          <div>
            <h2 className="text-[15px] font-semibold text-ink">Review {upload.filename}</h2>
            <p className="mt-0.5 text-[13px] text-ink-2">Nothing is guessed. Confirm each item and the report rebuilds automatically.</p>
          </div>
        </div>
        <div className="flex gap-2 text-xs">
          {upload.review.inserted != null && <Badge tone="neutral">{upload.review.inserted} transactions read</Badge>}
          {unmatched.length > 0 && <Badge tone={mapped === unmatched.length ? "good" : "warn"}>{mapped}/{unmatched.length} mapped</Badge>}
        </div>
      </div>

      <div className="space-y-6 p-5">
        {unmatched.length > 0 && (
          <div>
            <h3 className="mb-1 text-[13px] font-semibold text-ink">Match each scheme to an instrument</h3>
            <p className="mb-3 text-xs text-muted">Unmapped transactions stay excluded from the analysis until you map them.</p>
            <ul className="space-y-3">
              {unmatched.map((u) => (
                <li key={u.raw_identifier} className="rounded-xl border border-line p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-[13px] font-medium text-ink">{u.raw_name ?? u.raw_identifier}</div>
                      <div className="mt-0.5 font-mono text-[11px] text-muted">{u.raw_identifier} · {u.count} transactions</div>
                    </div>
                    {choices[u.raw_identifier] ? <Badge tone="good" icon={Check}>Mapped</Badge> : <Badge tone="warn">Not mapped</Badge>}
                  </div>
                  <InstrumentPicker
                    value={choices[u.raw_identifier]}
                    suggestion={u.suggestion}
                    onChange={(inst) => setChoices((c) => ({ ...c, [u.raw_identifier]: inst }))}
                    onClear={() => setChoices((c) => { const n = { ...c }; delete n[u.raw_identifier]; return n; })}
                  />
                </li>
              ))}
            </ul>
          </div>
        )}

        {recon.length > 0 && (
          <div>
            <h3 className="mb-1 text-[13px] font-semibold text-ink">Unit reconciliation</h3>
            <p className="mb-3 text-xs text-muted">Units rebuilt from transactions should equal the closing balance printed on the statement.</p>
            <div className="scroll-thin overflow-x-auto rounded-xl border border-line">
              <table className="w-full min-w-[560px] text-[13px]">
                <thead className="bg-surface-2 text-left text-[12.5px] text-muted">
                  <tr>
                    <th className="px-3 py-2 font-medium">Scheme</th>
                    <th className="px-3 py-2 text-right font-medium">From transactions</th>
                    <th className="px-3 py-2 text-right font-medium">On statement</th>
                    <th className="px-3 py-2 text-right font-medium">Result</th>
                  </tr>
                </thead>
                <tbody className="tabular divide-y divide-[var(--border)]">
                  {recon.map((r) => (
                    <tr key={r.identifier} className={r.ok ? undefined : "bg-bad-soft/40"}>
                      <td className="max-w-[260px] truncate px-3 py-2 text-ink">{r.name}</td>
                      <td className="px-3 py-2 text-right">{num(r.ledger_units, 3)}</td>
                      <td className="px-3 py-2 text-right">{num(r.statement_units, 3)}</td>
                      <td className="px-3 py-2 text-right">
                        {r.ok ? <span className="inline-flex items-center gap-1 text-good"><CheckCircle2 size={14} />Matches</span> : <span className="font-medium text-bad">{num(r.variance, 3)}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {bad.length > 0 && (
              <div className="mt-3 rounded-xl border border-line p-3.5">
                <Checkbox checked={ack} onChange={setAck}>I have checked these {bad.length} difference{bad.length === 1 ? "" : "s"} and accept the analysis with them.</Checkbox>
              </div>
            )}
          </div>
        )}

        {(upload.review.warnings ?? []).length > 0 && <ParserNotes notes={upload.review.warnings!} />}

        {error && <Notice level="error">{error}</Notice>}
        <div className="flex flex-wrap items-center justify-end gap-3 border-t border-line pt-4">
          {mapped < unmatched.length && <span className="text-xs text-muted">{unmatched.length - mapped} scheme(s) will stay excluded</span>}
          <Button icon={Check} loading={busy} disabled={bad.length > 0 && !ack} onClick={save}>Confirm and build report</Button>
        </div>
      </div>
    </section>
  );
}

function ParserNotes({ notes }: { notes: string[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-line">
      <button className="flex w-full items-center justify-between px-4 py-3 text-left text-[13px]" onClick={() => setOpen((o) => !o)}>
        <span className="flex items-center gap-2 font-medium text-ink"><AlertTriangle size={15} className="text-warn" />{notes.length} note{notes.length === 1 ? "" : "s"} from the parser</span>
        <ChevronRight size={16} className={cx("text-muted transition", open && "rotate-90")} />
      </button>
      {open && (
        <ul className="space-y-1.5 border-t border-line px-4 py-3 text-xs text-ink-2">
          {notes.map((n, i) => <li key={i}>• {n}</li>)}
        </ul>
      )}
    </div>
  );
}

function InstrumentPicker({ value, suggestion, onChange, onClear }: {
  value?: { id: string; name: string };
  suggestion: { instrument_id: string; name: string; score: number } | null;
  onChange: (inst: { id: string; name: string }) => void;
  onClear: () => void;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Instrument[]>([]);
  const [searching, setSearching] = useState(!value);
  useEffect(() => {
    if (q.length < 2) return setResults([]);
    const t = setTimeout(() => api.searchInstruments(q).then(setResults).catch(() => setResults([])), 250);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div className="mt-3 space-y-2">
      {value && !searching ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-good-soft/60 px-3 py-2 text-[13px]">
          <span className="min-w-0">
            <span className="text-muted">Maps to </span>
            <strong className="text-ink">{value.name}</strong>
            {suggestion && suggestion.instrument_id === value.id && (
              <span className="ml-2 rounded-full bg-surface px-1.5 py-0.5 text-[11px] font-medium text-good ring-1 ring-good/20">{Math.round(suggestion.score * 100)}% name match</span>
            )}
          </span>
          <span className="flex gap-1">
            <button className="rounded px-2 py-1 text-xs font-medium text-ink-2 hover:bg-surface" onClick={() => setSearching(true)}>Change</button>
            <button className="rounded px-2 py-1 text-xs font-medium text-ink-2 hover:bg-surface" onClick={() => { onClear(); setSearching(true); }}>Skip</button>
          </span>
        </div>
      ) : (
        <>
          {suggestion && (
            <button className="flex w-full items-center justify-between rounded-lg border border-dashed border-accent/40 px-3 py-2 text-left text-[13px] hover:bg-accent-soft/50"
              onClick={() => { onChange({ id: suggestion.instrument_id, name: suggestion.name }); setSearching(false); }}>
              <span>Suggested: <strong className="text-ink">{suggestion.name}</strong></span>
              <span className="text-xs font-medium text-accent">Use · {Math.round(suggestion.score * 100)}%</span>
            </button>
          )}
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
            <input className={cx(inputCls, "h-9 pl-9")} placeholder="Search by name, ISIN or symbol" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          {results.length > 0 && (
            <ul className="scroll-thin max-h-52 overflow-y-auto rounded-lg border border-line bg-surface shadow-pop">
              {results.map((r) => (
                <li key={r.id}>
                  <button type="button" className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-[13px] hover:bg-surface-2"
                    onClick={() => { onChange({ id: r.id, name: r.name }); setQ(""); setSearching(false); }}>
                    <span className="truncate text-ink">{r.name}</span>
                    <span className="shrink-0 font-mono text-[11px] text-muted">{r.isin ?? r.symbol}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {value && <button className="text-xs text-muted hover:text-ink" onClick={() => setSearching(false)}>Cancel</button>}
        </>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- History */

function UploadHistory({ uploads }: { uploads: Upload[] }) {
  return (
    <Card title="Import history" icon={History}>
      {uploads.length === 0 ? (
        <p className="text-[13px] text-muted">No statements uploaded yet.</p>
      ) : (
        <ol className="relative space-y-5 border-l border-line pl-5">
          {uploads.map((u) => (
            <li key={u.id} className="relative">
              <span className={cx("absolute -left-[26.5px] top-1 h-3 w-3 rounded-full ring-4 ring-surface",
                u.status === "completed" ? "bg-good" : u.status === "failed" ? "bg-bad" : u.status === "needs_review" ? "bg-[var(--series-3)]" : "bg-accent")} />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="max-w-[180px] truncate text-[13px] font-medium text-ink" title={u.filename}>{u.filename}</span>
                <StatusBadge status={u.status} />
              </div>
              <div className="mt-0.5 text-xs text-muted">{titleCase(u.file_type)} · {relativeTime(u.created_at)}</div>
              {u.error && <p className="mt-1.5 rounded-lg bg-bad-soft px-2.5 py-1.5 text-xs text-bad">{u.error}</p>}
              {u.review.inserted != null && (
                <p className="mt-1 text-xs text-ink-2">
                  {u.review.inserted} added{u.review.duplicates ? ` · ${u.review.duplicates} duplicates skipped` : ""}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

function PrivacyCard() {
  return (
    <div className="rounded-2xl border border-line bg-surface-2/50 p-5 text-[13px]">
      <div className="flex items-center gap-2 font-semibold text-ink"><ShieldCheck size={16} className="text-good" />How client data is handled</div>
      <ul className="mt-3 space-y-2 text-ink-2">
        {[
          "Statement files are deleted right after parsing.",
          "CAS passwords live in memory for at most 10 minutes.",
          "Only you can see this client. Every access is checked.",
          "Uploading the same statement twice never double counts.",
        ].map((t) => (
          <li key={t} className="flex gap-2"><Check size={14} className="mt-0.5 shrink-0 text-good" />{t}</li>
        ))}
      </ul>
    </div>
  );
}

/* ----------------------------------------------------------------- Ledger */

const TYPE_TONE: Record<string, string> = {
  buy: "bg-good-soft text-good",
  switch_in: "bg-good-soft text-good",
  sell: "bg-bad-soft text-bad",
  switch_out: "bg-bad-soft text-bad",
  dividend_payout: "bg-[color-mix(in_srgb,var(--series-4)_12%,transparent)] text-[var(--series-4)]",
  dividend_reinvest: "bg-[color-mix(in_srgb,var(--series-4)_12%,transparent)] text-[var(--series-4)]",
};
const PAGE = 25;

function Ledger({ portfolioId }: { portfolioId: string }) {
  const [rows, setRows] = useState<Transaction[] | null>(null);
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("all");
  const [page, setPage] = useState(0);
  useEffect(() => {
    api.transactions(portfolioId).then(setRows).catch(() => setRows([]));
  }, [portfolioId]);

  const filtered = useMemo(() => {
    const ql = q.toLowerCase();
    return (rows ?? []).filter((t) => {
      const k = kind === "all" || (kind === "buy" ? ["buy", "switch_in"].includes(t.type) : kind === "sell" ? ["sell", "switch_out"].includes(t.type) : t.type.startsWith("dividend"));
      return k && (!ql || `${t.raw_name ?? ""} ${t.raw_identifier}`.toLowerCase().includes(ql));
    });
  }, [rows, q, kind]);
  useEffect(() => {
    setPage(0);
  }, [q, kind]);

  if (!rows) return <Skeleton className="h-96 rounded-2xl" />;
  if (!rows.length) return <EmptyState icon={ReceiptText} title="No transactions yet">Upload a statement and every purchase, sale and dividend appears here.</EmptyState>;
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const view = filtered.slice(page * PAGE, page * PAGE + PAGE);
  const unmatched = rows.filter((r) => !r.instrument_id).length;

  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4">
        <div className="relative w-full sm:w-72">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
          <input className={cx(inputCls, "h-9 pl-9")} placeholder="Search by scheme or stock" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Segmented options={[{ id: "all", label: "All" }, { id: "buy", label: "Purchases" }, { id: "sell", label: "Sales" }, { id: "div", label: "Dividends" }]} value={kind} onChange={setKind} />
      </div>
      {unmatched > 0 && <div className="border-b border-line px-4 py-2.5"><Notice level="warning">{unmatched} transactions are not mapped to an instrument and are excluded from the report.</Notice></div>}
      <div className="scroll-thin overflow-x-auto">
        <table className="w-full min-w-[760px] text-[13px]">
          <thead className="bg-surface-2 text-left text-[12.5px] text-muted">
            <tr>
              <th className="px-4 py-3 font-medium">Date</th>
              <th className="px-4 py-3 font-medium">Instrument</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 text-right font-medium">Units</th>
              <th className="px-4 py-3 text-right font-medium">Price</th>
              <th className="px-4 py-3 text-right font-medium">Amount</th>
            </tr>
          </thead>
          <tbody className="tabular divide-y divide-[var(--border)]">
            {view.map((t) => (
              <tr key={t.id} className="hover:bg-surface-2/50">
                <td className="whitespace-nowrap px-4 py-2.5 text-ink-2">{date(t.date)}</td>
                <td className="max-w-[320px] px-4 py-2.5">
                  <div className="truncate text-ink">{t.raw_name ?? t.raw_identifier}</div>
                  {!t.instrument_id && <span className="text-[11px] font-medium text-warn">Not mapped</span>}
                </td>
                <td className="px-4 py-2.5">
                  <span className={cx("rounded-md px-1.5 py-0.5 text-[11px] font-semibold", TYPE_TONE[t.type] ?? "bg-surface-2 text-ink-2")}>{titleCase(t.type)}</span>
                </td>
                <td className="px-4 py-2.5 text-right">{num(t.units, 3)}</td>
                <td className="px-4 py-2.5 text-right text-ink-2">{t.price ? num(t.price, 2) : "–"}</td>
                <td className="px-4 py-2.5 text-right font-medium text-ink">{inr(Number(t.amount))}</td>
              </tr>
            ))}
            {view.length === 0 && <tr><td colSpan={6} className="px-4 py-10 text-center text-muted">No transactions match.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-line px-4 py-3 text-xs text-muted">
        <span>{filtered.length} transactions · the source of truth for every number in the report</span>
        <div className="flex items-center gap-1">
          <button className="rounded-lg p-1.5 hover:bg-surface-2 disabled:opacity-30" disabled={page === 0} onClick={() => setPage((p) => p - 1)} aria-label="Previous page"><ChevronLeft size={16} /></button>
          <span className="tabular px-2">{page + 1} / {pages}</span>
          <button className="rounded-lg p-1.5 hover:bg-surface-2 disabled:opacity-30" disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)} aria-label="Next page"><ChevronRight size={16} /></button>
        </div>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- Delete */

function DeleteModal({ open, name, onClose, onConfirm }: { open: boolean; name: string; onClose: () => void; onConfirm: () => Promise<void> }) {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setTyped("");
  }, [open]);
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Delete client data"
      description={`This permanently deletes ${name}'s portfolio, transactions and reports. It cannot be undone.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="danger" icon={Trash2} loading={busy} disabled={typed !== "DELETE"}
            onClick={async () => { setBusy(true); try { await onConfirm(); } finally { setBusy(false); } }}>
            Delete permanently
          </Button>
        </>
      }
    >
      <Field label="Type DELETE to confirm">
        <input className={inputCls} value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
      </Field>
    </Modal>
  );
}
