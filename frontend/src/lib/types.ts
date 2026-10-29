export interface Portfolio {
  id: string;
  name: string;
  client_name: string;
  created_at: string;
}

export interface PortfolioSummary extends Portfolio {
  current_value: number | null;
  xirr: number | null;
  findings: number | null;
  valuation_date: string | null;
  last_upload_status: string | null;
}

export interface UnmatchedItem {
  raw_identifier: string;
  raw_name: string | null;
  count: number;
  suggestion: { instrument_id: string; name: string; score: number } | null;
}

export interface ReconciliationRow {
  identifier: string;
  name: string;
  ledger_units: number;
  statement_units: number;
  variance: number;
  ok: boolean;
}

export interface Upload {
  id: string;
  portfolio_id: string;
  filename: string;
  file_type: string;
  status: "queued" | "processing" | "needs_review" | "completed" | "failed";
  error: string | null;
  review: {
    unmatched?: UnmatchedItem[];
    reconciliation?: ReconciliationRow[];
    reconciliation_acknowledged?: boolean;
    warnings?: string[];
    inserted?: number;
    duplicates?: number;
  };
  created_at: string;
  parsed_at: string | null;
}

export interface Transaction {
  id: number;
  instrument_id: string | null;
  raw_identifier: string;
  raw_name: string | null;
  date: string;
  type: string;
  units: string;
  price: string | null;
  amount: string;
}

export interface Instrument {
  id: string;
  type: string;
  isin: string | null;
  symbol: string | null;
  name: string;
  asset_class: string;
  category: string | null;
}

export interface Holding {
  instrument_id: string;
  name: string;
  type: string;
  asset_class: string;
  category: string | null;
  units: number;
  price: number;
  price_date: string;
  value: number;
  cost: number;
  gain: number;
  xirr: number | null;
  weight: number;
}

export interface Finding {
  id: string;
  type: string;
  severity: "high" | "medium" | "low";
  title: string;
  measured_value: number;
  threshold: number | null;
  unit: "percent" | "count";
  instruments: string[];
  data_date: string | null;
  calc_version: string;
  evidence: Record<string, unknown>;
  limitations: string[];
  discussion_prompts: string[];
  explanation: string | null;
  explanation_source: "llm" | "template" | null;
  /** Added in engine 1.1: options for the advisor to weigh. */
  options?: ActionOption[];
}

export interface TaxEstimate {
  units: number;
  proceeds: number;
  cost: number;
  gain: number;
  short_term_gain: number;
  long_term_gain: number;
  equity_rules: boolean;
  tax_if_exemption_unused: number | null;
  tax_if_exemption_used: number | null;
  rules: string;
  notes: string[];
}

export interface ActionOption {
  id: string;
  kind: "reduce" | "redirect" | "keep" | "add";
  title: string;
  summary: string;
  impact: { label: string; value: number | string | null; unit: "inr" | "percent" | "percent_points" | "count" | "years" | "text" }[];
  tax: TaxEstimate | null;
  tradeoffs: string[];
}

export interface Contribution {
  instrument_id: string;
  name: string;
  asset_class: string;
  type: string;
  value: number;
  held: boolean;
  money_in: number;
  profit: number;
  share_of_profit: number | null;
  xirr: number | null;
  index_xirr: number | null;
  vs_index: number | null;
}

export interface Summary {
  points: { kind: "headline" | "good" | "bad" | "warn"; text: string }[];
  text: string;
  source: "llm" | "template";
  facts: Record<string, unknown>;
}

export interface Report {
  status: "ok" | "empty" | "error";
  message?: string;
  created_at?: string;
  portfolio?: { name: string; client_name: string };
  meta: {
    calc_version: string;
    valuation_date: string;
    generated_at: string;
    benchmark: string | null;
    data_sources: string[];
    synthetic?: boolean;
  };
  overview: {
    current_value: number;
    cost: number;
    unrealized_gain: number;
    net_invested: number;
    xirr: number | null;
    holdings_count: number;
    funds_count: number;
    stocks_count: number;
    liquid_weight: number;
    first_investment: string | null;
  };
  holdings: Holding[];
  allocation: {
    asset_class: { name: string; weight: number; value: number }[];
    sector: { reliable: boolean; items: { name: string; value: number; weight: number; weight_of_equity: number }[] };
    market_cap: { name: string; value: number; weight: number }[];
    top_companies: {
      instrument_id: string;
      name: string;
      sector: string | null;
      value: number;
      weight: number;
      direct_value: number;
      via_funds_value: number;
    }[];
    lookthrough: {
      coverage: number;
      reliable: boolean;
      excluded: { name: string; reason: string }[];
      data_dates: Record<string, string>;
    };
  };
  overlap: { fund_a: string; fund_b: string; overlap: number; shared_stocks: number; as_of: string }[];
  performance: {
    series: { date: string; value: number; invested: number; portfolio_index: number; benchmark_index: number | null }[];
    twr_annualized: number | null;
    benchmark_annualized: number | null;
    benchmark_name: string | null;
    benchmark_compatible: boolean;
    period_start: string | null;
    period_end: string | null;
  };
  risk: {
    available: boolean;
    reason?: string;
    observations: number;
    period_start?: string;
    period_end?: string;
    volatility?: number;
    max_drawdown?: number;
    drawdown_peak?: string;
    drawdown_trough?: string;
    beta?: number | null;
    var_95_1d?: number;
    var_95_1d_parametric?: number;
    hhi: number;
    effective_holdings: number | null;
    method: Record<string, string>;
  };
  findings: Finding[];
  /** Added in engine 1.1. Older saved reports do not have these until recalculated. */
  contribution?: { total_profit: number; items: Contribution[]; helped: string[]; hurt: string[]; method: string };
  summary?: Summary;
  /** Added in engine 1.2: the client's risk profile and goals. */
  planning?: Planning;
  data_quality: { level: "info" | "warning" | "error"; message: string }[];
}

export interface TickerItem {
  symbol: string;
  name: string;
  type: string;
  date: string;
  close: number;
  prev_close: number;
  change: number;
  source: string;
}

export interface RiskProfile {
  score: number;
  category: string;
  equity_min: number;
  equity_max: number;
  answered: number;
  questions: number;
}

export interface GoalProjection {
  id: string;
  name: string;
  target_today: number;
  target_date: string;
  years: number;
  target_future: number;
  share_of_portfolio: number;
  set_aside: number;
  monthly_sip: number;
  expected_return: number;
  inflation: number;
  projected: number;
  funded_ratio: number | null;
  gap: number;
  required_sip: number | null;
  status: "on_track" | "at_risk" | "off_track" | "due";
}

export interface Planning {
  available: boolean;
  profile: RiskProfile | null;
  equity_share: number;
  in_range: boolean | null;
  goals: GoalProjection[];
  goals_on_track: number;
  assumptions: { expected_return: Record<string, number>; inflation: number; portfolio_expected_return: number; note: string };
}

export interface RiskQuestion {
  id: string;
  text: string;
  options: string[];
}

export interface GoalInput {
  id?: string | null;
  name: string;
  target_amount: number;
  target_date: string;
  monthly_sip: number;
  share_of_portfolio: number;
}

export interface ClientPlan {
  risk_answers: Record<string, number>;
  goals: GoalInput[];
  profile: RiskProfile | null;
  updated_at: string | null;
}
