import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Copy, ExternalLink, PenTool, Wallet as WalletIcon } from "lucide-react";
import { useAppState } from "../lib/app-state";
import { getTransactions, type Transaction } from "../lib/api";

const ARC_EXPLORER_BASE_URL = "https://testnet.arcscan.app";

function shorten(value: string, start = 10, end = 8) {
  if (value.length <= start + end + 3) return value;
  return `${value.slice(0, start)}...${value.slice(-end)}`;
}

export function Wallet() {
  const { currentBuyer, latestRun, health } = useAppState();
  const [copied, setCopied] = useState(false);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isLoadingTransactions, setIsLoadingTransactions] = useState(true);

  const payments = latestRun?.payments ?? [];
  const paymentTotal = useMemo(
    () => payments.reduce((sum, payment) => sum + Number(payment.amount_usdc || 0), 0),
    [payments],
  );
  const latestPayment = payments[0] ?? null;

  useEffect(() => {
    const fetchTransactions = async () => {
      try {
        setIsLoadingTransactions(true);
        const response = await getTransactions();
        setTransactions(response.transactions || []);
      } catch (err) {
        console.error("Error fetching transactions:", err);
        setTransactions([]);
      } finally {
        setIsLoadingTransactions(false);
      }
    };

    fetchTransactions();
  }, []);

  // Refresh transactions when latestRun changes
  useEffect(() => {
    if (latestRun?.thread_id) {
      const fetchTransactions = async () => {
        try {
          const response = await getTransactions();
          setTransactions(response.transactions || []);
        } catch (err) {
          console.error("Error fetching transactions:", err);
        }
      };
      fetchTransactions();
    }
  }, [latestRun?.thread_id]);

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
                <p className="mt-2 text-3xl font-black uppercase tracking-tight text-white">{paymentTotal.toFixed(3)}</p>
                <p className="mt-1 text-[10px] font-black uppercase tracking-[0.15em] text-gray-400">USDC</p>
              </div>
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-400">Payment Count</p>
                <p className="mt-2 text-3xl font-black uppercase tracking-tight text-white">{payments.length}</p>
                <p className="mt-1 text-[10px] font-black uppercase tracking-[0.15em] text-gray-400">Recorded</p>
              </div>
            </div>
            <div className="mt-6 border-t border-white/20 pt-5">
              <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-400">Latest Transaction</p>
              <p className="mt-2 text-xs font-black uppercase tracking-widest text-white">
                {latestPayment ? `${latestPayment.state} • ${latestPayment.amount_usdc} USDC` : "No payments recorded yet"}
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
          <div className="text-right">
            <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">Buyer Address</p>
            <p className="mt-2 font-mono text-xs font-bold text-black">{shorten(walletAddress)}</p>
          </div>
        </div>

        <div className="p-8">
          {isLoadingTransactions ? (
            <div className="border-2 border-dashed border-black p-6 text-center">
              <p className="text-xs font-black uppercase tracking-[0.15em] text-black">Loading transactions...</p>
            </div>
          ) : transactions.length === 0 ? (
            <div className="border-2 border-dashed border-black p-6 text-center">
              <p className="text-xs font-black uppercase tracking-[0.15em] text-black">No wallet payments yet</p>
              <p className="mt-3 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                Fund the wallet, then run the buyer workflow from the dashboard to create real payment records here.
              </p>
            </div>
          ) : (
            <div className="space-y-5">
              {transactions.map((tx) => {
                const explorerUrl = tx.tx_hash ? `${ARC_EXPLORER_BASE_URL}/tx/${tx.tx_hash}` : null;
                return (
                  <div key={tx.id} className="grid grid-cols-1 gap-5 border-b border-gray-200 pb-5 last:border-b-0 last:pb-0 md:grid-cols-[1.3fr_0.8fr_0.8fr_auto]">
                    <div>
                      <p className="text-xs font-black uppercase tracking-widest text-black">{tx.task_id}</p>
                      <p className="mt-2 break-all font-mono text-[10px] font-bold text-gray-500">{tx.circle_transaction_id}</p>
                    </div>
                    <div>
                      <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">Amount</p>
                      <p className="mt-2 text-xs font-black uppercase tracking-widest text-black">{Number(tx.amount_usdc || 0).toFixed(6)} USDC</p>
                    </div>
                    <div>
                      <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">State</p>
                      <p className="mt-2 text-xs font-black uppercase tracking-widest text-black">{tx.state}</p>
                    </div>
                    <div className="md:justify-self-end">
                      {explorerUrl ? (
                        <a
                          href={explorerUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-2 border-2 border-black px-4 py-3 text-[10px] font-black uppercase tracking-[0.18em] text-black shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] transition-all hover:-translate-y-0.5 hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]"
                        >
                          <ExternalLink size={14} />
                          Open Tx
                        </a>
                      ) : null}
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
