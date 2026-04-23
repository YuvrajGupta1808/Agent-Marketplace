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

export interface StreamEvent {
  type: string;
  phase?: string;
  task_id?: string;
  node_name?: string;
  data: Record<string, unknown>;
  timestamp_ms: number;
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

export async function runMarketplaceStream(
  payload: {
    userGoal: string;
    buyerAgentId: string;
    sellerAgentId: string;
    threadId?: string;
  },
  onEvent: (event: StreamEvent) => void,
): Promise<RunResponse> {
  const threadId = payload.threadId ?? `ui-${crypto.randomUUID()}`;
  const response = await fetch(`${API_BASE_URL}/run/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_goal: payload.userGoal,
      buyer_agent_id: payload.buyerAgentId,
      seller_agent_id: payload.sellerAgentId,
      thread_id: threadId,
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

  let finalResult: RunResponse | null = null;
  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) {
    throw new Error("Response body not readable");
  }

  try {
    let eventCount = 0;
    let buffer = "";

    const processEventPayload = (rawPayload: string) => {
      const data = rawPayload.trim();
      if (!data) return;

      // SSE keepalive messages can be sent as "[DONE]".
      if (data === "[DONE]") return;

      try {
        const event: StreamEvent = JSON.parse(data);
        eventCount++;
        console.log(`[runMarketplaceStream] Event ${eventCount}: type=${event.type}`);
        onEvent(event);

        if (event.type === "done") {
          console.log("[runMarketplaceStream] Done event received, extracting full_result");
          finalResult = (event.data.full_result as RunResponse | undefined) ?? finalResult;
          if (finalResult && !finalResult.thread_id) {
            finalResult.thread_id = threadId;
          }
          return;
        }

        // Fallback: some servers emit final payloads under alternate event names.
        if (!finalResult && (event.type === "result" || event.type === "final")) {
          const maybeResult = (event.data.full_result ?? event.data) as Partial<RunResponse>;
          if (maybeResult && typeof maybeResult === "object" && "results" in maybeResult) {
            finalResult = {
              thread_id: (maybeResult.thread_id as string) ?? threadId,
              final_answer: (maybeResult.final_answer as string | null | undefined) ?? null,
              running_answer: (maybeResult.running_answer as string | null | undefined) ?? null,
              query_intent: maybeResult.query_intent as string | undefined,
              is_conversational: maybeResult.is_conversational as boolean | undefined,
              task_specs: (maybeResult.task_specs as RunResponse["task_specs"]) ?? [],
              results: (maybeResult.results as RunResponse["results"]) ?? [],
              buyer_workflows: (maybeResult.buyer_workflows as RunResponse["buyer_workflows"]) ?? [],
              transaction_hashes: (maybeResult.transaction_hashes as string[]) ?? [],
              payments: (maybeResult.payments as RunResponse["payments"]) ?? [],
              failed_tasks: (maybeResult.failed_tasks as string[]) ?? [],
              pending_question: (maybeResult.pending_question as string | null | undefined) ?? null,
            };
          }
        }
      } catch (err) {
        console.error("Failed to parse SSE event:", data, err);
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        console.log(`[runMarketplaceStream] SSE stream ended. Total events received: ${eventCount}`);
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";

      for (const block of events) {
        const dataLines = block
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.replace(/^data:\s?/, ""));

        if (dataLines.length === 0) continue;
        processEventPayload(dataLines.join("\n"));
      }
    }

    if (buffer.trim()) {
      const dataLines = buffer
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.replace(/^data:\s?/, ""));
      if (dataLines.length > 0) {
        processEventPayload(dataLines.join("\n"));
      }
    }

  } finally {
    reader.releaseLock();
  }

  if (!finalResult) {
    throw new Error("Stream ended without a complete result. Please retry.");
  }

  return finalResult;
}

export function getHealth() {
  return apiRequest<HealthResponse>("/health");
}

export { API_BASE_URL };
