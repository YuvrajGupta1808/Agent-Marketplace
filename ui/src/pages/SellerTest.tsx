import { useState, useEffect } from "react";
import { useAppState } from "../lib/app-state";
import { testResearch, TestResearchResult } from "../lib/api";
import { AlertCircle, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
  const { currentUser, sellerAgents, isReady } = useAppState();
  const [query, setQuery] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<TestResearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!currentUser) {
      setLoadError("Please log in to test seller agents.");
      return;
    }
    if (sellerAgents.length === 0 && isReady) {
      setLoadError("No seller agents available. Please create one first.");
    } else if (sellerAgents.length > 0 && !selectedAgentId) {
      setSelectedAgentId(sellerAgents[0].id);
      setLoadError(null);
    }
  }, [currentUser, sellerAgents, selectedAgentId, isReady]);

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

      // Simple response: just has "output" text
      const output = res.output || JSON.stringify(res);

      if (!output) {
        throw new Error("No output returned from research");
      }

      const normalizedResult: TestResearchResult = {
        task_id: res.task_id || "test-task",
        title: `Research: ${query.trim().slice(0, 50)}`,
        summary: output,
        bullets: [],
        citations: [],
      };

      setResult(normalizedResult);
    } catch (err) {
      console.error("Research error:", err);
      setError(err instanceof Error ? err.message : "Research failed");
    } finally {
      setIsLoading(false);
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
                      onChange={(e) => setSelectedAgentId(e.target.value)}
                      className="w-full border-2 border-black py-3 px-4 text-xs font-bold uppercase tracking-widest outline-none focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
                    >
                      {sellerAgents.length === 0 ? (
                        <option disabled>No agents available</option>
                      ) : (
                        sellerAgents.map((agent) => (
                          <option key={agent.id} value={agent.id}>
                            {agent.name}
                          </option>
                        ))
                      )}
                    </select>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={isLoading || !query.trim() || !selectedAgentId || !isReady || !currentUser}
                  className="mt-auto bg-black text-white text-[10px] font-black uppercase tracking-[0.2em] py-4 flex items-center justify-center gap-2 hover:bg-gray-800 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  {isLoading ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      RESEARCHING...
                    </>
                  ) : (
                    "RUN RESEARCH"
                  )}
                </button>
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
              <h2 className="text-xl font-bold uppercase tracking-tight text-black mb-6">{result.title}</h2>
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
                  {normalizeMarkdown(result.summary)}
                </ReactMarkdown>
              </div>
            </div>
          ) : (
            <div className="border-2 border-dashed border-gray-300 bg-gray-50 p-8 flex items-center justify-center min-h-[200px]">
              <p className="text-xs font-bold uppercase tracking-widest text-gray-400 text-center">
                Run a research query to see results here
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
