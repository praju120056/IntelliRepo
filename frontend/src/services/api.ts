import axios from 'axios';
import type {
  AnalyzeResponse,
  RepoStatusResponse,
  GraphData,
  SearchRequest,
  SearchResponse,
  QueryRequest,
  QueryResponse,
} from '../types';

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 120_000,
});

// ── Repository ────────────────────────────────────────────────────

export const analyzeRepo = (url: string): Promise<AnalyzeResponse> =>
  api.post('/repos/analyze', { url }).then(r => r.data);

export const getRepoStatus = (repoId: string): Promise<RepoStatusResponse> =>
  api.get(`/repos/${repoId}`).then(r => r.data);

export const getRepoTree = (repoId: string) =>
  api.get(`/repos/${repoId}/tree`).then(r => r.data);

export const listRepos = () =>
  api.get('/repos').then(r => r.data);

export const deleteRepo = (repoId: string): Promise<void> =>
  api.delete(`/repos/${repoId}`).then(() => undefined);

// ── Graph ─────────────────────────────────────────────────────────

export const getFullGraph = (repoId: string): Promise<GraphData> =>
  api.get(`/repos/${repoId}/graph`).then(r => r.data);

export const getDepsGraph = (repoId: string): Promise<GraphData> =>
  api.get(`/repos/${repoId}/graph/deps`).then(r => r.data);

export const getCallGraph = (repoId: string): Promise<GraphData> =>
  api.get(`/repos/${repoId}/graph/calls`).then(r => r.data);

export const getNodeContext = (repoId: string, nodeId: string, depth = 2) =>
  api.get(`/repos/${repoId}/graph/node/${encodeURIComponent(nodeId)}`, { params: { depth } }).then(r => r.data);

export const getGraphStats = (repoId: string) =>
  api.get(`/repos/${repoId}/graph/stats`).then(r => r.data);

// ── Search ────────────────────────────────────────────────────────

export const semanticSearch = (repoId: string, body: SearchRequest): Promise<SearchResponse> =>
  api.post(`/repos/${repoId}/search`, body).then(r => r.data);

// ── Query ─────────────────────────────────────────────────────────

export const executeQuery = (repoId: string, body: QueryRequest): Promise<QueryResponse> =>
  api.post(`/repos/${repoId}/query`, body).then(r => r.data);

export default api;
