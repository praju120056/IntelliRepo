import { create } from 'zustand';
import type {
  RepoStatusResponse,
  GraphData,
  SearchResponse,
  QueryResponse,
  ActiveView,
  GraphNode,
  AnalysisStatus,
} from '../types';

interface RepoStore {
  // ── Active repository ─────────────────────────────────────────
  currentRepo: RepoStatusResponse | null;
  setCurrentRepo: (repo: RepoStatusResponse | null) => void;
  updateRepoStatus: (status: AnalysisStatus) => void;

  // ── Graph data ────────────────────────────────────────────────
  graphData: GraphData | null;
  setGraphData: (data: GraphData | null) => void;

  // ── File tree ─────────────────────────────────────────────────
  fileTree: unknown[] | null;
  setFileTree: (tree: unknown[] | null) => void;

  // ── Selected node ─────────────────────────────────────────────
  selectedNode: GraphNode | null;
  setSelectedNode: (node: GraphNode | null) => void;

  // ── Search results ────────────────────────────────────────────
  searchResults: SearchResponse | null;
  setSearchResults: (results: SearchResponse | null) => void;
  isSearching: boolean;
  setIsSearching: (v: boolean) => void;

  // ── Query results ─────────────────────────────────────────────
  queryResults: QueryResponse | null;
  setQueryResults: (results: QueryResponse | null) => void;
  isQuerying: boolean;
  setIsQuerying: (v: boolean) => void;

  // ── UI view ───────────────────────────────────────────────────
  activeView: ActiveView;
  setActiveView: (view: ActiveView) => void;

  // ── Loading / error ───────────────────────────────────────────
  isAnalyzing: boolean;
  setIsAnalyzing: (v: boolean) => void;
  error: string | null;
  setError: (msg: string | null) => void;

  // ── Highlighted nodes (from query/search results) ─────────────
  highlightedNodeIds: Set<string>;
  setHighlightedNodeIds: (ids: Set<string>) => void;

  // ── Reset ─────────────────────────────────────────────────────
  reset: () => void;
}

const initialState = {
  currentRepo: null,
  graphData: null,
  fileTree: null,
  selectedNode: null,
  searchResults: null,
  isSearching: false,
  queryResults: null,
  isQuerying: false,
  activeView: { type: 'home' } as ActiveView,
  isAnalyzing: false,
  error: null,
  highlightedNodeIds: new Set<string>(),
};

export const useRepoStore = create<RepoStore>((set) => ({
  ...initialState,

  setCurrentRepo: (repo) => set({ currentRepo: repo }),
  updateRepoStatus: (status) =>
    set((s) => ({
      currentRepo: s.currentRepo ? { ...s.currentRepo, status } : null,
    })),

  setGraphData: (data) => set({ graphData: data }),
  setFileTree: (tree) => set({ fileTree: tree }),
  setSelectedNode: (node) => set({ selectedNode: node }),

  setSearchResults: (results) => set({ searchResults: results }),
  setIsSearching: (v) => set({ isSearching: v }),

  setQueryResults: (results) => set({ queryResults: results }),
  setIsQuerying: (v) => set({ isQuerying: v }),

  setActiveView: (view) => set({ activeView: view }),

  setIsAnalyzing: (v) => set({ isAnalyzing: v }),
  setError: (msg) => set({ error: msg }),

  setHighlightedNodeIds: (ids) => set({ highlightedNodeIds: ids }),

  reset: () => set(initialState),
}));
