import { Send, ChevronDown, ChevronUp } from "lucide-react";
import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AgentRecord, RunResponse } from "../../lib/api";

interface ChatInterfaceProps {
  buyer: AgentRecord | null;
  sellerAgents: AgentRecord[];
  selectedSellerId: string | null;
  setSelectedSellerId: (sellerId: string) => void;
  onRunWorkflow: (goal: string) => Promise<RunResponse>;
  isCircleEnabled: boolean;
}

interface Message {
  role: "user" | "agent";
  content: string;
  thinking?: string;
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

export function ChatInterface({
  buyer,
  sellerAgents,
  selectedSellerId,
  setSelectedSellerId,
  onRunWorkflow,
  isCircleEnabled,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([
    { role: "agent", content: "Backend workflow ready. Choose a seller, then send a research request.", id: "init" }
  ]);
  const [input, setInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [expandedThinking, setExpandedThinking] = useState<Set<string>>(new Set());


  const connectedSellerIds = Array.isArray(buyer?.metadata.connected_seller_ids)
    ? (buyer?.metadata.connected_seller_ids as string[])
    : sellerAgents.map((seller) => seller.id);
  const availableSellers = sellerAgents.filter((seller) => connectedSellerIds.includes(seller.id));

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
    setMessages(prev => [...prev, { role: "user", content: goal, id: userMsgId }]);
    setInput("");
    setIsSubmitting(true);

    try {
      const result = await onRunWorkflow(goal);
      const finalAnswer = getDisplayAnswer(result);
      const msgId = `msg-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: finalAnswer, id: msgId },
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Workflow failed.";
      setMessages((prev) => [...prev, { role: "agent", content: `❌ Error: ${message}`, id: `err-${Date.now()}` }]);
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleThinking = (msgId: string) => {
    setExpandedThinking(prev => {
      const newSet = new Set(prev);
      if (newSet.has(msgId)) {
        newSet.delete(msgId);
      } else {
        newSet.add(msgId);
      }
      return newSet;
    });
  };

  return (
    <div className="flex h-full flex-col bg-gray-50/50">
      {/* Header */}
      <div className="border-b-4 border-black bg-white px-6 py-4 flex items-center gap-2">
        <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse z-10"></div>
        <span className="text-[10px] font-black uppercase tracking-[0.2em] text-black">
          Chat: {buyer?.name ?? "No Buyer Agent"}
        </span>
      </div>

      {/* Seller Selection */}
      <div className="border-b border-gray-200 bg-white px-6 py-3">
        <label className="mb-2 block text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Seller Agent</label>
        <select
          value={selectedSellerId ?? ""}
          onChange={(event) => setSelectedSellerId(event.target.value)}
          className="w-full bg-white border-2 border-black px-4 py-3 text-xs font-bold uppercase tracking-widest outline-none"
        >
          <option value="" disabled>
            Select seller agent
          </option>
          {availableSellers.map((seller) => (
            <option key={seller.id} value={seller.id}>
              {seller.name}
            </option>
          ))}
        </select>
      </div>

      {/* Messages - Only this scrolls */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 flex flex-col justify-end">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex w-full flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}>
            {/* Thinking Section (inline, collapsible) */}
            {msg.thinking && (
              <div className="mb-2 w-full max-w-[85%] cursor-pointer" onClick={() => toggleThinking(msg.id)}>
                <div className="flex items-center gap-2 px-4 py-2 text-[9px] font-black uppercase tracking-widest text-gray-600 border-2 border-gray-400 bg-gray-100 hover:bg-gray-200 transition-colors rounded-none">
                  {expandedThinking.has(msg.id) ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  💭 Thinking
                </div>
                {expandedThinking.has(msg.id) && (
                  <div className="mt-0 px-4 py-3 text-[9px] text-gray-700 leading-relaxed border-2 border-gray-400 border-t-0 bg-white rounded-none whitespace-pre-wrap max-w-[85%]">
                    {msg.thinking}
                  </div>
                )}
              </div>
            )}

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
      </div>

      {/* Input */}
      <div className="p-6 bg-white border-t border-gray-100">
        <form onSubmit={handleSend} className="relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="COMMAND AGENT..."
            className="w-full bg-white border-2 border-black py-4 pl-6 pr-14 text-xs font-bold uppercase tracking-widest rounded-none focus:outline-none focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-all"
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
