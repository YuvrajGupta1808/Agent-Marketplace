export type AgentRole = "buyer" | "seller";

export interface UserRecord {
  id: string;
  external_id?: string | null;
  display_name: string;
  created_at: string;
}

export interface WalletRecord {
  id: string;
  owner_type: string;
  owner_id: string;
  circle_wallet_id: string;
  wallet_set_id: string;
  blockchain: string;
  account_type: string;
  address: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface AgentRecord {
  id: string;
  user_id: string;
  role: AgentRole;
  name: string;
  endpoint_url?: string | null;
  created_at: string;
  wallet: WalletRecord;
  metadata: Record<string, unknown>;
}

export interface PaymentRecord {
  task_id: string;
  circle_transaction_id: string;
  amount_usdc: string;
  tx_hash?: string | null;
  state: string;
  created_at?: string | null;
  metadata?: Record<string, unknown>;
}

export interface GraphNodeOutput {
  node_name: string;
  title: string;
  phase?: string;
  status?: string;
  duration_ms?: number | null;
  reasoning?: string;
  input_state: Record<string, unknown>;
  output: Record<string, unknown>;
  state_after: Record<string, unknown>;
}

export interface BuyerWorkflowRecord {
  task_id: string;
  execution_plan: string[];
  node_outputs: GraphNodeOutput[];
}

export interface ResearchResult {
  task_id: string;
  title: string;
  summary: string;
  bullets: string[];
  citations: Array<{ title: string; url: string; snippet: string }>;
  tx_hash?: string | null;
  circle_transaction_id?: string | null;
  amount_usdc?: string | null;
  seller_name: string;
  seller_endpoint?: string | null;
  is_ambiguous: boolean;
  metadata: Record<string, unknown>;
}

export interface RunResponse {
  thread_id: string;
  final_answer?: string | null;
  running_answer?: string | null;
  query_intent?: string;
  is_conversational?: boolean;
  task_specs: Array<{ task_id: string; query: string; objective: string }>;
  results: ResearchResult[];
  buyer_workflows: BuyerWorkflowRecord[];
  transaction_hashes: string[];
  payments: PaymentRecord[];
  failed_tasks: string[];
  pending_question?: string | null;
}

export interface HealthResponse {
  status: string;
  circle_enabled: boolean;
  research_mode: string;
  seller_price_usdc: number;
}

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let message = response.statusText;
    try {
      const payload = await response.json();
      message = payload.detail ?? payload.message ?? JSON.stringify(payload);
    } catch {
      message = await response.text();
    }
    throw new Error(message || `HTTP ${response.status}`);
  }

  return (await response.json()) as T;
}

export function listUsers() {
  return apiRequest<UserRecord[]>("/users");
}

export function getUser(userId: string) {
  return apiRequest<UserRecord>(`/users/${userId}`);
}

export function createUser(displayName: string, externalId?: string) {
  return apiRequest<{ user: UserRecord }>("/users", {
    method: "POST",
    body: JSON.stringify({
      display_name: displayName,
      external_id: externalId || undefined,
    }),
  });
}

export function listAgents(params?: { userId?: string; role?: AgentRole }) {
  const search = new URLSearchParams();
  if (params?.userId) search.set("user_id", params.userId);
  if (params?.role) search.set("role", params.role);
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return apiRequest<AgentRecord[]>(`/agents${suffix}`);
}

export function listUserAgents(userId: string, role?: AgentRole) {
  const search = new URLSearchParams();
  if (role) search.set("role", role);
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return apiRequest<AgentRecord[]>(`/users/${userId}/agents${suffix}`);
}

export function createAgent(payload: {
  userId: string;
  role: AgentRole;
  name: string;
  endpointUrl?: string;
  metadata?: Record<string, unknown>;
}) {
  return apiRequest<{ agent: AgentRecord }>("/agents", {
    method: "POST",
    body: JSON.stringify({
      user_id: payload.userId,
      role: payload.role,
      name: payload.name,
      endpoint_url: payload.endpointUrl,
      metadata: payload.metadata ?? {},
    }),
  });
}

export function runMarketplace(payload: {
  userGoal: string;
  buyerAgentId: string;
  sellerAgentId: string;
  threadId?: string;
}) {
  return apiRequest<RunResponse>("/run", {
    method: "POST",
    body: JSON.stringify({
      user_goal: payload.userGoal,
      buyer_agent_id: payload.buyerAgentId,
      seller_agent_id: payload.sellerAgentId,
      thread_id: payload.threadId ?? `ui-${crypto.randomUUID()}`,
    }),
  });
}

export interface StreamEvent {
  type: "node_update" | "custom_event" | "stream_complete" | "error" | "final_answer";
  node?: string;
  data?: Record<string, unknown>;
  error?: string;
  answer?: string;
}

export async function* streamMarketplace(payload: {
  userGoal: string;
  buyerAgentId: string;
  sellerAgentId: string;
  threadId?: string;
}): AsyncGenerator<StreamEvent, void, unknown> {
  const response = await fetch(`${API_BASE_URL}/run/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user_goal: payload.userGoal,
      buyer_agent_id: payload.buyerAgentId,
      seller_agent_id: payload.sellerAgentId,
      thread_id: payload.threadId ?? `ui-${crypto.randomUUID()}`,
    }),
  });

  if (!response.ok) {
    let message = response.statusText;
    try {
      const payload = await response.json();
      message = payload.detail ?? payload.message ?? JSON.stringify(payload);
    } catch {
      message = await response.text();
    }
    throw new Error(message || `HTTP ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const eventData = JSON.parse(line.slice(6));
            yield eventData as StreamEvent;
          } catch {
            // Skip invalid JSON
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export function getHealth() {
  return apiRequest<HealthResponse>("/health");
}

export interface Transaction {
  id: string;
  thread_id: string;
  task_id: string;
  buyer_agent_id: string;
  seller_agent_id: string;
  circle_transaction_id: string;
  amount_usdc: string;
  tx_hash: string | null;
  state: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export function getTransactions(params?: { threadId?: string; buyerAgentId?: string }) {
  const search = new URLSearchParams();
  if (params?.threadId) search.set("thread_id", params.threadId);
  if (params?.buyerAgentId) search.set("buyer_agent_id", params.buyerAgentId);
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return apiRequest<{ total: number; transactions: Transaction[] }>(`/transactions${suffix}`);
}

export { API_BASE_URL };
