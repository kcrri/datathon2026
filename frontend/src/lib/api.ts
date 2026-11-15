import { getLang, translate } from "@/i18n";
import { PERSONAS, type PersonaId, type Scenario } from "./personas";

export type Proposal = {
  id: string;
  type: "create_account";
  account_type: string;
  account_type_label?: string;
  horizon: string;
  horizon_label: string;
  risk: string;
  risk_label: string;
  persona: string;
  reason: string;
};

export type ChatMessage = {
  role: "user" | "assistant";
  text?: string;
  data?: ChatResponse;
  resolved?: boolean;
};

export type ChatResponse = {
  answer: string;
  trace: Array<{ agent: string; action: string; runtime?: string }>;
  metrics: Record<string, string>;
  sources: string[];
  warnings: string[];
  proposal: Proposal | null;
  suggestions: string[];
  trade_check?: TradeCheck | null;
  position?: TradePosition | null;
  headlines?: Headline[] | null;
  persona_fit?: PersonaFit | null;
};

export type RuntimeInfo = {
  agents: string;
  agent_runtime: string | null;
  engine: string;
  function: string | null;
  region: string | null;
  data: string;
};

export type McpInfo = {
  url: string;
  base_url: string;
  token: string;
  local_only: boolean;
  stable: boolean;
  tools: Array<{ name: string; title: string; description: string; input_schema: unknown }>;
  example: { risk: string; horizon: string; goals: string[] };
  server: { name: string; title: string; version: string };
};

/** What Claude submitted through the MCP connector. */
export type ClaudeProfile = {
  source: "mcp";
  client?: string;
  risk: "low" | "mid" | "high";
  horizon: string;
  goals: string[];
  name?: string;
  submitted_at: string;
};

export type InvestorRecord = {
  persona_id: PersonaId;
  persona_name: string;
  account_type: string | null;
  risk_band: "low" | "mid" | "high";
  updated_at: string;
  profile?: ClaudeProfile;
};

export type PersonaFit = {
  persona: { id: string; name: string; risk: string; horizon_years: string; horizon_text?: string | null; goal: string; source?: string | null };
  stance: "fits" | "wait" | "careful";
  headline: string;
  why: string[];
};

export type Headline = { date: string; headline: string; sentiment: string | number | null; category: string };

export type TradePosition = {
  ticker: string;
  action: TradeAction;
  holds: boolean;
  shares_held: number;
  price: number;
  sample_qty: number;
  sample_amount_cad: number;
  portfolio_pct: number;
  cash_after_cad: number;
  affordable: boolean;
};

export type Account = {
  id: string;
  name: string;
  type: string;
  horizon: string;
  risk: string;
  risk_label: string;
  persona: string;
  horizon_agent: string;
  strategies: string[];
  balance: number;
  /** Current value from the Lambda (holdings at today's prices plus cash). Show this, not `balance`. */
  value_cad?: number;
  invested_cad?: number;
  cash_cad?: number;
  value_source?: "market" | "stored balance";
  persona_id?: PersonaId;
};

export type IntegrationStatus = {
  configured: boolean;
  label: string;
  detail: string;
};

export type ApiMeta = {
  profiles: Record<string, unknown>;
  faq: string[];
  integrations: {
    region: string | null;
    lambda: IntegrationStatus;
    bedrock: IntegrationStatus;
    dataset: IntegrationStatus;
  };
};

export type MetricEvidence = {
  evidence_id: string;
  label: string;
  current: number;
  proposed: number;
  delta: number;
  unit: "percent" | "ratio";
  source: string;
  formula_version: string;
};

export type PerformancePoint = {
  date: string;
  current: number;
  proposed: number;
};

export type TraceStep = {
  step_id: string;
  parent_id: string | null;
  agent: string;
  action: string;
  status: "completed" | "blocked" | "failed";
  delegated_to: string[];
  evidence_ids: string[];
  details: Record<string, unknown>;
};

export type GovernanceFinding = {
  rule_id: string;
  severity: "info" | "warning" | "block";
  message: string;
  evidence_ids: string[];
};

export type AgentFinding = {
  agent: string;
  role: string;
  summary: string;
  requested_operations: string[];
  evidence_ids: string[];
};

