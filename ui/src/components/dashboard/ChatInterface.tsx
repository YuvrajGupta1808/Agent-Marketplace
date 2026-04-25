import { Send } from "lucide-react";
import React, { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamMarketplace } from "../../lib/api";
import type { AgentRecord, RunResponse, StreamEvent } from "../../lib/api";
import type { TransactionHistoryRef } from "./TransactionHistory";
import { ThinkingNode } from "./ThinkingNode";

interface ChatInterfaceProps {
  buyer: AgentRecord | null;
  buyerAgents: AgentRecord[];
  sellerAgents: AgentRecord[];
  selectedSellerId: string | null;
  onSelectBuyerAgent: (buyerId: string) => void;
  setSelectedSellerId: (sellerId: string) => void;
  onRunWorkflow: (goal: string) => Promise<RunResponse>;
  isCircleEnabled: boolean;
  transactionHistoryRef?: React.RefObject<TransactionHistoryRef>;
}

interface Message {
  role: "user" | "agent";
  content: string;
  id: string;
}

function getDisplayAnswer(result: RunResponse): string {
  const primary = [result.final_answer, result.running_answer]
    .find((value) => typeof value === "string" && value.trim().length > 0)
    ?.trim();
  if (primary) return primary;

  if (result.results.length > 0) {
    const top = result.results[0];
    if (top.summary?.trim()) return top.summary.trim();
    if (top.title?.trim()) return `Completed: ${top.title.trim()}`;
  }

  if (result.pending_question?.trim()) {
    return `Need clarification: ${result.pending_question.trim()}`;
  }

  return "Workflow completed, but no final answer was produced.";
}

function normalizeChatContent(content: string): string {
  if (!content) return "";

  let normalized = content.trim();

  // Convert escaped newlines when backend returns JSON-stringified markdown.
  if (normalized.includes("\\n")) {
    normalized = normalized.replace(/\\n/g, "\n");
  }

  // Remove wrapping markdown code fences often emitted by models.
  normalized = normalized
    .replace(/^```(?:markdown|md|text)?\s*\n/i, "")
    .replace(/\n```$/i, "")
    .trim();

  return normalized;
}

function getBuyerUseCaseMessage(buyer: AgentRecord | null): string {
  if (!buyer) {
    return "Select or create a buyer agent to begin.";
  }

  const metadataUseCase =
    (typeof buyer.metadata.use_case === "string" && buyer.metadata.use_case.trim()) ||
    (typeof buyer.metadata.description === "string" && buyer.metadata.description.trim()) ||
    "";

  const useCase = buyer.description?.trim() || metadataUseCase;
  if (useCase) return useCase;

  return `${buyer.name} is ready. Choose a seller, then send a research request.`;
}

