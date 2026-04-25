import {
    addEdge,
    Connection,
    Controls,
    Edge,
    ReactFlow,
    useEdgesState,
    useNodesState
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useCallback, useEffect, useMemo, useRef } from 'react';
import type { ReactFlowInstance } from '@xyflow/react';
import type { AgentRecord, RunResponse } from '../../lib/api';
import { isSellerPublished } from '../../lib/seller';

function buildGraph(
  buyer: AgentRecord | null,
  sellerAgents: AgentRecord[],
  selectedSellerId: string | null,
  latestRun: RunResponse | null,
) {
  if (!buyer) {
    return { nodes: [], edges: [] };
  }

  const connectedSellerIds = Array.isArray(buyer.metadata.connected_seller_ids)
    ? (buyer.metadata.connected_seller_ids as string[])
    : sellerAgents.map((seller) => seller.id);
  const connectedSellers = sellerAgents.filter((seller) => isSellerPublished(seller) && connectedSellerIds.includes(seller.id));

  const nodes = [
    {
      id: buyer.id,
      type: 'input',
      data: { label: buyer.name },
      position: { x: 250, y: 50 },
      style: { backgroundColor: '#ffffff', color: '#000000', borderRadius: '0px', padding: '16px 24px', border: '2px solid #000000', boxShadow: '4px 4px 0px 0px rgba(0,0,0,1)', fontWeight: '900', fontSize: '12px', letterSpacing: '0.1em' },
    },
    ...connectedSellers.map((seller, index) => ({
      id: seller.id,
      data: { label: seller.name },
      position: { x: 80 + (index * 220), y: 220 },
      style: {
        backgroundColor: '#000000',
        color: '#ffffff',
        borderRadius: '0px',
        padding: '12px 16px',
        border: '2px solid #000000',
        fontSize: '10px',
        fontWeight: 'bold',
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        boxShadow: '4px 4px 0px 0px rgba(0,0,0,1)',
      },
    })),
  ];

  const latestPayment = latestRun?.payments[0];
  const edges = connectedSellers.map((seller) => ({
    id: `edge-${buyer.id}-${seller.id}`,
    source: buyer.id,
    target: seller.id,
    animated: seller.id === selectedSellerId,
    label: seller.id === selectedSellerId && latestPayment
      ? `${latestPayment.amount_usdc} USDC`
      : 'Connected',
  }));

  return { nodes, edges };
}

interface AgentFlowGraphProps {
  buyer: AgentRecord | null;
  sellerAgents: AgentRecord[];
  selectedSellerId: string | null;
  latestRun: RunResponse | null;
}

export function AgentFlowGraph({ buyer, sellerAgents, selectedSellerId, latestRun }: AgentFlowGraphProps) {
  const graph = useMemo(
    () => buildGraph(buyer, sellerAgents, selectedSellerId, latestRun),
    [buyer, sellerAgents, selectedSellerId, latestRun],
  );
  const [nodes, setNodes, onNodesChange] = useNodesState(graph.nodes as any);
  const [edges, setEdges, onEdgesChange] = useEdgesState(graph.edges);
  const containerRef = useRef<HTMLDivElement>(null);
  const rfRef = useRef<ReactFlowInstance | null>(null);

  const onConnect = useCallback(
    (params: Connection | Edge) =>
      setEdges((eds) => addEdge(params, eds) as typeof eds),
    [setEdges],
  );

  const centerGraph = useCallback((instance: ReactFlowInstance) => {
    void instance.fitView({ padding: 0.2, duration: 0 });
  }, []);

  const onInit = useCallback(
    (instance: ReactFlowInstance) => {
      rfRef.current = instance;
      centerGraph(instance);
    },
    [centerGraph],
  );

  useEffect(() => {
    setNodes(graph.nodes as any);
    setEdges(graph.edges as any);
  }, [graph.nodes, graph.edges, setEdges, setNodes]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      if (rfRef.current) centerGraph(rfRef.current);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [centerGraph]);

  // Show plan and execution info
  const executionPhases = latestRun?.buyer_workflows?.[0]?.node_outputs || [];
  const planningNote = latestRun?.buyer_workflows?.[0]?.execution_plan?.length
    ? `Plan: ${latestRun.buyer_workflows[0].execution_plan.length} steps`
    : '';
  const timeInfo = executionPhases.length > 0
    ? `Execution: ${executionPhases.reduce((sum, n) => sum + (n.duration_ms || 0), 0)}ms`
    : '';

  return (
    <div className="relative flex h-full flex-col bg-gray-50">
      <div className="absolute left-6 top-6 z-10 border-2 border-black bg-white p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
        <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-black">Agent Flow</h3>
        <p className="mt-1 text-[10px] font-bold uppercase text-gray-500">{buyer?.name || 'No Buyer'} → Sellers</p>
        {planningNote && <p className="mt-2 text-[9px] text-gray-600">📋 {planningNote}</p>}
        {timeInfo && <p className="text-[9px] text-gray-600">⏱️ {timeInfo}</p>}
        {latestRun?.is_conversational && <p className="mt-1 text-[9px] text-blue-600">💬 Conversational Query</p>}
      </div>
      <div ref={containerRef} className="relative min-h-0 w-full flex-1">
        {!buyer ? (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-gray-50/95 p-8 text-center">
            <div className="border-2 border-black bg-white p-6 shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]">
              <p className="text-xs font-black uppercase tracking-[0.15em] text-black">No buyer agent yet</p>
              <p className="mt-3 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                Build a buyer agent to see the live graph.
              </p>
            </div>
          </div>
        ) : null}
        <div
          className="pointer-events-none absolute inset-0 z-0 opacity-[0.03]"
          style={{
            backgroundImage: 'radial-gradient(#000 1px, transparent 1px)',
            backgroundSize: '20px 20px',
          }}
        />
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onInit={onInit}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          className="z-10 bg-transparent"
        >
          <style>{`.react-flow__handle { opacity: 0 !important; pointer-events: none !important; }`}</style>
          <Controls className="rounded-none border-2 border-black bg-white fill-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]" />
        </ReactFlow>
      </div>
    </div>
  );
}
