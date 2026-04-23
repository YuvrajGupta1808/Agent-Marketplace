import { Send } from "lucide-react";
import React, { useEffect, useState } from "react";
import type { AgentRecord, RunResponse, StreamEvent } from "../../lib/api";

interface ChatInterfaceProps {
  buyer: AgentRecord | null;
  sellerAgents: AgentRecord[];
  selectedSellerId: string | null;
  setSelectedSellerId: (sellerId: string) => void;
  onRunWorkflow: (goal: string) => Promise<RunResponse>;
  isCircleEnabled: boolean;
  streamEvents: StreamEvent[];
  isStreaming: boolean;
}

export function ChatInterface({
  buyer,
  sellerAgents,
  selectedSellerId,
  setSelectedSellerId,
  onRunWorkflow,
  isCircleEnabled,
  streamEvents,
  isStreaming,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Array<{role: "user" | "agent", content: string}>>([
    { role: "agent", content: "Backend workflow ready. Choose a seller, then send a research request." }
  ]);
  const [input, setInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastProcessedEventIndex, setLastProcessedEventIndex] = useState(0);

  useEffect(() => {
    // Process new stream events
    if (streamEvents.length > lastProcessedEventIndex) {
      const newEvents = streamEvents.slice(lastProcessedEventIndex);
      setLastProcessedEventIndex(streamEvents.length);

      for (const event of newEvents) {
        switch (event.type) {
          case "phase_start":
            {
              const message = (event.data.message as string) || "Processing...";
              setMessages((prev) => [...prev, { role: "agent", content: message }]);
            }
            break;
          case "phase_complete":
            {
              const intent = event.data.intent as string;
              if (intent === "conversational") {
                setMessages((prev) => [
                  ...prev,
                  { role: "agent", content: "💬 Conversational query detected" },
                ]);
              } else {
                setMessages((prev) => [
                  ...prev,
                  { role: "agent", content: `📋 Planning research approach...` },
                ]);
              }
            }
            break;
          case "planning":
            {
              const taskCount = event.data.tasks as any[];
              setMessages((prev) => [
                ...prev,
                {
                  role: "agent",
                  content: `📋 Created plan with ${taskCount?.length || 0} research task(s)`,
                },
              ]);
            }
            break;
          case "buyer_executing":
            {
              const taskId = event.data.task_id as string;
              setMessages((prev) => [
                ...prev,
                { role: "agent", content: `🎯 Executing task: ${taskId}` },
              ]);
            }
            break;
          case "agent_reasoning":
            {
              const reasoning = event.data.reasoning as string;
              if (reasoning) {
                setMessages((prev) => [
                  ...prev,
                  { role: "agent", content: `💭 Agent Reasoning:\n${reasoning}` },
                ]);
              }
            }
            break;
          case "research_complete":
            {
              const count = event.data.count as number;
              setMessages((prev) => [
                ...prev,
                {
                  role: "agent",
                  content: `📚 Research complete for ${count} task(s)`,
                },
              ]);
            }
            break;
          case "result":
            {
              const title = event.data.title as string;
              const summary = event.data.summary as string;
              const bullets = event.data.bullets as string[];
              let resultText = `**${title}**\n${summary}`;
              if (bullets && bullets.length > 0) {
                resultText += `\n${bullets.map((b) => `• ${b}`).join("\n")}`;
              }
              setMessages((prev) => [...prev, { role: "agent", content: resultText }]);
            }
            break;
          case "done":
            {
              const finalAnswer = event.data.final_answer as string;
              if (finalAnswer) {
                setMessages((prev) => [
                  ...prev,
                  { role: "agent", content: finalAnswer },
                ]);
              }
            }
            break;
          case "error":
            {
              const error = event.data.error as string;
              setMessages((prev) => [
                ...prev,
                { role: "agent", content: `❌ Error: ${error}` },
              ]);
            }
            break;
        }
      }
    }
  }, [streamEvents, lastProcessedEventIndex]);

  const connectedSellerIds = Array.isArray(buyer?.metadata.connected_seller_ids)
    ? (buyer?.metadata.connected_seller_ids as string[])
    : sellerAgents.map((seller) => seller.id);
  const availableSellers = sellerAgents.filter((seller) => connectedSellerIds.includes(seller.id));

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    if (!buyer) {
      setMessages((prev) => [...prev, { role: "agent", content: "Create a buyer agent before sending workflow commands." }]);
      return;
    }
    if (!isCircleEnabled) {
      setMessages((prev) => [...prev, { role: "agent", content: "Circle is not configured on the backend, so real wallet execution is blocked." }]);
      return;
    }
    if (!selectedSellerId) {
      setMessages((prev) => [...prev, { role: "agent", content: "Select a seller agent before running the workflow." }]);
      return;
    }

    const goal = input;
    setMessages(prev => [...prev, { role: "user", content: goal }]);
    setInput("");
    setIsSubmitting(true);

    try {
      const result = await onRunWorkflow(goal);

      let response = "";

      // Show intent detection result
      if (result.is_conversational) {
        // For conversational queries, show the direct answer
        response = result.final_answer || "I'm ready to help with any research questions you have!";
      } else {
        // For research queries, show the full workflow
        const planningNote = result.buyer_workflows?.[0]?.execution_plan?.length
          ? `📋 Execution Plan: ${result.buyer_workflows[0].execution_plan.length} steps\n`
          : "";

        // Show execution timing
        const executionPhases = result.buyer_workflows?.[0]?.node_outputs || [];
        const totalTime = executionPhases.reduce((sum, n) => sum + (n.duration_ms || 0), 0);
        const timingNote = executionPhases.length > 0
          ? `⏱️ Total Time: ${totalTime}ms (${executionPhases.length} nodes)\n\n`
          : "";

        // Show reasoning from buyer agent
        const buyerReasoning = executionPhases
          .find((n: any) => n.node_name === "buyer-plan")?.reasoning
          || executionPhases.find((n: any) => n.title?.includes("Reason"))?.reasoning
          || "";
        const reasoningNote = buyerReasoning ? `💭 Agent Reasoning:\n${buyerReasoning}\n\n` : "";

        // Show research results
        const resultsNote = result.results?.length > 0
          ? `📚 Research Findings:\n${result.results.map((r: any) => {
              const bullets = r.bullets?.slice(0, 2).map((b: string) => `• ${b}`).join('\n') || '';
              return `${r.title}\n${r.summary?.substring(0, 120)}${r.summary && r.summary.length > 120 ? '...' : ''}\n${bullets}`;
            }).join('\n\n')}\n\n`
          : "";

        response = (planningNote + timingNote + reasoningNote + resultsNote + (result.final_answer || "Research complete.")).trim();
      }

      setMessages((prev) => [...prev, { role: "agent", content: response }]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Workflow failed.";
      setMessages((prev) => [...prev, { role: "agent", content: `❌ Error: ${message}` }]);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex h-full flex-col bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white/80 backdrop-blur px-6 py-4 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <div>
            <span className="text-xs font-semibold text-gray-900 uppercase tracking-wide">
              {buyer?.name ?? "No Buyer Agent"}
            </span>
            <p className="text-[11px] text-gray-500 mt-0.5">Agent Marketplace</p>
          </div>
        </div>
      </div>

      {/* Seller Selection */}
      <div className="border-b border-gray-200 bg-white/50 px-6 py-4">
        <label className="mb-3 block text-xs font-semibold uppercase tracking-wide text-gray-700">Select Research Provider</label>
        <select
          value={selectedSellerId ?? ""}
          onChange={(event) => setSelectedSellerId(event.target.value)}
          className="w-full bg-white border border-gray-300 px-4 py-2.5 text-sm font-medium text-gray-900 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all hover:border-gray-400"
        >
          <option value="" disabled>
            Choose a seller agent...
          </option>
          {availableSellers.map((seller) => (
            <option key={seller.id} value={seller.id}>
              {seller.name}
            </option>
          ))}
        </select>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 flex flex-col justify-end">
        {messages.map((msg, i) => (
          <div key={i} className={`flex w-full flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}>
             <div className={`px-5 py-3 max-w-[85%] rounded-2xl leading-relaxed text-sm transition-all ${
               msg.role === "user"
                 ? "bg-blue-600 text-white rounded-br-none shadow-lg"
                 : "bg-white text-gray-900 border border-gray-200 rounded-bl-none shadow-md"
             }`}>
               <div className="whitespace-pre-wrap break-words">{msg.content}</div>
             </div>
             <span className={`mt-2 text-xs font-medium ${msg.role === "user" ? "text-blue-600" : "text-gray-500"}`}>
               {msg.role === "user" ? "You" : "Agent"}
             </span>
          </div>
        ))}
        {isSubmitting && (
          <div className="flex items-center gap-2 text-gray-500">
            <div className="flex gap-1">
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: "0.1s"}}></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: "0.2s"}}></div>
            </div>
            <span className="text-xs">Agent thinking...</span>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 bg-white/80 backdrop-blur px-6 py-5">
        <form onSubmit={handleSend} className="relative flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isSubmitting}
            placeholder="Ask the research agent anything..."
            className="flex-1 bg-gray-100 border border-gray-300 px-5 py-3 text-sm text-gray-900 rounded-full focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all placeholder-gray-500 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
          />
          <button
            type="submit"
            disabled={isSubmitting || !input.trim()}
            className="flex-shrink-0 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white w-10 h-10 rounded-full flex items-center justify-center transition-all transform hover:scale-105 active:scale-95 shadow-lg"
          >
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}
