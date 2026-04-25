import { AlertCircle, Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { BuiltInTool } from "../lib/api";
import { listSellerTools, testResearch } from "../lib/api";
import { useAppState } from "../lib/app-state";
import { formatToolNames, getSellerPrice, getSellerStatus, getSellerToolIds } from "../lib/seller";

function normalizeMarkdown(text: string) {
  if (!text) return "";

  let normalized = text.trim();
  if (normalized.includes("\\n")) {
    normalized = normalized.replace(/\\n/g, "\n");
  }

  return normalized
    .replace(/^```(?:markdown|md|text)?\s*\n/i, "")
    .replace(/\n```$/i, "")
    .trim();
}

export function SellerTest() {
  const { currentUser, sellerAgents, isReady, selectedSellerId, setSelectedSellerId, setSellerStatus } = useAppState();
  const [query, setQuery] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [result, setResult] = useState<unknown | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [toolOptions, setToolOptions] = useState<BuiltInTool[]>([]);

  const ownedSellerAgents = useMemo(
    () => (currentUser ? sellerAgents.filter((agent) => agent.user_id === currentUser.id) : []),
    [currentUser, sellerAgents],
  );
  const selectedSeller = ownedSellerAgents.find((agent) => agent.id === selectedAgentId) ?? null;
  const selectedSellerStatus = selectedSeller ? getSellerStatus(selectedSeller) : "draft";
  const resultRecord = useMemo(
    () => (result && typeof result === "object" ? (result as Record<string, unknown>) : null),
    [result],
  );
  const outputPreview = useMemo(() => {
    if (!resultRecord) return "";
    if (typeof resultRecord.output === "string") return resultRecord.output;
    const nestedResult = resultRecord.result;
    if (nestedResult && typeof nestedResult === "object") {
      const nestedRecord = nestedResult as Record<string, unknown>;
      if (typeof nestedRecord.summary === "string") return nestedRecord.summary;
      if (typeof nestedRecord.output === "string") return nestedRecord.output;
    }
    return "";
  }, [resultRecord]);
  const rawResultJson = useMemo(() => {
    if (result == null) return "";
    try {
      return JSON.stringify(result, null, 2);
    } catch {
      return String(result);
    }
  }, [result]);

  useEffect(() => {
    let cancelled = false;
    listSellerTools()
      .then((tools) => {
        if (!cancelled) setToolOptions(tools);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load seller tools.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!currentUser) {
      setLoadError("Please log in to test seller agents.");
      return;
    }
    if (ownedSellerAgents.length === 0 && isReady) {
      setLoadError("No seller agents available. Please create one first.");
    } else if (ownedSellerAgents.length > 0 && (!selectedAgentId || !ownedSellerAgents.some((agent) => agent.id === selectedAgentId))) {
      const nextSellerId =
        (selectedSellerId && ownedSellerAgents.some((agent) => agent.id === selectedSellerId) && selectedSellerId) ||
        ownedSellerAgents[0].id;
      setSelectedAgentId(nextSellerId);
      setSelectedSellerId(nextSellerId);
      setLoadError(null);
    }
  }, [currentUser, ownedSellerAgents, selectedAgentId, selectedSellerId, setSelectedSellerId, isReady]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentUser) {
      setError("Please log in to test seller agents.");
      return;
    }
    if (!query.trim() || !selectedAgentId) {
      setError("Please enter a query and select an agent.");
      return;
    }

    setError(null);
    setResult(null);
    setIsLoading(true);

    try {
      const res = await testResearch({
        query: query.trim(),
        seller_agent_id: selectedAgentId,
        user_id: currentUser.id,
      });
      setResult(res);
    } catch (err) {
      console.error("Research error:", err);
      setError(err instanceof Error ? err.message : "Research failed");
    } finally {
      setIsLoading(false);
    }
  };

  const handlePublish = async () => {
    if (!selectedSeller) return;
    setError(null);
    setIsPublishing(true);
    try {
      await setSellerStatus(selectedSeller.id, "published");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to publish seller agent.");
    } finally {
      setIsPublishing(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-8 py-16 w-full">
      <div className="mb-16">
        <h1 className="text-4xl font-black uppercase tracking-tighter text-black">Seller Test</h1>
        <p className="mt-2 text-xs font-bold uppercase tracking-widest text-gray-500">
          Test seller agent research without payment.
        </p>
      </div>

      <div className="flex flex-col gap-8">
        {/* Form */}
        <div className="flex flex-col max-w-2xl w-full mx-auto">
          {loadError ? (
            <div className="border-2 border-red-500 bg-red-50 p-8 text-red-700 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
              <div className="flex gap-3">
                <AlertCircle size={20} className="shrink-0" />
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] mb-2">Loading Error</p>
                  <p className="text-xs">{loadError}</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="border-2 border-black bg-white p-8 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
              <form onSubmit={handleSubmit} className="flex flex-col gap-6">
                <div>
                  <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-700 block mb-2">
                    Query
                  </label>
                  <textarea
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Enter your research query..."
                    className="w-full border-2 border-black py-3 px-4 text-xs font-bold tracking-widest outline-none focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] resize-none"
                    rows={6}
                  />
                </div>

                <div>
                  <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-700 block mb-2">
                    Seller Agent
                  </label>
                  {!isReady ? (
                    <div className="w-full border-2 border-black py-3 px-4 text-xs font-bold uppercase tracking-widest flex items-center justify-center gap-2 bg-gray-50">
                      <Loader2 size={14} className="animate-spin" />
                      Loading agents...
                    </div>
                  ) : (
                    <select
                      value={selectedAgentId}
                      onChange={(e) => {
                        setSelectedAgentId(e.target.value);
                        setSelectedSellerId(e.target.value);
                        setResult(null);
                      }}
                      className="w-full border-2 border-black py-3 px-4 text-xs font-bold uppercase tracking-widest outline-none focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
                    >
                      {ownedSellerAgents.length === 0 ? (
                        <option disabled>No agents available</option>
                      ) : (
                        ownedSellerAgents.map((agent) => (
                          <option key={agent.id} value={agent.id}>
                            {agent.name}
                          </option>
                        ))
                      )}
                    </select>
                  )}
                </div>

                {selectedSeller ? (
                  <div className="grid grid-cols-1 gap-3 border-2 border-black bg-gray-50 p-4 text-[10px] font-black uppercase tracking-[0.16em] text-black sm:grid-cols-3">
                    <div>Status: {selectedSellerStatus}</div>
                    <div>Price: {getSellerPrice(selectedSeller)} USDC</div>
                    <div>Tools: {formatToolNames(getSellerToolIds(selectedSeller), toolOptions)}</div>
                  </div>
                ) : null}

                <button
                  type="submit"
                  disabled={isLoading || !query.trim() || !selectedAgentId || !isReady || !currentUser}
                  className="mt-auto bg-black text-white text-[10px] font-black uppercase tracking-[0.2em] py-4 flex items-center justify-center gap-2 hover:bg-gray-800 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  {isLoading ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      RUNNING...
                    </>
                  ) : (
                    "RUN TASK"
                  )}
                </button>
                {result && selectedSellerStatus === "draft" ? (
                  <button
                    type="button"
                    onClick={handlePublish}
                    disabled={isPublishing}
                    className="border-2 border-black bg-white py-4 text-[10px] font-black uppercase tracking-[0.2em] text-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isPublishing ? "PUBLISHING..." : "PUBLISH SELLER"}
                  </button>
                ) : null}
              </form>
            </div>
          )}
        </div>

        {/* Results */}
        <div className="flex flex-col max-w-2xl w-full mx-auto">
          {error ? (
            <div className="border-2 border-red-500 bg-red-50 p-8 text-red-700 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
              <div className="flex gap-3">
                <AlertCircle size={20} className="shrink-0" />
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] mb-2">Error</p>
                  <p className="text-xs">{error}</p>
                </div>
              </div>
            </div>
          ) : result ? (
            <div className="border-2 border-black bg-white p-8 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
              <h2 className="text-xl font-bold uppercase tracking-tight text-black mb-6">Task Output</h2>
              {outputPreview ? (
                <div className="prose prose-sm max-w-none text-gray-700">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h1: ({ children }) => <h1 className="text-base font-black text-black">{children}</h1>,
                      h2: ({ children }) => <h2 className="text-sm font-black text-black">{children}</h2>,
                      h3: ({ children }) => <h3 className="text-sm font-bold text-black">{children}</h3>,
                      p: ({ children }) => <p className="text-xs font-medium leading-relaxed">{children}</p>,
                      ul: ({ children }) => <ul className="list-disc pl-5 text-xs font-medium space-y-1">{children}</ul>,
                      ol: ({ children }) => (
                        <ol className="list-decimal pl-5 text-xs font-medium space-y-1">{children}</ol>
                      ),
                      li: ({ children }) => <li>{children}</li>,
                      strong: ({ children }) => <strong className="font-black text-black">{children}</strong>,
                      code: ({ children }) => (
                        <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-[11px] text-black">{children}</code>
                      ),
                      pre: ({ children }) => (
                        <pre className="overflow-x-auto border border-gray-300 bg-gray-50 p-3 font-mono text-[11px]">
                          {children}
                        </pre>
                      ),
                      blockquote: ({ children }) => (
                        <blockquote className="border-l-2 border-gray-400 pl-3 italic text-gray-700">{children}</blockquote>
                      ),
                    }}
                  >
                    {normalizeMarkdown(outputPreview)}
                  </ReactMarkdown>
                </div>
              ) : null}
              <div className={outputPreview ? "mt-6" : ""}>
                <p className="mb-2 text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Raw Response</p>
                <pre className="overflow-x-auto border border-gray-300 bg-gray-50 p-3 font-mono text-[11px] text-black">
                  {rawResultJson}
                </pre>
              </div>
            </div>
          ) : (
            <div className="border-2 border-dashed border-gray-300 bg-gray-50 p-8 flex items-center justify-center min-h-[200px]">
              <p className="text-xs font-bold uppercase tracking-widest text-gray-400 text-center">
                Run a task to see output here
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
