import type { ClientPlan, GoalInput, Instrument, RiskQuestion, TickerItem, Portfolio, PortfolioSummary, Report, Transaction, Upload } from "./types";

const BASE = "/api/v1";
const TOKEN_KEY = "foliolens.token";

export const auth = {
  get token(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string | null) {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* storage unavailable: the session simply won't persist */
    }
  },
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = auth.token;
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(BASE + path, { ...init, headers });
  if (res.status === 401 && token) {
    auth.set(null);
    window.dispatchEvent(new Event("foliolens:logout"));
  }
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = typeof body.detail === "string" ? body.detail : body.detail?.[0]?.msg ?? message;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  register: (email: string, password: string) =>
    request("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request<{ email: string }>("/auth/me"),
  demoReport: () => request<Report>("/demo/report"),
  ticker: () => request<TickerItem[]>("/market/ticker"),
  health: () => fetch("/api/v1/health").then((r) => r.ok).catch(() => false),
  portfolios: () => request<PortfolioSummary[]>("/portfolios"),
  createPortfolio: (name: string, client_name: string) =>
    request<Portfolio>("/portfolios", { method: "POST", body: JSON.stringify({ name, client_name }) }),
  portfolio: (id: string) => request<Portfolio>(`/portfolios/${id}`),
  deletePortfolio: (id: string) => request<void>(`/portfolios/${id}`, { method: "DELETE" }),
  report: (id: string) => request<Report>(`/portfolios/${id}/report`),
  refreshReport: (id: string) => request(`/portfolios/${id}/report/refresh`, { method: "POST" }),
  uploads: (id: string) => request<Upload[]>(`/portfolios/${id}/uploads`),
  upload: (uploadId: string) => request<Upload>(`/uploads/${uploadId}`),
  consentText: () => request<{ version: string; text: string }>("/consent-text"),
  createUpload: (id: string, form: FormData) =>
    request<Upload>(`/portfolios/${id}/uploads`, { method: "POST", body: form }),
  review: (uploadId: string, body: { mappings: { raw_identifier: string; instrument_id: string }[]; acknowledge_reconciliation?: boolean }) =>
    request<Upload>(`/uploads/${uploadId}/review`, { method: "POST", body: JSON.stringify(body) }),
  transactions: (id: string) => request<Transaction[]>(`/portfolios/${id}/transactions`),
  riskQuestions: () => request<{ questions: RiskQuestion[]; bands: { name: string; from_score: number; equity_min: number; equity_max: number }[] }>("/risk-questions"),
  plan: (id: string) => request<ClientPlan>(`/portfolios/${id}/plan`),
  savePlan: (id: string, body: { risk_answers: Record<string, number>; goals: GoalInput[] }) =>
    request<ClientPlan>(`/portfolios/${id}/plan`, { method: "PUT", body: JSON.stringify(body) }),
  searchInstruments: (q: string) => request<Instrument[]>(`/instruments?q=${encodeURIComponent(q)}`),
};
