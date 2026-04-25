import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Check, ArrowRight } from "lucide-react";
import { useAppState } from "../lib/app-state";

export function Builder() {
  const { createBuyerAgent, currentBuyer, currentUser, health, sellerAgents, selectedSellerId } = useAppState();
  const [agentType, setAgentType] = useState<"buyer" | "seller">("buyer");
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [isBuilt, setIsBuilt] = useState(false);
  const [builtAgentId, setBuiltAgentId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  React.useEffect(() => {
    if (selectedSellerId) {
      setSelectedAgents((prev) => (prev.includes(selectedSellerId) ? prev : [...prev, selectedSellerId]));
    }
  }, [selectedSellerId]);

  const toggleAgent = (id: string) => {
    setSelectedAgents((prev) =>
      prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]
    );
  };

  const handleBuild = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (agentType === "seller") {
      setError("Seller agent creation is intentionally not wired in this UI yet.");
      return;
    }
    if (!currentUser) {
      setError("Register or log in before building a buyer agent.");
      return;
    }
    if (!health?.circle_enabled) {
      setError("Circle is not configured on the backend. Real Circle wallets are required.");
      return;
    }

    setIsSubmitting(true);
    try {
      const agent = await createBuyerAgent({
        name,
        description,
        prompt,
        connectedSellerIds: selectedAgents,
      });
      setBuiltAgentId(agent.id);
      setIsBuilt(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create buyer agent.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isBuilt) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-32 text-center flex flex-col items-center">
        <div className="mx-auto mb-8 flex h-24 w-24 items-center justify-center bg-black border-4 border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
          <Check size={48} className="text-white" />
        </div>
        <h2 className="text-4xl font-black uppercase tracking-tighter text-black">Agent Successfully Built!</h2>
        <p className="mt-4 text-xs font-bold uppercase tracking-widest text-gray-500">Your buyer agent is now ready to use with Circle-backed payments.</p>
        <p className="mt-4 text-[10px] font-mono font-bold uppercase tracking-widest text-black">ID: {builtAgentId}</p>
        <div className="mt-10 w-full max-w-xs">
          <Link
            to="/dashboard"
            className="inline-flex items-center justify-center w-full gap-3 bg-black py-4 text-[10px] font-black uppercase tracking-[0.2em] text-white transition-colors hover:bg-gray-800 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
          >
            Go to Dashboard <ArrowRight size={16} />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-8 py-16 w-full">
      <div className="mb-12 text-center">
        <h1 className="text-4xl font-black uppercase tracking-tighter text-black">Agent Builder</h1>
        <p className="mt-4 text-xs font-bold uppercase tracking-widest text-gray-500">Build buyer agents against the live backend. Seller creation stays deferred here.</p>
      </div>

      {!currentUser ? (
        <div className="mb-8 border-2 border-black bg-gray-50 p-6 text-center shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]">
          <p className="text-xs font-black uppercase tracking-[0.15em] text-black">No active user session</p>
          <p className="mt-3 text-[10px] font-bold uppercase tracking-widest text-gray-500">
            Register or log in first so the backend can attach the buyer agent to a real user.
          </p>
        </div>
      ) : null}

      {!health?.circle_enabled ? (
        <div className="mb-8 border-2 border-red-500 bg-red-50 p-6 text-center">
          <p className="text-xs font-black uppercase tracking-[0.15em] text-red-700">Circle required</p>
          <p className="mt-3 text-[10px] font-bold uppercase tracking-widest text-red-600">
            Buyer agent creation is blocked until Circle credentials are configured on the backend.
          </p>
        </div>
      ) : null}

      <div className="mb-10 flex border-2 border-black bg-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] relative overflow-hidden p-1">
        <button
          onClick={() => setAgentType("buyer")}
          className={`flex-1 py-4 text-[10px] font-black uppercase tracking-[0.2em] transition-colors ${
            agentType === "buyer" ? "bg-black text-white" : "text-gray-500 hover:text-black hover:bg-gray-50"
          }`}
        >
          Buyer Agent
        </button>
        <button
          onClick={() => setAgentType("seller")}
          className={`flex-1 py-4 text-[10px] font-black uppercase tracking-[0.2em] transition-colors ${
            agentType === "seller" ? "bg-black text-white" : "text-gray-500 hover:text-black hover:bg-gray-50"
          }`}
        >
          Seller Agent
        </button>
      </div>

      <form onSubmit={handleBuild} className="space-y-10 border-2 border-black bg-white p-8 sm:p-12 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
        <div>
          <label className="mb-3 block text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Agent Name</label>
          <input
            required
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="E.G. MASTER BUYER BOT"
            className="w-full bg-white border-2 border-black px-4 py-3 text-xs font-bold tracking-widest outline-none transition-all focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
          />
        </div>

        <div>
           <label className="mb-3 block text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Use Case Description</label>
           <textarea
             required
             rows={3}
             value={description}
             onChange={(event) => setDescription(event.target.value)}
             placeholder="DESCRIBE WHAT THIS AGENT WILL DO..."
             className="w-full bg-white border-2 border-black px-4 py-3 text-xs font-bold tracking-widest outline-none transition-all focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
           />
        </div>

        <div>
           <label className="mb-3 block text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Prompt / System Instruction</label>
           <textarea
             required
             rows={4}
             value={prompt}
             onChange={(event) => setPrompt(event.target.value)}
             placeholder="YOU ARE A HELPFUL ASSISTANT..."
             className="w-full bg-white border-2 border-black px-4 py-3 text-xs font-mono outline-none transition-all focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
           />
        </div>

        {agentType === "buyer" && (
          <div className="space-y-6 pt-8 border-t-2 border-black border-dashed">
            <div>
              <h3 className="text-sm font-black uppercase tracking-[0.1em] text-black">Connect Seller Agents</h3>
              <p className="mt-1 text-[10px] font-bold uppercase tracking-widest text-gray-500">Select the seller agents this buyer agent has access to.</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {sellerAgents.map((agent) => {
                const isSelected = selectedAgents.includes(agent.id);
                return (
                  <div
                    key={agent.id}
                    onClick={() => toggleAgent(agent.id)}
                    className={`cursor-pointer border-2 transition-all p-5 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:-translate-y-0.5 hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] ${
                      isSelected ? "border-black bg-black text-white" : "border-black hover:bg-gray-50"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className={`text-xs font-black uppercase tracking-widest ${isSelected ? 'text-white' : 'text-black'}`}>{agent.name}</span>
                      <div className={`flex h-6 w-6 items-center justify-center border-2 ${
                        isSelected ? "border-white bg-white text-black" : "border-gray-200"
                      }`}>
                        {isSelected && <Check size={16} strokeWidth={4} />}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            {sellerAgents.length === 0 ? (
              <div className="border-2 border-dashed border-black p-5 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                No seller agents found in the backend yet. Seller agent creation is intentionally deferred from this UI.
              </div>
            ) : null}
          </div>
        )}

        {agentType === "seller" ? (
          <div className="border-2 border-dashed border-black bg-gray-50 p-6 text-center">
            <p className="text-xs font-black uppercase tracking-[0.15em] text-black">Seller builder deferred</p>
            <p className="mt-3 text-[10px] font-bold uppercase tracking-widest text-gray-500">
              Seller agent creation is not connected here. You said you will handle it later.
            </p>
          </div>
        ) : null}

        {error ? (
          <div className="border-2 border-red-500 bg-red-50 p-4 text-[10px] font-bold uppercase tracking-widest text-red-700">
            {error}
          </div>
        ) : null}

        <div className="pt-8">
          <button
            type="submit"
            disabled={isSubmitting || agentType === "seller" || !currentUser || !health?.circle_enabled}
            className="w-full bg-black py-5 text-[10px] font-black uppercase tracking-[0.2em] text-white transition-colors hover:bg-gray-800"
          >
            {isSubmitting ? "Building Agent..." : `Build ${agentType === "buyer" ? "Buyer" : "Seller"} Agent`}
          </button>
        </div>
      </form>
    </div>
  );
}
