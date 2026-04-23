import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import {
  AgentRecord,
  HealthResponse,
  PaymentRecord,
  RunResponse,
  UserRecord,
  createAgent,
  createUser,
  getHealth,
  getUser,
  listAgents,
  listUserAgents,
  runMarketplace,
} from "./api";

interface AppStateValue {
  currentUser: UserRecord | null;
  currentBuyer: AgentRecord | null;
  sellerAgents: AgentRecord[];
  selectedSellerId: string | null;
  latestRun: RunResponse | null;
  health: HealthResponse | null;
  isReady: boolean;
  isStreaming: boolean;
  allPayments: PaymentRecord[];
  loginAsUser: (user: UserRecord) => Promise<void>;
  registerNewUser: (displayName: string, externalId?: string) => Promise<UserRecord>;
  logout: () => void;
  refreshData: () => Promise<void>;
  createBuyerAgent: (payload: {
    name: string;
    description: string;
    prompt: string;
    connectedSellerIds: string[];
  }) => Promise<AgentRecord>;
  setSelectedSellerId: React.Dispatch<React.SetStateAction<string | null>>;
  setLatestRun: React.Dispatch<React.SetStateAction<RunResponse | null>>;
  runBuyerWorkflow: (userGoal: string) => Promise<RunResponse>;
}

const STORAGE_KEYS = {
  userId: "agent-marketplace.user-id",
  buyerId: "agent-marketplace.buyer-id",
  selectedSellerId: "agent-marketplace.selected-seller-id",
  latestRun: "agent-marketplace.latest-run",
};

const AppStateContext = createContext<AppStateValue | null>(null);

function getPaymentIdentity(payment: PaymentRecord): string {
  if (payment.circle_transaction_id) return `circle:${payment.circle_transaction_id}`;
  if (payment.tx_hash) return `hash:${payment.tx_hash}`;
  return `task:${payment.task_id}:${payment.created_at ?? ""}:${payment.amount_usdc ?? ""}`;
}

