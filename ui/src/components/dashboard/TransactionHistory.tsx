import type { PaymentRecord } from "../../lib/api";

interface TransactionHistoryProps {
  payments: PaymentRecord[];
}

function formatTxTime(transactionId: string) {
  return transactionId ? "Recorded" : "Pending";
}

export function TransactionHistory({ payments }: TransactionHistoryProps) {
  const total = payments.reduce((sum, payment) => sum + Number(payment.amount_usdc || 0), 0);

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="border-b-4 border-black px-6 py-4 flex items-center justify-between">
        <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-black">Ledger Stream</h3>
        <span className="text-[9px] font-bold text-gray-400">TOTAL: {total.toFixed(3)} USDC</span>
      </div>
      
      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-6 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
        {payments.length === 0 ? (
          <div className="border-2 border-dashed border-black p-5 text-center">
            <p className="text-xs font-black uppercase tracking-[0.15em] text-black">No transactions yet</p>
            <p className="mt-3 text-[10px] font-bold uppercase tracking-widest text-gray-500">
              Run the buyer workflow to populate the backend payment ledger here.
            </p>
          </div>
        ) : (
        <div className="space-y-4">
          {payments.map((tx) => {
            return (
            <div key={tx.circle_transaction_id} className="flex items-center justify-between border-b border-gray-100 pb-4 last:border-b-0 last:pb-0">
              <div>
                <p className="text-xs font-black uppercase tracking-widest text-black">{tx.task_id}</p>
                <div className="flex items-center gap-2 mt-1 text-[10px] text-gray-500 font-mono">
                  <span>{tx.circle_transaction_id}</span>
                  <span>•</span>
                  <span>{tx.state}</span>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs font-mono font-bold text-black">{tx.amount_usdc} USDC</p>
                <p className="text-[10px] text-gray-500 mt-1 uppercase font-bold">{formatTxTime(tx.circle_transaction_id)}</p>
              </div>
            </div>
          )})}
        </div>
        )}
      </div>
    </div>
  );
}
