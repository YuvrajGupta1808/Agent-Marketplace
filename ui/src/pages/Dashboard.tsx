import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { AgentFlowGraph } from "../components/dashboard/AgentFlowGraph";
import { ChatInterface } from "../components/dashboard/ChatInterface";
import { TransactionHistory } from "../components/dashboard/TransactionHistory";
import { useAppState } from "../lib/app-state";

function ResizeHandle() {
  return (
    <PanelResizeHandle className="w-1 bg-black hover:bg-gray-700 active:bg-black transition-colors cursor-col-resize z-10" />
  );
}

function VerticalResizeHandle() {
  return (
    <PanelResizeHandle className="h-1 bg-black hover:bg-gray-700 active:bg-black transition-colors cursor-row-resize z-10" />
  );
}

export function Dashboard() {
  const {
    currentBuyer,
    health,
    latestRun,
    runBuyerWorkflow,
    selectedSellerId,
    sellerAgents,
    setSelectedSellerId,
    allPayments,
  } = useAppState();

  return (
    <div className="flex min-h-0 w-full flex-1 flex-col overflow-hidden border-t border-black bg-black">
      <PanelGroup
        orientation="horizontal"
        className="min-h-0 min-w-0 w-full flex-1"
      >
        <Panel defaultSize={40} minSize={25} className="min-h-0 min-w-0">
          <PanelGroup
            orientation="vertical"
            className="h-full min-h-0 min-w-0 w-full"
          >
            <Panel defaultSize={70} minSize={30} className="min-h-0 min-w-0">
              <div className="h-full min-h-0 w-full overflow-hidden bg-gray-50">
                <AgentFlowGraph
                  buyer={currentBuyer}
                  sellerAgents={sellerAgents}
                  selectedSellerId={selectedSellerId}
                  latestRun={latestRun}
                />
              </div>
            </Panel>

            <VerticalResizeHandle />

            <Panel defaultSize={30} minSize={20} className="min-h-0 min-w-0">
              <div className="h-full min-h-0 w-full overflow-hidden bg-white">
                <TransactionHistory payments={allPayments} latestRun={latestRun} />
              </div>
            </Panel>
          </PanelGroup>
        </Panel>

        <ResizeHandle />

        <Panel defaultSize={60} minSize={35} className="min-h-0 min-w-0">
          <div className="h-full min-h-0 w-full overflow-hidden bg-white">
            <ChatInterface
              buyer={currentBuyer}
              sellerAgents={sellerAgents}
              selectedSellerId={selectedSellerId}
              setSelectedSellerId={(sellerId) => setSelectedSellerId(sellerId || null)}
              onRunWorkflow={runBuyerWorkflow}
              isCircleEnabled={Boolean(health?.circle_enabled)}
            />
          </div>
        </Panel>
      </PanelGroup>
    </div>
  );
}
