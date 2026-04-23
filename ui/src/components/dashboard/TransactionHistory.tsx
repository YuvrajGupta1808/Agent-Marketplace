import { useEffect, useMemo, useState, useImperativeHandle, forwardRef } from "react";
import { ExternalLink } from "lucide-react";
import type { RunResponse, Transaction } from "../../lib/api";
import { getTransactions, pollPendingTransactions } from "../../lib/api";

interface TransactionHistoryProps {
  latestRun: RunResponse | null;
}

export interface TransactionHistoryRef {
  addRealtimeTransaction: (tx: Partial<Transaction>) => void;
}

const TESTNET_EXPLORER = "https://testnet.arcscan.app";
const MAX_LABEL_LENGTH = 60;

function truncateLabel(label: string): string {
  return label.length > MAX_LABEL_LENGTH ? `${label.slice(0, MAX_LABEL_LENGTH - 3)}...` : label;
}

function normalizeLabel(label: string): string {
  return truncateLabel(label.replace(/\s+/g, " ").trim());
}

function formatFallbackTaskName(taskId: string): string {
  const numberedTaskMatch = /^task-(\d+)$/i.exec(taskId);
  if (numberedTaskMatch) {
    return `Task ${numberedTaskMatch[1]}`;
  }

  return normalizeLabel(
    taskId
      .replace(/[-_]+/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase()),
  );
}

