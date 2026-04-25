import React, { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { StreamEvent } from "../../lib/api";

interface ThinkingStep {
  id: string;
  type: "planning" | "task_planned" | "task_start" | "discovery" | "step" | "payment_request" | "payment_done" | "research_sent" | "result_received" | "synthesis" | "error";
  message: string;
  details?: Record<string, unknown>;
  timestamp: number;
  status: "pending" | "in_progress" | "complete" | "error";
}

interface ThinkingNodeProps {
  isLoading: boolean;
  events: StreamEvent[];
}

function getStatusBadge(type: ThinkingStep["type"], status: ThinkingStep["status"]) {
  const baseClasses = "px-2 py-1 text-[7px] font-black uppercase tracking-wider border whitespace-nowrap";

  if (status === "error") {
    return <span className={`${baseClasses} bg-red-100 border-red-300 text-red-700`}>ERROR</span>;
  }

  if (status === "complete") {
    return <span className={`${baseClasses} bg-green-100 border-green-300 text-green-700`}>DONE</span>;
  }

  if (status === "in_progress") {
    return <span className={`${baseClasses} bg-blue-100 border-blue-300 text-blue-700`}>RUNNING</span>;
  }

  return <span className={`${baseClasses} bg-gray-100 border-gray-300 text-gray-600`}>PENDING</span>;
}

function getStepLabel(type: ThinkingStep["type"]): string {
  switch (type) {
    case "planning":
      return "PLANNING";
    case "task_planned":
      return "TASKS GENERATED";
    case "discovery":
      return "DISCOVERY";
    case "step":
      return "STEP";
    case "payment_request":
      return "PAYMENT";
    case "payment_done":
      return "PAYMENT DONE";
    case "research_sent":
      return "REQUEST SENT";
    case "result_received":
      return "RESULT";
    case "synthesis":
      return "SYNTHESIS";
    case "error":
      return "ERROR";
    default:
      return "STEP";
  }
}

export function ThinkingNode({ isLoading, events }: ThinkingNodeProps) {
  const [steps, setSteps] = useState<ThinkingStep[]>([]);
  const [expanded, setExpanded] = useState(true);

  React.useEffect(() => {
    const newSteps: ThinkingStep[] = [];

    for (const event of events) {
      if (event.type === "custom_event") {
        const customData = event.data as Record<string, unknown>;
        const eventType = customData.event_type as string;

        if (eventType === "planning") {
          newSteps.push({
            id: `planning-${Date.now()}`,
            type: "planning",
            message: "Analyzing goal and planning tasks...",
            timestamp: Date.now(),
            status: "complete",
          });
        } else if (eventType === "tasks_planned") {
          const taskCount = customData.task_count as number;
          const tasks = customData.tasks as Array<{task_id: string; query: string}>;
          newSteps.push({
            id: `tasks-planned-${Date.now()}`,
            type: "task_planned",
            message: `Generated ${taskCount} research task(s)`,
            details: {
              tasks: tasks.map(t => `• ${t.query}`).join("\n"),
            },
            timestamp: Date.now(),
            status: "complete",
          });
        } else if (eventType === "node_start") {
          const nodeTitle = customData.title as string;
          const taskId = customData.task_id as string;
          const node = customData.node as string;
          const query = customData.query as string;

          let message = "";
          let type: ThinkingStep["type"] = "step";

          if (node.startsWith("discover_seller")) {
            message = `Discovering seller for: "${query.slice(0, 50)}..."`;
            type = "discovery";
          } else if (node.startsWith("plan_research_steps")) {
            message = `Planning research approach...`;
            type = "step";
          } else if (node.startsWith("execute_payment")) {
            message = `Preparing payment for research...`;
            type = "payment_request";
          } else if (node.startsWith("send_research")) {
            message = `Sending research request to seller...`;
            type = "research_sent";
          } else if (node.startsWith("fetch_result")) {
            message = `Fetching research results...`;
            type = "result_received";
          } else {
            message = `${nodeTitle}`;
          }

          if (message) {
            newSteps.push({
              id: `${taskId}-${node}-start-${Date.now()}`,
              type,
              message,
              timestamp: Date.now(),
              status: "in_progress",
            });
          }
        } else if (eventType === "node_complete") {
          const nodeTitle = customData.title as string;
          const node = customData.node as string;
          const status = customData.status as string;
          const taskId = customData.task_id as string;
          const errorMessage = customData.error as string | undefined;

          if (status === "error") {
            newSteps.push({
              id: `${taskId}-${node}-error-${Date.now()}`,
              type: "error",
              message: errorMessage ? `${nodeTitle} failed: ${errorMessage}` : `${nodeTitle} failed`,
              timestamp: Date.now(),
              status: "error",
            });
          } else if (node.startsWith("execute_payment") && customData.payment_details) {
            const paymentDetails = customData.payment_details as Record<string, unknown>;
            const amount = paymentDetails.amount_usdc as string;
            newSteps.push({
              id: `${taskId}-payment-done-${Date.now()}`,
              type: "payment_done",
              message: `Payment executed: ${amount} USDC`,
              details: paymentDetails,
              timestamp: Date.now(),
              status: "complete",
            });
          } else if (node.startsWith("fetch_result") && customData.research_result) {
            const result = customData.research_result as Record<string, unknown>;
            const title = result.title as string;
            newSteps.push({
              id: `${taskId}-result-${Date.now()}`,
              type: "result_received",
              message: `Research completed: "${title}"`,
              details: result,
              timestamp: Date.now(),
              status: "complete",
            });
          }
        } else if (eventType === "error") {
          newSteps.push({
            id: `error-${Date.now()}`,
            type: "error",
            message: `Error: ${customData.error as string}`,
            timestamp: Date.now(),
            status: "error",
          });
        }
      } else if (event.type === "error") {
        newSteps.push({
          id: `stream-error-${Date.now()}`,
          type: "error",
          message: `Error: ${event.error || "Workflow failed."}`,
          timestamp: Date.now(),
          status: "error",
        });
      }
    }

    setSteps(newSteps);
  }, [events]);

  // Show thinking section if loading OR has steps (keep it persistent)
  if (steps.length === 0 && !isLoading) {
    return null;
  }

  return (
    <div className="flex w-full justify-start mb-3">
      <div className="w-full max-w-[85%] bg-white border-2 border-black">
        {/* Header */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center justify-between w-full px-4 py-3 border-b-2 border-black hover:bg-gray-50 transition-colors"
        >
          <div className="flex-1 text-left">
            <div className="text-[11px] font-black uppercase tracking-[0.2em] text-black">
              Thinking Process
            </div>
            <div className="text-[10px] font-bold uppercase tracking-widest text-gray-500 mt-1">
              {steps.length} events captured
              {isLoading && " • In progress"}
              {!isLoading && steps.length > 0 && " • Complete"}
            </div>
          </div>
          <div className="flex-shrink-0 text-black">
            {expanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
          </div>
        </button>

        {/* Content */}
        {expanded && (
          <div className="p-4 space-y-2 max-h-96 overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
            {steps.length === 0 && isLoading ? (
              <div className="text-[10px] font-bold uppercase tracking-widest text-gray-600 py-2">
                Initializing...
              </div>
            ) : (
              steps.map((step) => (
                <div key={step.id} className="flex items-start gap-3 text-[10px]">
                  {/* Status badge */}
                  <div className="flex-shrink-0 pt-0.5">
                    {getStatusBadge(step.type, step.status)}
                  </div>

                  {/* Message */}
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-black break-words">
                      {step.message}
                    </p>

                    {/* Details */}
                    {step.details && step.type === "task_planned" && (
                      <div className="mt-1.5 space-y-0.5 text-[9px] text-gray-700 font-medium pl-2 border-l border-gray-300">
                        {(step.details.tasks as string).split("\n").map((task, i) => (
                          <div key={i}>{task}</div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {isLoading && (
              <div className="flex items-center gap-2 pt-2 border-t border-gray-200">
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-gray-600">
                  Processing...
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