function mergePayments(existing: PaymentRecord[], incoming: PaymentRecord[]): PaymentRecord[] {
  const merged = new Map<string, PaymentRecord>();

  for (const payment of existing) {
    merged.set(getPaymentIdentity(payment), payment);
  }

  for (const payment of incoming) {
    merged.set(getPaymentIdentity(payment), payment);
  }

  return Array.from(merged.values());
}

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [currentUser, setCurrentUser] = useState<UserRecord | null>(null);
  const [currentBuyer, setCurrentBuyer] = useState<AgentRecord | null>(null);
  const [sellerAgents, setSellerAgents] = useState<AgentRecord[]>([]);
  const [selectedSellerId, setSelectedSellerId] = useState<string | null>(null);
  const [latestRun, setLatestRun] = useState<RunResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [allPayments, setAllPayments] = useState<PaymentRecord[]>([]);

  const refreshData = async () => {
    const [healthPayload, sellers] = await Promise.all([
      getHealth(),
      listAgents({ role: "seller" }),
    ]);
    setHealth(healthPayload);
    setSellerAgents(sellers);

    const userId = localStorage.getItem(STORAGE_KEYS.userId);
    if (!userId) {
      setCurrentUser(null);
      setCurrentBuyer(null);
      setIsReady(true);
      return;
    }

    let user: UserRecord;
    try {
      user = await getUser(userId);
    } catch {
      localStorage.removeItem(STORAGE_KEYS.userId);
      localStorage.removeItem(STORAGE_KEYS.buyerId);
      localStorage.removeItem(STORAGE_KEYS.selectedSellerId);
      localStorage.removeItem(STORAGE_KEYS.latestRun);
      setCurrentUser(null);
      setCurrentBuyer(null);
      setSelectedSellerId(sellers[0]?.id ?? null);
      setLatestRun(null);
      setAllPayments([]);
      setIsReady(true);
      return;
    }
    setCurrentUser(user);

    const buyers = await listUserAgents(userId, "buyer");
    const storedBuyerId = localStorage.getItem(STORAGE_KEYS.buyerId);
    const buyer = buyers.find((item) => item.id === storedBuyerId) ?? buyers.at(-1) ?? null;
    setCurrentBuyer(buyer);
    if (buyer) {
      localStorage.setItem(STORAGE_KEYS.buyerId, buyer.id);
    } else {
      localStorage.removeItem(STORAGE_KEYS.buyerId);
    }

    const storedSellerId = localStorage.getItem(STORAGE_KEYS.selectedSellerId);
    const sellerIdsFromBuyer = Array.isArray(buyer?.metadata?.connected_seller_ids)
      ? (buyer?.metadata?.connected_seller_ids as string[])
      : [];
    const availableSellerIds = new Set(
      sellers
        .filter((seller) => sellerIdsFromBuyer.length === 0 || sellerIdsFromBuyer.includes(seller.id))
        .map((seller) => seller.id),
    );
    const nextSellerId =
      (storedSellerId && availableSellerIds.has(storedSellerId) && storedSellerId) ||
      sellerIdsFromBuyer.find((sellerId) => availableSellerIds.has(sellerId)) ||
      sellers[0]?.id ||
      null;
    setSelectedSellerId(nextSellerId);
    setIsReady(true);
  };

  useEffect(() => {
    const latestRunRaw = localStorage.getItem(STORAGE_KEYS.latestRun);
    if (latestRunRaw) {
      try {
        setLatestRun(JSON.parse(latestRunRaw) as RunResponse);
      } catch {
        localStorage.removeItem(STORAGE_KEYS.latestRun);
      }
    }
    void refreshData();
    setAllPayments([]);
  }, []);

  useEffect(() => {
    if (selectedSellerId) {
      localStorage.setItem(STORAGE_KEYS.selectedSellerId, selectedSellerId);
    } else {
      localStorage.removeItem(STORAGE_KEYS.selectedSellerId);
    }
  }, [selectedSellerId]);

  useEffect(() => {
    if (latestRun) {
      localStorage.setItem(STORAGE_KEYS.latestRun, JSON.stringify(latestRun));
    } else {
      localStorage.removeItem(STORAGE_KEYS.latestRun);
    }
  }, [latestRun]);

  const loginAsUser = async (user: UserRecord) => {
    localStorage.setItem(STORAGE_KEYS.userId, user.id);
    setCurrentUser(user);
    await refreshData();
  };

  const registerNewUser = async (displayName: string, externalId?: string) => {
    const response = await createUser(displayName, externalId);
    await loginAsUser(response.user);
    return response.user;
  };

  const logout = () => {
    localStorage.removeItem(STORAGE_KEYS.userId);
    localStorage.removeItem(STORAGE_KEYS.buyerId);
    localStorage.removeItem(STORAGE_KEYS.selectedSellerId);
    localStorage.removeItem(STORAGE_KEYS.latestRun);
    setCurrentUser(null);
    setCurrentBuyer(null);
    setSelectedSellerId(null);
    setLatestRun(null);
    setAllPayments([]);
  };

  const createBuyerAgentForUser = async (payload: {
    name: string;
    description: string;
    prompt: string;
    connectedSellerIds: string[];
  }) => {
    if (!currentUser) {
      throw new Error("Register or log in before creating a buyer agent.");
    }
    if (!health?.circle_enabled) {
      throw new Error("Circle is not configured on the backend. Real Circle wallets are required.");
    }

    const response = await createAgent({
      userId: currentUser.id,
      role: "buyer",
      name: payload.name,
      metadata: {
        description: payload.description,
        prompt: payload.prompt,
        connected_seller_ids: payload.connectedSellerIds,
      },
    });
    localStorage.setItem(STORAGE_KEYS.buyerId, response.agent.id);
    setCurrentBuyer(response.agent);
    if (payload.connectedSellerIds[0]) {
      setSelectedSellerId(payload.connectedSellerIds[0]);
    }
    return response.agent;
  };

  const runBuyerWorkflow = async (userGoal: string) => {
    if (!currentBuyer) {
      throw new Error("Create a buyer agent before running the workflow.");
    }
    if (!health?.circle_enabled) {
      throw new Error("Circle is not configured on the backend. Real Circle payments are required.");
    }
    if (!selectedSellerId) {
      throw new Error("Select a seller agent before running the workflow.");
    }

    setIsStreaming(true);

    try {
      const result = await runMarketplace({
        userGoal,
        buyerAgentId: currentBuyer.id,
        sellerAgentId: selectedSellerId,
      });
      setLatestRun(result);
      // Keep full session ledger history while deduplicating repeated events.
      setAllPayments((currentPayments) => mergePayments(currentPayments, result.payments ?? []));
      return result;
    } finally {
      setIsStreaming(false);
    }
  };

  const value = useMemo<AppStateValue>(
    () => ({
      currentUser,
      currentBuyer,
      sellerAgents,
      selectedSellerId,
      latestRun,
      health,
      isReady,
      isStreaming,
      allPayments,
      loginAsUser,
      registerNewUser,
      logout,
      refreshData,
      createBuyerAgent: createBuyerAgentForUser,
      setSelectedSellerId,
      setLatestRun,
      runBuyerWorkflow,
    }),
    [currentUser, currentBuyer, sellerAgents, selectedSellerId, latestRun, health, isReady, isStreaming, allPayments],
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState() {
  const context = useContext(AppStateContext);
  if (!context) {
    throw new Error("useAppState must be used inside AppStateProvider.");
  }
  return context;
}