export const TransactionHistory = forwardRef<TransactionHistoryRef, TransactionHistoryProps>(
  ({ latestRun }, ref) => {
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [refreshing, setRefreshing] = useState(false);
    const [polling, setPolling] = useState(false);

    useImperativeHandle(ref, () => ({
      addRealtimeTransaction: (tx: Partial<Transaction>) => {
        setTransactions((prev) => {
          const isDuplicate = prev.some(
            (existingTx) => existingTx.circle_transaction_id === tx.circle_transaction_id
          );
          if (isDuplicate) return prev;

          const fullTx: Transaction = {
            id: tx.id || `tx-${Date.now()}`,
            thread_id: tx.thread_id || "unknown",
            task_id: tx.task_id || "unknown",
            buyer_agent_id: tx.buyer_agent_id || "",
            seller_agent_id: tx.seller_agent_id || "",
            circle_transaction_id: tx.circle_transaction_id || "",
            amount_usdc: tx.amount_usdc || "0",
            tx_hash: tx.tx_hash || null,
            state: tx.state || "INITIATED",
            created_at: tx.created_at || new Date().toISOString(),
            metadata_json: "{}",
            metadata: {},
          };

          return [fullTx, ...prev];
        });
      },
    }));

    const taskNames = useMemo(() => {
      const labels = new Map<string, string>();

      for (const task of latestRun?.task_specs ?? []) {
        if (task.query?.trim()) {
          labels.set(task.task_id, normalizeLabel(task.query));
          continue;
        }
        if (task.objective?.trim()) {
          labels.set(task.task_id, normalizeLabel(task.objective));
        }
      }

      for (const result of latestRun?.results ?? []) {
        if (!labels.has(result.task_id) && result.title?.trim()) {
          labels.set(result.task_id, normalizeLabel(result.title));
        }
      }

      return labels;
    }, [latestRun]);

    const fetchTransactions = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const response = await getTransactions();
        setTransactions(response.transactions || []);
        console.log(`Loaded ${response.transactions?.length || 0} transactions from database`);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : "Failed to fetch transactions";
        setError(errMsg);
        console.error("Error fetching transactions:", errMsg);
        setTransactions([]);
      } finally {
        setIsLoading(false);
      }
    };

    useEffect(() => {
      fetchTransactions();

      const refreshInterval = setInterval(fetchTransactions, 5000);

      const pollInterval = setInterval(async () => {
        try {
          const pending = transactions.filter(tx => tx.state === "INITIATED" && !tx.tx_hash);
          if (pending.length > 0) {
            await pollPendingTransactions();
            await fetchTransactions();
          }
        } catch (err) {
          // Silent fail for auto-poll
        }
      }, 15000);

      return () => {
        clearInterval(refreshInterval);
        clearInterval(pollInterval);
      };
    }, []);

    useEffect(() => {
      if (latestRun) {
        console.log("New run detected, refreshing transactions...");
        fetchTransactions();
      }
    }, [latestRun?.thread_id]);

    const handleRefresh = async () => {
      setRefreshing(true);
      await fetchTransactions();
      setRefreshing(false);
    };

    const handlePollCircle = async () => {
      setPolling(true);
      try {
        const result = await pollPendingTransactions();
        console.log(`📡 Polled Circle: ${result.updated} updated, ${result.total_pending} still pending`);
        await fetchTransactions();
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to poll Circle";
        console.error("Poll failed:", msg);
      } finally {
        setPolling(false);
      }
    };

    const confirmedTransactions = transactions.filter(tx =>
      tx.state === "COMPLETE" || tx.state === "CONFIRMED" || tx.state === "INITIATED"
    );
    const total = confirmedTransactions.reduce((sum, tx) => sum + Number(tx.amount_usdc || 0), 0);
    const sortedTransactions = [...confirmedTransactions].sort((a, b) => {
      const dateA = new Date(a.created_at).getTime();
      const dateB = new Date(b.created_at).getTime();
      return dateB - dateA;
    });

    const getTaskName = (tx: Transaction): string => {
      const metadata = tx.metadata;
      const metadataQuery = typeof metadata?.query === "string" ? metadata.query : null;
      const metadataDescription = typeof metadata?.description === "string" ? metadata.description : null;

      if (metadataQuery?.trim()) {
        return normalizeLabel(metadataQuery);
      }
      if (metadataDescription?.trim()) {
        return normalizeLabel(metadataDescription);
      }

      return taskNames.get(tx.task_id) ?? formatFallbackTaskName(tx.task_id);
    };

    return (
      <div className="flex h-full flex-col bg-white">
        <div className="border-b-4 border-black px-6 py-4 flex items-center justify-between">
          <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-black">Ledger Stream</h3>
          <div className="flex items-center gap-3">
            <span className="text-[9px] font-bold text-gray-400">TOTAL: {total.toFixed(6)} USDC</span>
            <button
              onClick={handlePollCircle}
              disabled={polling || isLoading}
              className="text-[9px] font-bold uppercase tracking-widest px-2 py-1 border border-black rounded hover:bg-blue-50 disabled:opacity-50"
              title="Poll Circle for pending transaction updates"
            >
              {polling ? "..." : "◆"}
            </button>
            <button
              onClick={handleRefresh}
              disabled={refreshing || isLoading}
              className="text-[9px] font-bold uppercase tracking-widest px-2 py-1 border border-black rounded hover:bg-gray-100 disabled:opacity-50"
              title="Refresh transactions"
            >
              {refreshing ? "..." : "↻"}
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-6 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
          {isLoading ? (
            <div className="border-2 border-dashed border-black p-5 text-center">
              <p className="text-xs font-black uppercase tracking-[0.15em] text-black">Loading transactions...</p>
            </div>
          ) : error ? (
            <div className="border-2 border-dashed border-red-300 p-5 text-center bg-red-50">
              <p className="text-xs font-black uppercase tracking-[0.15em] text-red-600">Error loading transactions</p>
              <p className="mt-2 text-[10px] font-bold text-red-500">{error}</p>
              <button
                onClick={handleRefresh}
                className="mt-3 text-[9px] font-bold uppercase tracking-widest px-3 py-2 bg-black text-white border border-black rounded hover:bg-gray-800"
              >
                Retry
              </button>
            </div>
          ) : sortedTransactions.length === 0 ? (
            <div className="border-2 border-dashed border-black p-5 text-center">
              <p className="text-xs font-black uppercase tracking-[0.15em] text-black">No confirmed transactions yet</p>
              <p className="mt-3 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                Transactions will appear here once they are confirmed on the blockchain.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {sortedTransactions.map((tx) => {
                const isComplete = tx.state === 'COMPLETE' && tx.tx_hash;
                const explorerUrl = isComplete ? `${TESTNET_EXPLORER}/tx/${tx.tx_hash}` : null;
                const shortTaskName = getTaskName(tx);
                const circleIdShort = `${tx.circle_transaction_id.slice(0, 8)}...${tx.circle_transaction_id.slice(-8)}`;
                const txHashShort = tx.tx_hash ? `${tx.tx_hash.slice(0, 12)}...${tx.tx_hash.slice(-12)}` : null;

                return (
                  <div key={tx.id} className="border-2 border-black bg-white">
                    <div className="flex gap-4 p-4">
                      {/* LEFT BOX: Transaction Core Info */}
                      <div className="flex-1 min-w-0 flex flex-col justify-between">
                        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-700 mb-2 line-clamp-1">
                          {shortTaskName}
                        </p>

                        <p className="text-xl font-black text-black mb-3">
                          {Number(tx.amount_usdc || 0).toFixed(6)}
                        </p>

                        <p className="text-[8px] font-mono text-gray-500 truncate" title={tx.circle_transaction_id}>
                          {circleIdShort}
                        </p>
                      </div>

                      {/* RIGHT BOX: Blockchain Confirmation */}
                      <div className="flex-1 border-l-2 border-gray-200 pl-4 flex flex-col justify-between">
                        <p className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-2">
                          {isComplete ? 'ON CHAIN' : 'PENDING'}
                        </p>

                        {isComplete ? (
                          <>
                            <a
                              href={explorerUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm font-black text-blue-600 hover:text-blue-800 hover:underline transition-colors mb-2 flex items-center gap-1 group"
                              title={`View on Arc: ${tx.tx_hash}`}
                            >
                              <span className="truncate">{txHashShort}</span>
                              <ExternalLink size={12} className="flex-shrink-0 group-hover:translate-x-0.5 transition-transform" />
                            </a>
                            <p className="text-[8px] font-bold text-green-700">CONFIRMED</p>
                          </>
                        ) : (
                          <>
                            <p className="text-sm font-bold text-gray-400">-</p>
                            <p className="text-[8px] font-bold text-gray-500">Awaiting confirmation...</p>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    );
  }
);

TransactionHistory.displayName = "TransactionHistory";
