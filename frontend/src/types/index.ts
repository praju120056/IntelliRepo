// Central TypeScript type definitions for GitParse

// ── API Types ────────────────────────────────────────────────────

export type AnalysisStatus =
  | 'pending'
  | 'cloning'
  | 'parsing'
  | 'building_graph'
  | 'embedding'
  | 'indexing'
  | 'complete'
  | 'failed';

export interface FileNode {
  path: string;
  language: string;
  size_bytes: number;
  lines: number;
  is_parseable: boolean;
}

export interface RepositoryMap {
  repo_id: string;
  url: string;
  name: string;
  default_branch: string;
  total_files: number;
  python_files: number;
  file_tree: FileNode[];
  cloned_at: string;
  status: AnalysisStatus;
}

export interface RepoStatusResponse {
  repo_id: string;
  url: string;
  name: string;
  status: AnalysisStatus;
  python_files: number;
  total_files: number;
  cloned_at: string;
  last_accessed?: string;
}

export interface AnalyzeResponse {
  repo_id: string;
  status: AnalysisStatus;
  message: string;
}

// ── Graph Types ──────────────────────────────────────────────────

export type NodeType = 'repository' | 'file' | 'class' | 'function';
export type EdgeType = 'contains' | 'imports' | 'calls' | 'inherits' | 'defines';

export interface GraphNode {
  id: string;
  type: NodeType;
  label?: string;
  name?: string;
  file_path?: string;
  path?: string;
  language?: string;
  start_line?: number;
  end_line?: number;
  bases?: string[];
  args?: string[];
  decorators?: string[];
  docstring?: string;
  is_method?: boolean;
  class_name?: string;
  lines?: number;
  size_bytes?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: EdgeType;
  module?: string;
  call_name?: string;
  impact?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    total_nodes: number;
    total_edges: number;
    repo_id: string;
    repo_name: string;
  };
}

// ── Search Types ─────────────────────────────────────────────────

export interface SearchRequest {
  query: string;
  top_k?: number;
  node_types?: string[];
  expand?: boolean;
  expand_depth?: number;
}

export interface SearchResultNode {
  id: string;
  type: string;
  name: string;
  file_path: string;
  start_line?: number;
  end_line?: number;
  docstring?: string;
  score: number;
  origin: 'semantic' | 'graph_expansion';
}

export interface SearchResponse {
  query: string;
  seed_nodes: SearchResultNode[];
  expanded_nodes: SearchResultNode[];
  edges: GraphEdge[];
  explanation: string;
}

// ── Query Types ──────────────────────────────────────────────────

export type QueryType =
  | 'callers_of'
  | 'dependencies_of'
  | 'importers_of'
  | 'call_chain'
  | 'impact_of';

export interface QueryRequest {
  type: QueryType;
  target: string;
  depth?: number;
}

export interface QueryResponse {
  query_type: QueryType;
  target: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  explanation: string;
  metadata: Record<string, unknown>;
}

// ── UI Types ─────────────────────────────────────────────────────

export interface ActiveView {
  type: 'home' | 'tree' | 'deps' | 'calls' | 'search' | 'query';
}

export const STATUS_LABELS: Record<AnalysisStatus, string> = {
  pending: 'Pending',
  cloning: 'Cloning repository...',
  parsing: 'Parsing Python files...',
  building_graph: 'Building graph...',
  embedding: 'Generating embeddings...',
  indexing: 'Indexing vectors...',
  complete: 'Analysis complete',
  failed: 'Analysis failed',
};

export const NODE_COLORS: Record<NodeType, string> = {
  repository: 'var(--color-repo)',
  file: 'var(--color-file)',
  class: 'var(--color-class)',
  function: 'var(--color-function)',
};
