import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Copy, ExternalLink, PenTool, Wallet as WalletIcon } from "lucide-react";
import { useAppState } from "../lib/app-state";
import { getTransactions, pollPendingTransactions, type Transaction } from "../lib/api";

const ARC_EXPLORER_BASE_URL = "https://testnet.arcscan.app";

function shorten(value: string, start = 10, end = 8) {
  if (value.length <= start + end + 3) return value;
  return `${value.slice(0, start)}...${value.slice(-end)}`;
}

export function Wallet() {
  const { buyerAgents, currentBuyer, latestRun, health, selectBuyerAgent } = useAppState();
  const [copied, setCopied] = useState(false);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isLoadingTransactions, setIsLoadingTransactions] = useState(true);
  const [polling, setPolling] = useState(false);

  const scopedFetchTransactions = async (buyerId: string) => {
    const response = await getTransactions({ buyerAgentId: buyerId });
    // Show all transactions that have been processed (INITIATED, CONFIRMED, or COMPLETE)
    return (response.transactions || []).filter(
      (tx) => tx.state === "COMPLETE" || tx.state === "CONFIRMED" || tx.state === "INITIATED",
    );
  };

  // Real-time payment snapshot from transactions instead of latestRun
  const paymentTotal = useMemo(
    () => transactions.reduce((sum, tx) => sum + Number(tx.amount_usdc || 0), 0),
    [transactions],
  );
  const paymentCount = useMemo(
    () => transactions.filter(tx => tx.state === 'COMPLETE' || tx.state === 'CONFIRMED').length,
    [transactions],
  );
  const latestPayment = transactions.length > 0 ? transactions[0] : null;

  useEffect(() => {
    const fetchTransactions = async () => {
      if (!currentBuyer) {
        setTransactions([]);
        setIsLoadingTransactions(false);
        return;
      }
      try {
        setIsLoadingTransactions(true);
        const scopedTransactions = await scopedFetchTransactions(currentBuyer.id);
        setTransactions(scopedTransactions);
      } catch (err) {
        console.error("Error fetching transactions:", err);
        setTransactions([]);
      } finally {
        setIsLoadingTransactions(false);
      }
    };

    fetchTransactions();

    // Auto-refresh every 5 seconds to catch confirmed transactions
    const interval = setInterval(fetchTransactions, 5000);
    return () => clearInterval(interval);
  }, [currentBuyer?.id]);

  // Refresh transactions when latestRun changes
  useEffect(() => {
    if (latestRun?.thread_id && currentBuyer) {
      const fetchTransactions = async () => {
        try {
          const scopedTransactions = await scopedFetchTransactions(currentBuyer.id);
          setTransactions(scopedTransactions);
        } catch (err) {
          console.error("Error fetching transactions:", err);
        }
      };
      fetchTransactions();
    }
  }, [latestRun?.thread_id, currentBuyer?.id]);

  const handleCopyAddress = async () => {
    if (!currentBuyer?.wallet.address) return;
    try {
      await navigator.clipboard.writeText(currentBuyer.wallet.address);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  const handlePollCircle = async () => {
    if (!currentBuyer) return;
    setPolling(true);
    try {
      const result = await pollPendingTransactions();
      console.log(`📡 Polled Circle: ${result.updated} updated, ${result.total_pending} still pending`);
      // Refresh transactions after polling
      const scopedTransactions = await scopedFetchTransactions(currentBuyer.id);
      setTransactions(scopedTransactions);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to poll Circle";
      console.error("Poll failed:", msg);
    } finally {
      setPolling(false);
    }
  };

  if (!currentBuyer) {
    return (
      <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-8 py-16">
        <div className="border-2 border-black bg-white p-10 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
          <div className="mb-6 flex h-16 w-16 items-center justify-center bg-black text-white">
            <WalletIcon size={28} />
          </div>
          <h1 className="text-4xl font-black uppercase tracking-tighter text-black">Wallet Control</h1>
          <p className="mt-4 max-w-2xl text-xs font-bold uppercase tracking-widest text-gray-500">
            Build a buyer agent first. The buyer agent is what provisions the Circle wallet used for marketplace payments.
          </p>
          <div className="mt-8">
            <Link
              to="/builder"
              className="inline-flex items-center justify-center border-2 border-black bg-black px-6 py-4 text-[10px] font-black uppercase tracking-[0.2em] text-white transition-all hover:-translate-y-0.5 hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]"
            >
              Open Builder
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const walletAddress = currentBuyer.wallet.address;
  const walletExplorerUrl = `${ARC_EXPLORER_BASE_URL}/address/${walletAddress}`;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col px-8 py-16">
      <div className="mb-12 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-4xl font-black uppercase tracking-tighter text-black">Wallet And Payments</h1>
          <p className="mt-3 max-w-3xl text-xs font-bold uppercase tracking-widest text-gray-500">
            Fund the buyer wallet externally, then use this page to verify the destination address, track payment activity, and inspect the Circle wallet identifiers.
          </p>
          <div className="mt-4">
            {buyerAgents.length > 0 ? (
              <select
                aria-label="Select buyer wallet"
                value={currentBuyer.id}
                onChange={(event) => selectBuyerAgent(event.target.value)}
                className="max-w-[320px] border-2 border-black bg-white px-3 py-2 text-[10px] font-black uppercase tracking-[0.16em] text-black outline-none"
              >
                {buyerAgents.map((buyerAgent) => (
                  <option key={buyerAgent.id} value={buyerAgent.id}>
                    {buyerAgent.name}
                  </option>
                ))}
              </select>
            ) : null}
          </div>
        </div>
        <div className="border-2 border-black bg-black px-4 py-3 text-[10px] font-black uppercase tracking-[0.2em] text-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
          {health?.circle_enabled ? "Circle Backend Active" : "Circle Backend Not Ready"}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1.3fr_0.9fr]">
        <section className="border-2 border-black bg-white p-8 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
          <div className="flex items-start justify-between gap-6">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Funding Address</p>
              <h2 className="mt-3 text-2xl font-black uppercase tracking-tight text-black">{currentBuyer.name}</h2>
            </div>
            <div className="border-2 border-black bg-gray-50 px-3 py-2 text-[10px] font-black uppercase tracking-[0.15em] text-black">
              Buyer Wallet
            </div>
          </div>

          <div className="mt-8 border-2 border-black bg-gray-50 p-5">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Deposit USDC Here</p>
            <code className="mt-4 block break-all text-sm font-black text-black md:text-base">{walletAddress}</code>
          </div>

          <div className="mt-6 flex flex-col gap-4 sm:flex-row">
            <button
              onClick={handleCopyAddress}
              className="inline-flex items-center justify-center gap-2 border-2 border-black bg-black px-5 py-4 text-[10px] font-black uppercase tracking-[0.2em] text-white transition-all hover:-translate-y-0.5 hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]"
            >
              <Copy size={14} />
              {copied ? "Address Copied" : "Copy Address"}
            </button>
            <a
              href={walletExplorerUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center justify-center gap-2 border-2 border-black bg-white px-5 py-4 text-[10px] font-black uppercase tracking-[0.2em] text-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-all hover:-translate-y-0.5 hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]"
            >
              <ExternalLink size={14} />
              Open In Arc Explorer
            </a>
          </div>

          <div className="mt-8 border-t-2 border-dashed border-black pt-6">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">How To Add Funds</p>
            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="border-2 border-black p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">Asset</p>
                <p className="mt-2 text-xs font-black uppercase tracking-widest text-black">USDC</p>
              </div>
              <div className="border-2 border-black p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">Network</p>
                <p className="mt-2 text-xs font-black uppercase tracking-widest text-black">ARC-TESTNET</p>
              </div>
              <div className="border-2 border-black p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">Method</p>
                <p className="mt-2 text-xs font-black uppercase tracking-widest text-black">External Transfer</p>
              </div>
            </div>
            <p className="mt-5 max-w-3xl text-[10px] font-bold uppercase tracking-widest text-gray-500">
              This UI does not mint or top up the wallet directly. Send testnet USDC to the buyer wallet address above, then use the dashboard workflow to spend from it.
            </p>
          </div>
        </section>

        <section className="flex flex-col gap-8">
          <div className="border-2 border-black bg-white p-8 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Wallet Profile</p>
            <div className="mt-6 space-y-5">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">Wallet ID</p>
                <p className="mt-2 break-all font-mono text-xs font-bold text-black">{currentBuyer.wallet.id}</p>
              </div>
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">Circle Wallet ID</p>
                <p className="mt-2 break-all font-mono text-xs font-bold text-black">{currentBuyer.wallet.circle_wallet_id}</p>
              </div>
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">Wallet Set ID</p>
                <p className="mt-2 break-all font-mono text-xs font-bold text-black">{currentBuyer.wallet.wallet_set_id}</p>
              </div>
              <div className="grid grid-cols-2 gap-4 border-t-2 border-dashed border-black pt-5">
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">Blockchain</p>
                  <p className="mt-2 text-xs font-black uppercase tracking-widest text-black">{currentBuyer.wallet.blockchain}</p>
                </div>
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">Account Type</p>
                  <p className="mt-2 text-xs font-black uppercase tracking-widest text-black">{currentBuyer.wallet.account_type}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="border-2 border-black bg-black p-8 text-white shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400">Payment Snapshot</p>
            <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-400">Total Sent</p>
                <p className="mt-2 text-3xl font-black uppercase tracking-tight text-white">{paymentTotal.toFixed(6)}</p>
                <p className="mt-1 text-[10px] font-black uppercase tracking-[0.15em] text-gray-400">USDC</p>
              </div>
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-400">Confirmed Payments</p>
                <p className="mt-2 text-3xl font-black uppercase tracking-tight text-white">{paymentCount}</p>
                <p className="mt-1 text-[10px] font-black uppercase tracking-[0.15em] text-gray-400">On Chain</p>
              </div>
            </div>
            <div className="mt-6 border-t border-white/20 pt-5">
              <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-400">Latest Transaction</p>
              <p className="mt-2 text-xs font-black uppercase tracking-widest text-white">
                {latestPayment ? `${latestPayment.state} • ${Number(latestPayment.amount_usdc).toFixed(6)} USDC` : "No payments recorded yet"}
              </p>
            </div>
          </div>
        </section>
      </div>

      <section className="mt-10 border-2 border-black bg-white shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
        <div className="flex items-center justify-between border-b-4 border-black px-8 py-5">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Payments Ledger</p>
            <h2 className="mt-2 text-xl font-black uppercase tracking-tight text-black">Wallet Payment Activity</h2>
          </div>
          <div className="flex items-center justify-end gap-3">
            <div className="text-right">
              <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">Buyer Address</p>
              <p className="mt-2 font-mono text-xs font-bold text-black">{shorten(walletAddress)}</p>
            </div>
            <button
              onClick={handlePollCircle}
              disabled={polling || isLoadingTransactions}
              className="text-[9px] font-bold uppercase tracking-widest px-3 py-2 border-2 border-black rounded hover:bg-blue-50 disabled:opacity-50 transition-colors"
              title="Poll Circle for pending transaction updates"
            >
              {polling ? "..." : "◆"}
            </button>
          </div>
        </div>

        <div className="p-8">
          {isLoadingTransactions ? (
            <div className="border-2 border-dashed border-black p-6 text-center">
              <p className="text-xs font-black uppercase tracking-[0.15em] text-black">Loading transactions...</p>
            </div>
          ) : transactions.length === 0 ? (
            <div className="border-2 border-dashed border-black p-6 text-center">
              <p className="text-xs font-black uppercase tracking-[0.15em] text-black">No confirmed payments yet</p>
              <p className="mt-3 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                Run the buyer workflow from the dashboard. Payments will appear here once confirmed on the blockchain.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {transactions.map((tx) => {
                const isComplete = tx.state === 'COMPLETE' && tx.tx_hash;
                const explorerUrl = isComplete ? `${ARC_EXPLORER_BASE_URL}/tx/${tx.tx_hash}` : null;
                const circleIdShort = `${tx.circle_transaction_id.slice(0, 8)}...${tx.circle_transaction_id.slice(-8)}`;
                const txHashShort = tx.tx_hash ? `${tx.tx_hash.slice(0, 12)}...${tx.tx_hash.slice(-12)}` : null;

                // Get the actual query/request from metadata instead of task_id
                const metadata = tx.metadata;
                const displayQuery = typeof metadata?.query === "string" ? metadata.query : tx.task_id;
                const truncatedQuery = displayQuery.length > 50 ? displayQuery.substring(0, 50) + "..." : displayQuery;

                return (
                  <div key={tx.id} className="border-2 border-black bg-white">
                    <div className="flex gap-4 p-4">
                      {/* LEFT BOX: Transaction Core Info */}
                      <div className="flex-1 min-w-0 flex flex-col justify-between">
                        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-700 mb-2 line-clamp-1" title={displayQuery}>
                          {truncatedQuery}
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
                              <ExternalLink size={12} className="shrink-0 group-hover:translate-x-0.5 transition-transform" />
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
      </section>

      <section className="mt-10 flex flex-col gap-4 border-2 border-black bg-gray-50 p-8 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Next Step</p>
          <p className="mt-3 text-xs font-bold uppercase tracking-widest text-black">
            After the wallet is funded, open the dashboard and run the buyer workflow against the seller agent.
          </p>
        </div>
        <Link
          to="/dashboard"
          className="inline-flex items-center justify-center gap-2 border-2 border-black bg-black px-5 py-4 text-[10px] font-black uppercase tracking-[0.2em] text-white transition-all hover:-translate-y-0.5 hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]"
        >
          <PenTool size={14} />
          Open Dashboard
        </Link>
      </section>
    </div>
  );
}