export type AnalysisResponse = {
  analysis_id: string;
  question: string;
  persona_id: PersonaId;
  account_type: "TFSA" | "RRSP";
  answer: string;
  conclusion: "risk_reduced" | "risk_increased" | "mixed";
  current_allocations: Record<string, number>;
  proposed_allocations: Record<string, number>;
  metrics: MetricEvidence[];
  performance_series: PerformancePoint[];
  agent_findings: AgentFinding[];
  governance: GovernanceFinding[];
  trace: TraceStep[];
  assumptions: string[];
  limitations: string[];
  data_sources: string[];
  model_id: string;
  disclaimer: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const USER_ID = "demo";

export type TradeAction = "buy" | "sell";

export type TradeVerdict =
  | "no_signal"
  | "panic_risk"
  | "evidence_supported"
  | "mixed"
  | "chasing_risk"
  | "falling_knife"
  | "dip_with_context";

export type Holding = {
  ticker: string;
  weight: number;
  shares: number;
  price: number;
  value_cad: number;
  move_pct: number;
};

export type Portfolio = {
  persona_id: PersonaId;
  account_type?: string | null;
  refreshed: boolean;
  invested_cad: number;
  cash_cad: number;
  total_value_cad: number;
  holdings: Holding[];
  note: string;
  computed_by: string;
};

export type MarketStatus = {
  refreshed: boolean;
  new_price_rows: number;
  new_headlines: number;
  computed_by: string;
};

export type Explanation = {
  source: string;
  popup_title: string;
  popup_text: string;
  detail: string;
  evidence_ids: string[];
};

export type TradeCheck = {
  explanation?: Explanation | null;
  driver?: "market" | "company" | "mixed";
  trace?: Array<{ agent: string; action: string; runtime?: string }>;
  persona_fit?: PersonaFit | null;
  action: TradeAction;
  ticker: string;
  verdict: TradeVerdict;
  score: { name: string; value: number; low_label: string; high_label: string } | null;
  sentiment: number | null;
  sentiment_label: "upbeat" | "neutral" | "negative" | null;
  evidence: { evidence_id: string; label: string; value: number | null; unit: string }[];
  limitations: string[];
  computed_by: string;
};

export type AnalysisInput = { question: string; shift: Scenario };

export async function runAnalysis(persona_id: PersonaId, input?: AnalysisInput): Promise<AnalysisResponse> {
  const persona = PERSONAS.find((item) => item.id === persona_id)!;
  const { question, shift } = input ?? {
    question: translate(`persona.${persona_id}.scenario`),
    shift: persona.scenario,
  };
  const response = await fetch(`${API_URL}/api/analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      persona_id,
      question,
      language: getLang(),
      account_type: "TFSA",
      strategy_allocations: persona.allocations,
      shift: { from_strategy: shift.from, to_strategy: shift.to, amount: shift.amount },
    }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail ? `: ${body.detail}` : "";
    console.error("analysis failed", response.status, detail);
    throw new Error(translate("error.analysis", { status: response.status }));
  }
  return response.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail ? `: ${payload.detail}` : "";
    console.error("request failed", response.status, detail);
    throw new Error(translate("error.generic", { status: response.status }));
  }
  return response.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail ? `: ${payload.detail}` : "";
    console.error("request failed", response.status, detail);
    throw new Error(translate("error.generic", { status: response.status }));
  }
  return response.json();
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail ? `: ${payload.detail}` : "";
    console.error("request failed", response.status, detail);
    throw new Error(translate("error.generic", { status: response.status }));
  }
  return response.json();
}

export const api = {
  chat: (message: string, holdingsPersona?: PersonaId, live = false) =>
    post<ChatResponse>("/api/chat", { user_id: USER_ID, message, lang: getLang(), holdings_persona: holdingsPersona, live }),
  approve: (id: string, risk: string | undefined) => post<ChatResponse>(`/api/actions/${id}/approve`, { risk, lang: getLang() }),
  reject: (id: string) => post<ChatResponse>(`/api/actions/${id}/reject?lang=${getLang()}`, {}),
  accounts: (persona?: PersonaId, live = false) =>
    get<Account[]>(
      `/api/accounts?user_id=${encodeURIComponent(USER_ID)}&live=${live}${persona ? `&persona_id=${encodeURIComponent(persona)}` : ""}`,
    ),
  deleteAccount: async (id: string) => {
    const response = await fetch(`${API_URL}/api/accounts/${id}?user_id=${encodeURIComponent(USER_ID)}`, { method: "DELETE" });
    if (!response.ok) throw new Error(translate("error.removeAccount", { status: response.status }));
  },
  /** Save the selected investor and account to S3 (via the agents), so every agent reads the same one. */
  setInvestor: (persona: PersonaId, accountType?: string, knownProfileAt: string | null = null) =>
    put<unknown>("/api/investor", {
      persona_id: persona,
      account_type: accountType ?? null,
      user_id: USER_ID,
      known_profile_at: knownProfileAt, // lets the server refuse to overwrite a newer profile from Claude
    }),
  mcpInfo: () => get<McpInfo>(`/api/mcp/info?user_id=${encodeURIComponent(USER_ID)}`),
  /** The saved investor, or null when none has been chosen yet. */
  getInvestor: async (): Promise<InvestorRecord | null> => {
    const response = await fetch(`${API_URL}/api/investor?user_id=${encodeURIComponent(USER_ID)}`);
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(translate("common.requestFailed"));
    return (await response.json()) as InvestorRecord;
  },
  clearClaudeProfile: async () => {
    await fetch(`${API_URL}/api/investor/profile?user_id=${encodeURIComponent(USER_ID)}`, { method: "DELETE" });
  },
  runtime: () => get<RuntimeInfo>("/api/runtime"),
  market: (live = false) => get<MarketStatus>(`/api/market?live=${live}`),
  refreshMarket: () => post<MarketStatus>("/api/market/refresh", {}),
  resetMarket: () => post<MarketStatus>("/api/market/reset", {}),
  portfolio: (persona: PersonaId, accountType?: string, live = false) =>
    get<Portfolio>(
      `/api/portfolio/${persona}?live=${live}${accountType ? `&account_type=${encodeURIComponent(accountType)}` : ""}`
    ),
  tradeCheck: (ticker: string, action: TradeAction, persona?: PersonaId, live = false, accountType?: string) =>
    get<TradeCheck>(
      `/api/trade-check/${encodeURIComponent(ticker)}?action=${action}&lang=${getLang()}&live=${live}&user_id=${encodeURIComponent(USER_ID)}${persona ? `&persona=${persona}` : ""}${accountType ? `&account_type=${encodeURIComponent(accountType)}` : ""}`
    ),
  features: () => get<{ flags: Record<string, boolean> }>("/api/features"),
  setFeature: (id: string, enabled: boolean) =>
    put<{ flags: Record<string, boolean> }>(`/api/features/${id}`, { enabled }),
  resetFeatures: () => post<{ flags: Record<string, boolean> }>("/api/features/reset", {}),
  meta: () => get<ApiMeta>("/api/meta"),
};
