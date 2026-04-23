import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { StreamEvent } from "../../lib/api";

interface ThinkingStep {
  id: string;
  type: "planning" | "task_planned" | "task_start" | "discovery" | "step" | "payment_request" | "payment_done" | "research_sent" | "result_received" | "synthesis" | "error";
  message: string;
  details?: Record<string, unknown>;
  timestamp: number;
  indent?: number;
}

interface ThinkingNodeProps {
  isLoading: boolean;
  events: StreamEvent[];
}

export function ThinkingNode({ isLoading, events }: ThinkingNodeProps) {
  const [steps, setSteps] = useState<ThinkingStep[]>([]);
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    const newSteps: ThinkingStep[] = [];

    for (const event of events) {
      if (event.type === "custom_event") {
        const customData = event.data as Record<string, unknown>;
        const eventType = customData.event_type as string;

        if (eventType === "planning") {
          newSteps.push({
            id: `planning-${Date.now()}`,
            type: "planning",
            message: "📋 Analyzing goal and planning tasks...",
            timestamp: Date.now(),
            indent: 0,
          });
        } else if (eventType === "tasks_planned") {
          const taskCount = customData.task_count as number;
          const tasks = customData.tasks as Array<{task_id: string; query: string}>;
          newSteps.push({
            id: `tasks-planned-${Date.now()}`,
            type: "task_planned",
            message: `✅ Generated ${taskCount} research task(s)`,
            details: {
              tasks: tasks.map(t => `• ${t.query}`).join("\n"),
            },
            timestamp: Date.now(),
            indent: 0,
          });
        } else if (eventType === "node_start") {
          const nodeTitle = customData.title as string;
          const taskId = customData.task_id as string;
          const node = customData.node as string;
          const query = customData.query as string;

          let message = "";
          let type: ThinkingStep["type"] = "step";

          if (node === "discover_seller") {
            message = `🔍 Discovering seller for: "${query.slice(0, 50)}..."`;
            type = "discovery";
          } else if (node === "plan_research_steps") {
            message = `📝 Planning research approach...`;
            type = "step";
          } else if (node === "execute_payment") {
            message = `💳 Preparing payment for research...`;
            type = "payment_request";
          } else if (node === "send_research_request") {
            message = `📤 Sending research request to seller...`;
            type = "research_sent";
          } else if (node === "fetch_result") {
            message = `📥 Fetching research results...`;
            type = "result_received";
          } else {
            message = `▶ ${nodeTitle}`;
          }

          if (message) {
            newSteps.push({
              id: `${taskId}-${node}-start-${Date.now()}`,
              type,
              message,
              timestamp: Date.now(),
              indent: 1,
            });
          }
        } else if (eventType === "node_complete") {
          const nodeTitle = customData.title as string;
          const node = customData.node as string;
          const status = customData.status as string;
          const duration = customData.duration_ms as number;
          const taskId = customData.task_id as string;

          if (status === "error") {
            newSteps.push({
              id: `${taskId}-${node}-error-${Date.now()}`,
              type: "error",
              message: `❌ ${nodeTitle} failed`,
              timestamp: Date.now(),
              indent: 1,
            });
          } else if (node === "execute_payment" && customData.payment_details) {
            const paymentDetails = customData.payment_details as Record<string, unknown>;
            const amount = paymentDetails.amount_usdc as string;
            newSteps.push({
              id: `${taskId}-payment-done-${Date.now()}`,
              type: "payment_done",
              message: `✅ Payment executed: ${amount} USDC`,
              details: paymentDetails,
              timestamp: Date.now(),
              indent: 1,
            });
          } else if (node === "fetch_result" && customData.research_result) {
            const result = customData.research_result as Record<string, unknown>;
            const title = result.title as string;
            const summary = result.summary as string;
            newSteps.push({
              id: `${taskId}-result-${Date.now()}`,
              type: "result_received",
              message: `✅ Research completed: "${title}"`,
              details: {
                summary: summary.slice(0, 200),
                bullet_count: result.bullets_count,
              },
              timestamp: Date.now(),
              indent: 1,
            });
          }
        } else if (eventType === "error") {
          newSteps.push({
            id: `error-${Date.now()}`,
            type: "error",
            message: `❌ Error: ${customData.error as string}`,
            timestamp: Date.now(),
            indent: 0,
          });
        }
      }
    }

    setSteps(newSteps);
  }, [events]);

  if (steps.length === 0 && !isLoading) {
    return null;
  }

  return (
    <div className="w-full bg-white border-2 border-black p-4 rounded-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] mb-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left"
      >
        <div className="flex-1">
          <div className="text-[10px] font-black uppercase tracking-[0.2em] text-black">
            💭 Thinking Process
          </div>
          <div className="text-[9px] font-bold uppercase tracking-widest text-gray-600 mt-1">
            {steps.length} events captured
          </div>
        </div>
        <div className="flex-shrink-0">
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>
      </button>

      {expanded && (
        <div className="mt-3 pt-3 border-t-2 border-black space-y-2">
          {steps.map((step) => (
            <div key={step.id} className="text-[9px] font-bold text-gray-800 pl-3 border-l-2 border-gray-400">
              <div className="flex items-start gap-2">
                <span className="flex-shrink-0">{step.message}</span>
              </div>
              {step.details && step.type === "task_planned" && (
                <div className="mt-1.5 space-y-0.5 text-[8px] text-gray-700 font-medium">
                  {(step.details.tasks as string).split("\n").map((task, i) => (
                    <div key={i} className="ml-2">{task}</div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {isLoading && (
        <div className="mt-3 pt-3 border-t-2 border-black flex items-center gap-2">
          <div className="animate-spin text-lg">⚙️</div>
          <span className="text-[9px] font-bold uppercase tracking-widest text-gray-700">Processing...</span>
        </div>
      )}
    </div>
  );
}
