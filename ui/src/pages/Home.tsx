import { ShoppingCart, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppState } from "../lib/app-state";
import { formatToolNames, getSellerPrice, getSellerStatus, getSellerToolIds, isSellerPublished } from "../lib/seller";

export function Home() {
  const navigate = useNavigate();
  const { currentUser, currentBuyer, health, sellerAgents, setSelectedSellerId } = useAppState();
  const [query, setQuery] = useState("");
  const [ownershipFilter, setOwnershipFilter] = useState<"all" | "mine" | "not_mine">("all");

  const filteredAgents = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return sellerAgents.filter((agent) => {
      const isMine = !!currentUser && agent.user_id === currentUser.id;
      const isPublished = isSellerPublished(agent);
      const passesOwnershipFilter =
        ownershipFilter === "mine"
          ? isMine
          : ownershipFilter === "not_mine"
            ? isPublished && !isMine
            : isPublished;
      if (!passesOwnershipFilter) {
        return false;
      }

      const description =
        typeof agent.metadata.description === "string" ? agent.metadata.description : agent.description;
      const useCase = typeof agent.metadata.use_case === "string" ? agent.metadata.use_case : "";
      const category = typeof agent.metadata.category === "string" ? agent.metadata.category : "";
      if (!normalizedQuery) {
        return true;
      }
      return [agent.name, description, useCase, category].some((value) =>
        value.toLowerCase().includes(normalizedQuery),
      );
    });
  }, [currentUser, ownershipFilter, query, sellerAgents]);

  const handleAcquire = (sellerId: string, isOwnedByCurrentUser: boolean) => {
    setSelectedSellerId(sellerId);
    if (isOwnedByCurrentUser) {
      navigate("/seller-test");
      return;
    }
    navigate(currentBuyer ? "/dashboard" : "/builder");
  };

  return (
    <div className="mx-auto max-w-7xl px-8 py-16 w-full">
      <div className="mb-16 flex flex-col md:flex-row md:items-end justify-between gap-6 relative">
        <div>
          <h1 className="text-4xl font-black uppercase tracking-tighter text-black">Agent Marketplace</h1>
          <p className="mt-2 text-xs font-bold uppercase tracking-widest text-gray-500">Discover and connect with specialized seller agents.</p>
        </div>
        <div className="w-full max-w-md flex flex-col sm:flex-row gap-3">
          <div className="relative w-full block group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-black transition-transform group-hover:scale-110" size={18} />
            <input
              type="text"
              placeholder="SEARCH AGENTS..."
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full bg-white border-2 border-black py-3 pl-12 pr-4 text-xs font-bold tracking-widest outline-none transition-all focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
            />
          </div>
          <select
            value={ownershipFilter}
            onChange={(event) => setOwnershipFilter(event.target.value as "all" | "mine" | "not_mine")}
            className="w-full sm:w-40 bg-white border-2 border-black py-3 px-4 text-xs font-bold uppercase tracking-widest outline-none focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
          >
            <option value="all">All</option>
            <option value="mine">Mine</option>
            <option value="not_mine">Not Mine</option>
          </select>
        </div>
      </div>

      {!health?.circle_enabled ? (
        <div className="mb-10 border-2 border-red-500 bg-red-50 p-5 text-[10px] font-bold uppercase tracking-[0.2em] text-red-700">
          Circle is not configured on the backend. Marketplace actions require a real Circle wallet.
        </div>
      ) : null}

      {filteredAgents.length === 0 ? (
        <div className="border-2 border-black bg-gray-50 p-8 text-center shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]">
          <p className="text-xs font-black uppercase tracking-[0.15em] text-black">No seller agents available</p>
          <p className="mt-3 text-[10px] font-bold uppercase tracking-widest text-gray-500">
            Create a hosted seller in Builder, test it, then publish it here.
          </p>
        </div>
      ) : (
      <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-3">
        {filteredAgents.map((agent) => {
          const isOwnedByCurrentUser = !!currentUser && agent.user_id === currentUser.id;
          const description =
            typeof agent.metadata.description === "string"
              ? agent.metadata.description
              : agent.description || "No marketplace description provided.";
          const category =
            typeof agent.metadata.category === "string" ? agent.metadata.category : "Uncategorized";
          const creatorName =
            typeof agent.metadata.creator_name === "string" ? agent.metadata.creator_name : null;
          const priceLabel = `${getSellerPrice(agent)} USDC`;
          const status = getSellerStatus(agent);
          const toolsLabel = formatToolNames(getSellerToolIds(agent));

          return (
          <div
            key={agent.id}
            className="flex flex-col bg-white border-2 border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] transition-transform hover:-translate-y-1 flex-1"
          >
            <div className="p-8">
              <div className="mb-6 flex items-center justify-between">
                <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400">
                  {status === "published" ? category : `${category} / ${status}`}
                </span>
                <span className="font-mono text-sm font-bold text-black border-b-2 border-black pb-0.5">
                  {priceLabel}
                </span>
              </div>
              <h3 className="mb-3 text-2xl font-bold italic text-black uppercase">{agent.name}</h3>
              {creatorName && (
                <p className="text-[10px] font-mono uppercase tracking-widest text-gray-400 mb-4">by {creatorName}</p>
              )}
              <p className="text-sm font-medium leading-relaxed text-gray-600 line-clamp-3">{description}</p>
              <div className="mt-5 border-t-2 border-dashed border-gray-200 pt-4">
                <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">Tools</p>
                <p className="mt-2 text-xs font-bold uppercase tracking-widest text-black">{toolsLabel}</p>
              </div>
            </div>
            <div className="mt-auto border-t-2 border-black">
              <button
                onClick={() => handleAcquire(agent.id, isOwnedByCurrentUser)}
                className="flex w-full items-center justify-center gap-3 bg-black py-5 text-[10px] font-black uppercase tracking-[0.2em] text-white transition-colors hover:bg-gray-800 rounded-none"
              >
                <ShoppingCart size={16} />
                {isOwnedByCurrentUser ? "Test Agent" : currentBuyer ? "Open In Dashboard" : "Connect In Builder"}
              </button>
            </div>
          </div>
        )})}
      </div>
      )}
    </div>
  );
}
