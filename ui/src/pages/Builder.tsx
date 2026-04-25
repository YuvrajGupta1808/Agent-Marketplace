import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Check, ArrowRight, Wrench, Brain, CreditCard, ExternalLink } from "lucide-react";
import { useAppState } from "../lib/app-state";
import type { BuiltInTool, LlmProviderOption } from "../lib/api";
import { listLlmProviders, listSellerTools } from "../lib/api";
import { getDefaultSellerCategory, getToolCategory, isSellerPublished, SELLER_CATEGORIES } from "../lib/seller";

export function Builder() {
  const { createBuyerAgent, createSellerAgent, currentUser, health, sellerAgents, selectedSellerId } = useAppState();
  const [agentType, setAgentType] = useState<"buyer" | "seller">("buyer");
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [isBuilt, setIsBuilt] = useState(false);
  const [builtAgentId, setBuiltAgentId] = useState("");
  const [builtAgentRole, setBuiltAgentRole] = useState<"buyer" | "seller">("buyer");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [prompt, setPrompt] = useState("");
  const [category, setCategory] = useState(getDefaultSellerCategory());
  const [priceUsdc, setPriceUsdc] = useState("0.010000");
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [toolOptions, setToolOptions] = useState<BuiltInTool[]>([]);
  const [llmProviders, setLlmProviders] = useState<LlmProviderOption[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState("aimlapi");
  const [selectedModelId, setSelectedModelId] = useState("");
  const [maxPaymentUsdc, setMaxPaymentUsdc] = useState("0.200000");
  const [toolsError, setToolsError] = useState<string | null>(null);
  const [providersError, setProvidersError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const publishedSellerAgents = useMemo(
    () => sellerAgents.filter(isSellerPublished),
    [sellerAgents],
  );
  const publishedSellerIds = useMemo(
    () => new Set(publishedSellerAgents.map((seller) => seller.id)),
    [publishedSellerAgents],
  );
  const selectedProvider = useMemo(
    () => llmProviders.find((provider) => provider.id === selectedProviderId) ?? llmProviders[0] ?? null,
    [llmProviders, selectedProviderId],
  );
  const selectedModel = useMemo(
    () => selectedProvider?.models.find((model) => model.id === selectedModelId) ?? selectedProvider?.models[0] ?? null,
    [selectedModelId, selectedProvider],
  );
  const visibleCategoryTools = useMemo(
    () => [...toolOptions]
      .filter((tool) => getToolCategory(tool.id) === category)
      .sort((a, b) => a.name.localeCompare(b.name)),
    [category, toolOptions],
  );

  useEffect(() => {
    if (selectedSellerId && publishedSellerIds.has(selectedSellerId)) {
      setSelectedAgents((prev) => (prev.includes(selectedSellerId) ? prev : [...prev, selectedSellerId]));
    }
  }, [publishedSellerIds, selectedSellerId]);

  useEffect(() => {
    let cancelled = false;
    listSellerTools()
      .then((tools) => {
        if (cancelled) return;
        setToolOptions(tools);
      })
      .catch((err) => {
        if (!cancelled) {
          setToolsError(err instanceof Error ? err.message : "Unable to load tools.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    listLlmProviders()
      .then((providers) => {
        if (cancelled) return;
        setLlmProviders(providers);
        const preferredProvider = providers.find((provider) => provider.id === "aimlapi" && provider.enabled)
          ?? providers.find((provider) => provider.enabled)
          ?? providers[0];
        if (preferredProvider) {
          setSelectedProviderId(preferredProvider.id);
          const preferredModel = preferredProvider.models[0];
          if (preferredModel) {
            setSelectedModelId(preferredModel.id);
            setMaxPaymentUsdc(preferredModel.payment_floor_usdc);
          }
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setProvidersError(err instanceof Error ? err.message : "Unable to load model providers.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedProvider) return;
    if (!selectedModel || !selectedProvider.models.some((model) => model.id === selectedModel.id)) {
      const nextModel = selectedProvider.models[0];
      if (nextModel) {
        setSelectedModelId(nextModel.id);
        setMaxPaymentUsdc(nextModel.payment_floor_usdc);
      }
    }
  }, [selectedModel, selectedProvider]);

  const toggleAgent = (id: string) => {
    setSelectedAgents((prev) =>
      prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]
    );
  };

  const toggleTool = (id: string) => {
    setSelectedTools((prev) => (prev.includes(id) ? prev.filter((toolId) => toolId !== id) : [...prev, id]));
  };

  const handleBuild = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!currentUser) {
      setError("Register or log in before building an agent.");
      return;
    }
    if (!health?.circle_enabled) {
      setError("Circle is not configured on the backend. Real Circle wallets are required.");
      return;
    }
    if (agentType === "seller" && selectedTools.length === 0) {
      setError("Select at least one built-in tool for this seller agent.");
      return;
    }
    if (agentType === "buyer" && (!selectedProvider || !selectedProvider.enabled || !selectedModel)) {
      setError(selectedProvider?.disabled_reason || "Select an enabled buyer model provider.");
      return;
    }

    setIsSubmitting(true);
    try {
      const agent = agentType === "buyer"
        ? await createBuyerAgent({
            name,
            description,
            prompt,
            connectedSellerIds: selectedAgents.filter((sellerId) => publishedSellerIds.has(sellerId)),
            llmConfig: {
              provider: selectedProvider.id,
              model: selectedModel.id,
            },
            paymentConfig: {
              maxPaymentUsdc,
            },
          })
        : await createSellerAgent({
            name,
            description,
            prompt,
            category,
            priceUsdc,
            builtInTools: selectedTools,
          });
      setBuiltAgentId(agent.id);
      setBuiltAgentRole(agentType);
      setIsBuilt(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create agent.");
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
        <p className="mt-4 text-xs font-bold uppercase tracking-widest text-gray-500">
          {builtAgentRole === "seller"
            ? "Your seller draft is ready for a test run before publishing."
            : "Your buyer agent is now ready to use with Circle-backed payments."}
        </p>
        <p className="mt-4 text-[10px] font-mono font-bold uppercase tracking-widest text-black">ID: {builtAgentId}</p>
        <div className="mt-10 w-full max-w-xs">
          <Link
            to={builtAgentRole === "seller" ? "/seller-test" : "/dashboard"}
            className="inline-flex items-center justify-center w-full gap-3 bg-black py-4 text-[10px] font-black uppercase tracking-[0.2em] text-white transition-colors hover:bg-gray-800 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
          >
            {builtAgentRole === "seller" ? "Test Seller" : "Go to Dashboard"} <ArrowRight size={16} />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-8 py-16 w-full">
      <div className="mb-12 text-center">
        <h1 className="text-4xl font-black uppercase tracking-tighter text-black">Agent Builder</h1>
        <p className="mt-4 text-xs font-bold uppercase tracking-widest text-gray-500">Build buyer agents and hosted seller agents against the live backend.</p>
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
            Agent creation is blocked until Circle credentials are configured on the backend.
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
              <div className="mb-4 flex items-center gap-3">
                <Brain size={16} />
                <h3 className="text-sm font-black uppercase tracking-[0.1em] text-black">Buyer Model Provider</h3>
              </div>
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                <div>
                  <label className="mb-3 block text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Provider</label>
                  <select
                    value={selectedProviderId}
                    onChange={(event) => {
                      const nextProvider = llmProviders.find((provider) => provider.id === event.target.value);
                      setSelectedProviderId(event.target.value);
                      const nextModel = nextProvider?.models[0];
                      if (nextModel) {
                        setSelectedModelId(nextModel.id);
                        setMaxPaymentUsdc(nextModel.payment_floor_usdc);
                      }
                    }}
                    className="w-full bg-white border-2 border-black px-4 py-3 text-xs font-bold uppercase tracking-widest outline-none transition-all focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
                  >
                    {llmProviders.map((provider) => (
                      <option key={provider.id} value={provider.id}>
                        {provider.name}{provider.enabled ? "" : ` (${provider.api_key_env} missing)`}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-3 block text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Model</label>
                  <select
                    value={selectedModel?.id ?? ""}
                    onChange={(event) => {
                      setSelectedModelId(event.target.value);
                      const nextModel = selectedProvider?.models.find((model) => model.id === event.target.value);
                      if (nextModel) {
                        setMaxPaymentUsdc(nextModel.payment_floor_usdc);
                      }
                    }}
                    disabled={!selectedProvider?.enabled}
                    className="w-full bg-white border-2 border-black px-4 py-3 text-xs font-bold tracking-widest outline-none transition-all disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400 focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
                  >
                    {(selectedProvider?.models ?? []).map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.name} / {model.tier}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {selectedProvider && selectedModel ? (
                <div className="mt-5 grid grid-cols-1 gap-4 border-2 border-black bg-gray-50 p-5 sm:grid-cols-[1fr_auto]">
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-[0.16em] text-black">
                      {selectedProvider.name} / {selectedModel.name}
                    </p>
                    <p className="mt-2 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                      {selectedProvider.enabled ? selectedModel.description : selectedProvider.disabled_reason}
                    </p>
                    <a
                      href={selectedProvider.docs_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-3 inline-flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.16em] text-black underline underline-offset-4"
                    >
                      Provider Docs <ExternalLink size={12} />
                    </a>
                  </div>
                  <div className="flex items-center gap-3 text-[10px] font-black uppercase tracking-[0.16em] text-black">
                    <CreditCard size={16} />
                    Floor {selectedModel.payment_floor_usdc} USDC
                  </div>
                </div>
              ) : providersError ? (
                <div className="mt-4 border-2 border-red-500 bg-red-50 p-4 text-[10px] font-bold uppercase tracking-widest text-red-700">
                  {providersError}
                </div>
              ) : (
                <div className="mt-4 border-2 border-dashed border-black p-5 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                  Loading model providers...
                </div>
              )}
            </div>

            <div>
              <label className="mb-3 block text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Max Payment Per Task</label>
              <input
                required
                type="number"
                min={selectedModel?.payment_floor_usdc ?? "0.000001"}
                step="0.000001"
                value={maxPaymentUsdc}
                onChange={(event) => setMaxPaymentUsdc(event.target.value)}
                className="w-full bg-white border-2 border-black px-4 py-3 text-xs font-mono font-bold tracking-widest outline-none transition-all focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
              />
              <p className="mt-2 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                Buyer runs will refuse seller offers above this USDC limit.
              </p>
            </div>

            <div>
              <h3 className="text-sm font-black uppercase tracking-[0.1em] text-black">Connect Seller Agents</h3>
              <p className="mt-1 text-[10px] font-bold uppercase tracking-widest text-gray-500">Select the seller agents this buyer agent has access to.</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {publishedSellerAgents.map((agent) => {
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
            {publishedSellerAgents.length === 0 ? (
              <div className="border-2 border-dashed border-black p-5 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                No published seller agents found in the backend yet.
              </div>
            ) : null}
          </div>
        )}

        {agentType === "seller" ? (
          <div className="space-y-8 pt-8 border-t-2 border-black border-dashed">
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div>
                <label className="mb-3 block text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Category</label>
                <select
                  required
                  value={category}
                  onChange={(event) => setCategory(event.target.value)}
                  className="w-full bg-white border-2 border-black px-4 py-3 text-xs font-bold tracking-widest outline-none transition-all focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
                >
                  {SELLER_CATEGORIES.map((categoryOption) => (
                    <option key={categoryOption} value={categoryOption}>
                      {categoryOption}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-3 block text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Price Per Run</label>
                <input
                  required
                  type="number"
                  min="0.000001"
                  step="0.000001"
                  value={priceUsdc}
                  onChange={(event) => setPriceUsdc(event.target.value)}
                  className="w-full bg-white border-2 border-black px-4 py-3 text-xs font-mono font-bold tracking-widest outline-none transition-all focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
                />
              </div>
            </div>

            <div>
              <div className="mb-4 flex items-center gap-3">
                <Wrench size={16} />
                <h3 className="text-sm font-black uppercase tracking-[0.1em] text-black">Built-In Tools</h3>
              </div>
              <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                Selected tools: {selectedTools.length}
              </p>
              <p className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">{category}</p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {visibleCategoryTools.map((tool) => {
                  const selected = selectedTools.includes(tool.id);
                  return (
                    <button
                      key={tool.id}
                      type="button"
                      disabled={!tool.enabled}
                      onClick={() => toggleTool(tool.id)}
                      className={`border-2 border-black p-4 text-left transition-all ${
                        selected ? "bg-black text-white" : "bg-white text-black hover:bg-gray-50"
                      } ${!tool.enabled ? "cursor-not-allowed opacity-50" : "cursor-pointer shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"}`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className={`text-[10px] font-black uppercase tracking-[0.16em] ${selected ? "text-white" : "text-black"}`}>
                            {tool.name}
                          </p>
                          <p className={`mt-2 text-[10px] font-bold uppercase tracking-widest ${selected ? "text-gray-300" : "text-gray-500"}`}>
                            {tool.description}
                          </p>
                        </div>
                        <div className={`flex h-6 w-6 shrink-0 items-center justify-center border-2 ${
                          selected ? "border-white bg-white text-black" : "border-black"
                        }`}>
                          {selected && <Check size={16} strokeWidth={4} />}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
              {visibleCategoryTools.length === 0 ? (
                <div className="mt-4 border-2 border-dashed border-black p-5 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                  No tools available for this category.
                </div>
              ) : null}
              {toolsError ? (
                <div className="mt-4 border-2 border-red-500 bg-red-50 p-4 text-[10px] font-bold uppercase tracking-widest text-red-700">
                  {toolsError}
                </div>
              ) : null}
              {toolOptions.length === 0 && !toolsError ? (
                <div className="border-2 border-dashed border-black p-5 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                  Loading seller tools...
                </div>
              ) : null}
            </div>
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
            disabled={isSubmitting || !currentUser || !health?.circle_enabled}
            className="w-full bg-black py-5 text-[10px] font-black uppercase tracking-[0.2em] text-white transition-colors hover:bg-gray-800"
          >
            {isSubmitting ? "Building Agent..." : `Build ${agentType === "buyer" ? "Buyer" : "Seller"} Agent`}
          </button>
        </div>
      </form>
    </div>
  );
}
