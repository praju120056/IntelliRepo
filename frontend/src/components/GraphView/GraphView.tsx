import React, { useCallback, useEffect, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import { useRepoStore } from '../../store/repoStore';
import { getDepsGraph, getCallGraph, getFullGraph } from '../../services/api';
import type { GraphData, NodeType } from '../../types';
import { CustomNode } from './CustomNode';
import './GraphView.css';

// ── Dagre layout ─────────────────────────────────────────────────

const nodeTypes = { custom: CustomNode };

const NODE_WIDTH = 180;
const NODE_HEIGHT = 60;

function applyDagreLayout(nodes: Node[], edges: Edge[], direction = 'TB'): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 60, ranksep: 80 });

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
  edges.forEach((e) => g.setEdge(e.source, e.target));

  dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      ...n,
      position: {
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2,
      },
    };
  });
}

// ── Color map ─────────────────────────────────────────────────────

const NODE_BORDER_COLORS: Record<string, string> = {
  repository: 'var(--color-repo)',
  file: 'var(--color-file)',
  class: 'var(--color-class)',
  function: 'var(--color-function)',
};

const EDGE_COLORS: Record<string, string> = {
  imports: '#fb923c',
  calls: '#38bdf8',
  inherits: '#4ade80',
  contains: '#475569',
};

// ── Graph data → React Flow nodes/edges ──────────────────────────

function convertToFlowData(
  graphData: GraphData,
  highlightedIds: Set<string>,
): { nodes: Node[]; edges: Edge[] } {
  const rfNodes: Node[] = graphData.nodes.map((n) => ({
    id: n.id,
    type: 'custom',
    data: {
      ...n,
      highlighted: highlightedIds.has(n.id),
      borderColor: NODE_BORDER_COLORS[n.type] || '#475569',
    },
    position: { x: 0, y: 0 },  // overwritten by dagre
  }));

  const rfEdges: Edge[] = graphData.edges.map((e, i) => ({
    id: `e-${i}-${e.source}-${e.target}`,
    source: e.source,
    target: e.target,
    style: {
      stroke: EDGE_COLORS[e.type] || '#475569',
      strokeWidth: 1.5,
      opacity: 0.7,
    },
    animated: e.type === 'calls',
    label: e.type !== 'contains' ? e.type : undefined,
    labelStyle: { fontSize: 10, fill: '#475569', fontFamily: 'var(--font-mono)' },
    labelBgStyle: { fill: 'var(--bg-elevated)', fillOpacity: 0.9 },
  }));

  return { nodes: rfNodes, edges: rfEdges };
}

// ── Component ─────────────────────────────────────────────────────

type GraphMode = 'deps' | 'calls' | 'full';

interface GraphViewProps {
  mode: GraphMode;
}

export function GraphView({ mode }: GraphViewProps) {
  const { currentRepo, graphData, setGraphData, highlightedNodeIds, setSelectedNode } = useRepoStore();
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = React.useState(false);

  const repoId = currentRepo?.repo_id;

  // Load graph based on mode
  useEffect(() => {
    if (!repoId) return;
    setLoading(true);
    const fetcher = mode === 'deps' ? getDepsGraph : mode === 'calls' ? getCallGraph : getFullGraph;
    fetcher(repoId)
      .then((data) => {
        setGraphData(data);
      })
      .finally(() => setLoading(false));
  }, [repoId, mode]);

  // Convert to React Flow format
  useEffect(() => {
    if (!graphData || graphData.nodes.length === 0) return;
    const { nodes: rfNodes, edges: rfEdges } = convertToFlowData(graphData, highlightedNodeIds);
    const layoutedNodes = applyDagreLayout(rfNodes, rfEdges, 'TB');
    setNodes(layoutedNodes);
    setEdges(rfEdges);
  }, [graphData, highlightedNodeIds]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node.data as never);
  }, [setSelectedNode]);

  const title = mode === 'deps' ? 'Import Dependency Graph' : mode === 'calls' ? 'Function Call Graph' : 'Full Graph';
  const subtitle = graphData
    ? `${graphData.stats.total_nodes} nodes · ${graphData.stats.total_edges} edges`
    : '';

  return (
    <div className="graph-view">
      {/* Header */}
      <div className="graph-header">
        <div>
          <h2 className="graph-title">{title}</h2>
          {subtitle && <p className="graph-subtitle">{subtitle}</p>}
        </div>
        <div className="graph-legend">
          {Object.entries(NODE_BORDER_COLORS).map(([type, color]) => (
            <div key={type} className="legend-item">
              <div className="legend-dot" style={{ background: color }} />
              <span>{type}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Canvas */}
      <div className="graph-canvas">
        {loading && (
          <div className="graph-loading">
            <div className="spinner" />
            <span>Loading graph data...</span>
          </div>
        )}
        {!loading && nodes.length === 0 && (
          <div className="empty-state">
            <p>No graph data available for this view.</p>
          </div>
        )}
        {!loading && nodes.length > 0 && (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.15 }}
            minZoom={0.05}
            maxZoom={2}
            defaultEdgeOptions={{ type: 'smoothstep' }}
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={24}
              size={1}
              color="var(--border-subtle)"
            />
            <Controls />
            <MiniMap
              nodeColor={(n) => NODE_BORDER_COLORS[(n.data as { type: NodeType })?.type] || '#475569'}
              maskColor="rgba(10,13,20,0.7)"
            />
          </ReactFlow>
        )}
      </div>
    </div>
  );
}