export function ChatInterface({
  buyer,
  buyerAgents,
  sellerAgents,
  selectedSellerId,
  onSelectBuyerAgent,
  setSelectedSellerId,
  onRunWorkflow,
  isCircleEnabled,
  transactionHistoryRef,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([
    { role: "agent", content: getBuyerUseCaseMessage(buyer), id: "init" }
  ]);
  const [input, setInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [streamEvents, setStreamEvents] = useState<StreamEvent[]>([]);
  const [currentUserMsgId, setCurrentUserMsgId] = useState<string | null>(null);

  const connectedSellerIds = Array.isArray(buyer?.metadata.connected_seller_ids)
    ? (buyer?.metadata.connected_seller_ids as string[])
    : sellerAgents.map((seller) => seller.id);
  const availableSellers = sellerAgents.filter((seller) => connectedSellerIds.includes(seller.id));

  useEffect(() => {
    setMessages([{ role: "agent", content: getBuyerUseCaseMessage(buyer), id: "init" }]);
    setStreamEvents([]);
    setCurrentUserMsgId(null);
  }, [buyer?.id, buyer?.name, buyer?.description, buyer?.metadata]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    if (!buyer) {
      setMessages((prev) => [...prev, { role: "agent", content: "Create a buyer agent before sending workflow commands.", id: `msg-${Date.now()}` }]);
      return;
    }
    if (!isCircleEnabled) {
      setMessages((prev) => [...prev, { role: "agent", content: "Circle is not configured on the backend, so real wallet execution is blocked.", id: `msg-${Date.now()}` }]);
      return;
    }
    if (!selectedSellerId) {
      setMessages((prev) => [...prev, { role: "agent", content: "Select a seller agent before running the workflow.", id: `msg-${Date.now()}` }]);
      return;
    }

    const goal = input;
    const userMsgId = `user-${Date.now()}`;
    const answerMsgId = `answer-${Date.now()}`;

    setMessages(prev => [...prev, { role: "user", content: goal, id: userMsgId }]);
    setInput("");
    setCurrentUserMsgId(userMsgId);
    setIsSubmitting(true);
    setStreamEvents([]); // Clear old events for this new request

    try {
      const events: StreamEvent[] = [];
      let answer = "";

      for await (const event of streamMarketplace({
        userGoal: goal,
        buyerAgentId: buyer.id,
        sellerAgentId: selectedSellerId,
      })) {
        events.push(event);
        setStreamEvents([...events]);

        // Capture final answer from stream
        if (event.type === "final_answer") {
          answer = event.answer || "";
        }

        // Handle real-time transaction creation
        if (event.type === "transaction_created" || event.event_type === "transaction_created") {
          const txData = event;
          if (transactionHistoryRef?.current) {
            transactionHistoryRef.current.addRealtimeTransaction({
              circle_transaction_id: txData.circle_transaction_id || "",
              amount_usdc: txData.amount_usdc || "0",
              tx_hash: txData.tx_hash || null,
              task_id: txData.task_id || "unknown",
              buyer_agent_id: txData.buyer_agent_id || "",
              state: txData.tx_hash ? "COMPLETE" : "INITIATED",
              created_at: new Date().toISOString(),
            });
            console.log("📊 Real-time transaction added:", txData.circle_transaction_id?.slice(0, 16));
          }
        }
      }

      // Add the final answer to messages (use actual answer from backend)
      const finalAnswer = answer || "Research completed successfully.";
      setMessages(prev => [...prev, { role: "agent", content: finalAnswer, id: answerMsgId }]);
      // Keep streamEvents for persistent thinking section display
    } catch (error) {
      const message = error instanceof Error ? error.message : "Workflow failed.";
      setMessages(prev => [...prev, { role: "agent", content: `❌ Error: ${message}`, id: answerMsgId }]);
      // Keep streamEvents even on error for debugging
    } finally {
      setIsSubmitting(false);
      setCurrentUserMsgId(null);
    }
  };

  return (
    <div className="flex h-full flex-col bg-gray-50/50">
      {/* Header */}
      <div className="border-b-4 border-black bg-white px-6 py-4 flex items-center gap-3">
        <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse z-10"></div>
        <span className="text-[10px] font-black uppercase tracking-[0.2em] text-black">
          Chat:
        </span>
        {buyerAgents.length > 0 ? (
          <select
            aria-label="Select buyer agent"
            value={buyer?.id ?? ""}
            onChange={(event) => onSelectBuyerAgent(event.target.value)}
            className="max-w-[280px] border-2 border-black bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.16em] text-black outline-none"
          >
            {buyerAgents.map((buyerAgent) => (
              <option key={buyerAgent.id} value={buyerAgent.id}>
                {buyerAgent.name}
              </option>
            ))}
          </select>
        ) : (
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">
            No Buyer Agent
          </span>
        )}
      </div>

      {/* Messages - Only this scrolls */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 flex flex-col justify-end">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex w-full flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}>
            {/* Main Message */}
            <div className={`p-4 rounded-none text-xs font-semibold max-w-[85%] border-2 leading-relaxed whitespace-pre-wrap wrap-break-word shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] ${msg.role === "user" ? "bg-black text-white border-black" : "bg-white text-gray-800 border-black"}`}>
              {msg.role === "user" ? (
                msg.content
              ) : (
                <div className="space-y-2 leading-relaxed">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h1: ({ children }) => <h1 className="text-sm font-black">{children}</h1>,
                      h2: ({ children }) => <h2 className="text-xs font-black">{children}</h2>,
                      h3: ({ children }) => <h3 className="text-xs font-bold">{children}</h3>,
                      p: ({ children }) => <p className="text-xs font-medium">{children}</p>,
                      ul: ({ children }) => <ul className="list-disc pl-5 text-xs font-medium space-y-1">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal pl-5 text-xs font-medium space-y-1">{children}</ol>,
                      li: ({ children }) => <li>{children}</li>,
                      code: ({ children }) => (
                        <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-[11px] text-black">{children}</code>
                      ),
                      pre: ({ children }) => (
                        <pre className="overflow-x-auto border border-gray-300 bg-gray-50 p-3 font-mono text-[11px]">{children}</pre>
                      ),
                      blockquote: ({ children }) => (
                        <blockquote className="border-l-2 border-gray-400 pl-3 italic text-gray-700">{children}</blockquote>
                      ),
                      a: ({ href, children }) => (
                        <a
                          href={href}
                          target="_blank"
                          rel="noreferrer"
                          className="underline underline-offset-2"
                        >
                          {children}
                        </a>
                      ),
                    }}
                  >
                    {normalizeChatContent(msg.content)}
                  </ReactMarkdown>
                </div>
              )}
            </div>
            <span className="mt-2 text-[9px] font-black uppercase tracking-widest text-gray-400">
              {msg.role === "user" ? "User" : "System Node"}
            </span>
          </div>
        ))}

        {/* Show thinking section during execution */}
        {isSubmitting && currentUserMsgId && (
          <div className="flex w-full flex-col items-start">
            <ThinkingNode isLoading={true} events={streamEvents} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-6 bg-white border-t border-gray-100">
        <form onSubmit={handleSend} className="relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="COMMAND AGENT..."
            className="w-full bg-white border-2 border-black py-4 pl-6 pr-14 text-xs font-bold tracking-widest rounded-none focus:outline-none focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-all"
          />
          <button
            type="submit"
            disabled={isSubmitting}
            className="absolute right-2 top-2 bg-black text-white w-10 h-10 rounded-none flex items-center justify-center transition-transform hover:-translate-y-0.5 active:translate-y-0"
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
}
