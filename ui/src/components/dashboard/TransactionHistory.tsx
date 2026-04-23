import { useMemo } from "react";
import { ExternalLink } from "lucide-react";
import type { PaymentRecord, RunResponse } from "../../lib/api";

interface TransactionHistoryProps {
  payments: PaymentRecord[];
  latestRun: RunResponse | null;
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

function formatPaymentState(state: string): string {
  return state
    .toLowerCase()
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}

export function TransactionHistory({ payments, latestRun }: TransactionHistoryProps) {
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

  const total = payments.reduce((sum, payment) => sum + Number(payment.amount_usdc || 0), 0);
  const sortedPayments = [...payments].sort((a, b) => {
    const dateA = new Date(a.created_at || 0).getTime();
    const dateB = new Date(b.created_at || 0).getTime();
    return dateB - dateA;
  });

  const getTaskName = (payment: PaymentRecord): string => {
    const metadata = payment.metadata;
    const metadataQuery = typeof metadata?.query === "string" ? metadata.query : null;
    const metadataDescription = typeof metadata?.description === "string" ? metadata.description : null;

    if (metadataQuery?.trim()) {
      return normalizeLabel(metadataQuery);
    }
    if (metadataDescription?.trim()) {
      return normalizeLabel(metadataDescription);
    }

    return taskNames.get(payment.task_id) ?? formatFallbackTaskName(payment.task_id);
  };

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="border-b-4 border-black px-6 py-4 flex items-center justify-between">
        <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-black">Ledger Stream</h3>
        <span className="text-[9px] font-bold text-gray-400">TOTAL: {total.toFixed(6)} USDC</span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-6 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
        {sortedPayments.length === 0 ? (
          <div className="border-2 border-dashed border-black p-5 text-center">
            <p className="text-xs font-black uppercase tracking-[0.15em] text-black">No transactions yet</p>
            <p className="mt-3 text-[10px] font-bold uppercase tracking-widest text-gray-500">
              Run the buyer workflow to populate the backend payment ledger here.
            </p>
          </div>
        ) : (
        <div className="space-y-4">
          {sortedPayments.map((tx) => {
            const txId = tx.circle_transaction_id || tx.task_id;
            const explorerUrl = tx.tx_hash ? `${TESTNET_EXPLORER}/tx/${tx.tx_hash}` : null;
            const statusLabel = formatPaymentState(tx.state);
            const statusClass =
              tx.state === "CONFIRMED" || tx.state === "COMPLETE"
                ? "text-green-600 font-bold"
                : "text-yellow-600 font-bold";

            return (
            <div key={txId} className="flex items-center justify-between border-b border-gray-100 pb-4 last:border-b-0 last:pb-0">
              <div className="flex-1">
                <p className="text-xs font-bold tracking-wide text-black">{getTaskName(tx)}</p>
                <div className="flex items-center gap-2 mt-2 text-[9px] text-gray-600 font-mono">
                  {explorerUrl ? (
                    <a
                      href={explorerUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-blue-600 underline flex items-center gap-1"
                    >
                      {tx.tx_hash ? tx.tx_hash.substring(0, 16) + '...' : txId.substring(0, 16) + '...'}
                      <ExternalLink size={10} className="inline" />
                    </a>
                  ) : (
                    <span className="text-gray-400">{txId.substring(0, 16)}...</span>
                  )}
                  <span>•</span>
                  <span className={statusClass}>
                    {statusLabel}
                  </span>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs font-mono font-bold text-black">{Number(tx.amount_usdc || 0).toFixed(6)} USDC</p>
                <p className="text-[9px] text-gray-500 mt-1 uppercase font-bold">
                  {tx.created_at ? new Date(tx.created_at).toLocaleDateString() : 'Recorded'}
                </p>
              </div>
            </div>
          )})}
        </div>
        )}
      </div>
    </div>
  );
}
