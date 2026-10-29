import { ArrowRight, Check, Eye, EyeOff, Lightbulb, Lock, Mail } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Logo } from "../components/Layout";
import { Button, Field, Notice, cx, inputCls, useDocumentTitle } from "../components/ui";
import { api, auth } from "../lib/api";
import { useDemoReport } from "./Landing";

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const isLogin = mode === "login";
  useDocumentTitle(isLogin ? "Sign in" : "Create account");
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (!isLogin) await api.register(email, password);
      const { access_token } = await api.login(email, password);
      auth.set(access_token);
      navigate("/app");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const demo = useDemoReport();
  const strength = password.length === 0 ? 0 : password.length < 10 ? 1 : password.length < 14 ? 2 : 3;

  return (
    <div className="min-h-screen bg-page">
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <Logo />
        <div className="mx-auto flex w-full max-w-[380px] flex-1 flex-col justify-center py-12">
          <h1 className="text-[30px] font-bold tracking-tight text-ink">{isLogin ? "Welcome back" : "Create your workspace"}</h1>
          <p className="mt-2 text-sm text-muted">
            {isLogin ? "Sign in to review your clients' portfolios." : "Free for advisors. Your first client review takes about a minute."}
          </p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <Field label="Work email">
              <div className="relative">
                <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
                <input className={cx(inputCls, "h-11 pl-9")} type="email" required autoComplete="email" placeholder="you@firm.in" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
            </Field>
            <Field label="Password">
              <div className="relative">
                <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
                <input className={cx(inputCls, "h-11 pl-9 pr-10")} type={show ? "text" : "password"} required minLength={isLogin ? 1 : 10}
                  autoComplete={isLogin ? "current-password" : "new-password"} value={password} onChange={(e) => setPassword(e.target.value)} />
                <button type="button" onClick={() => setShow((s) => !s)} className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-faint hover:text-ink" aria-label={show ? "Hide password" : "Show password"}>
                  {show ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {!isLogin && (
                <div className="mt-2">
                  <div className="flex gap-1">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className={cx("h-1 flex-1 rounded-full", strength >= i ? (strength === 1 ? "bg-bad" : strength === 2 ? "bg-[var(--series-3)]" : "bg-good") : "bg-surface-3")} />
                    ))}
                  </div>
                  <div className="mt-1.5 text-xs text-muted">{strength < 2 ? "At least 10 characters." : strength === 2 ? "Good. Longer is stronger." : "Strong password."}</div>
                </div>
              )}
            </Field>
            {error && <Notice level="error">{error}</Notice>}
            <Button type="submit" size="lg" loading={busy} className="w-full">
              {isLogin ? "Sign in" : "Create account"} {!busy && <ArrowRight size={16} />}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            {isLogin ? (
              <>New to FolioLens? <Link className="font-medium text-accent hover:underline" to="/register">Create an account</Link></>
            ) : (
              <>Already have an account? <Link className="font-medium text-accent hover:underline" to="/login">Sign in</Link></>
            )}
          </p>
          <div className="mt-8 flex items-center gap-3 text-xs text-faint">
            <div className="h-px flex-1 bg-line" />or<div className="h-px flex-1 bg-line" />
          </div>
          <Link to="/demo" className="mt-6 flex items-center justify-center gap-2 rounded-lg border border-line-strong bg-surface py-3 text-sm font-medium text-ink hover:border-accent/50">
            See a sample review, no sign-in <ArrowRight size={15} />
          </Link>
        </div>
        <p className="text-xs text-faint">For information and education only. Not investment advice.</p>
      </div>

      <div className="relative hidden overflow-hidden border-l border-line bg-surface lg:block">
        <div className="soft-grid absolute inset-0" />
        <div className="relative flex h-full flex-col justify-center px-14 py-16">
          <div className="text-[13px] font-semibold text-accent">What your client review looks like</div>
          <h2 className="mt-2 max-w-md text-[28px] font-bold leading-tight tracking-tight text-ink">
            The numbers, the why, and what to do next.
          </h2>
          <ul className="mt-8 max-w-[520px] space-y-3">
            {(demo?.summary?.points ?? []).slice(0, 4).map((p, i) => (
              <li key={i} className="flex gap-3 rounded-xl border border-line bg-surface p-3.5 shadow-card">
                <Lightbulb size={16} className="mt-0.5 shrink-0 text-accent" />
                <span className="text-[13.5px] leading-relaxed text-ink-2">{p.text}</span>
              </li>
            ))}
          </ul>
          <ul className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-ink-2">
            {["XIRR matches Excel", "Looks inside every fund", "AI numbers checked"].map((t) => (
              <li key={t} className="flex items-center gap-1.5"><Check size={14} className="text-good" />{t}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
    </div>
  );
}
