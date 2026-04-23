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
    <div className="flex h-full flex-col bg-gray-50/50">
      <div className="border-b-4 border-black bg-white px-6 py-4 flex items-center gap-2">
        <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse z-10"></div>
        <span className="text-[10px] font-black uppercase tracking-[0.2em] text-black">
          Chat: {buyer?.name ?? "No Buyer Agent"}
        </span>
      </div>

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
      
      <div className="flex-1 overflow-y-auto p-6 space-y-4 flex flex-col justify-end">
        {messages.map((msg, i) => (
          <div key={i} className={`flex w-full flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}>
             <div className={`p-4 rounded-none text-xs font-semibold max-w-[85%] border-2 leading-relaxed shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] ${msg.role === "user" ? "bg-black text-white border-black" : "bg-white text-gray-800 border-black"}`}>
               {msg.content}
             </div>
             <span className="mt-2 text-[9px] font-black uppercase tracking-widest text-gray-400">
               {msg.role === "user" ? "User" : "System Node"}
             </span>
          </div>
        ))}
      </div>

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
