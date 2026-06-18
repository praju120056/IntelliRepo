import React, { useState } from 'react';
import { Search, Filter, Loader2, ChevronRight } from 'lucide-react';
import { semanticSearch, executeQuery } from '../../services/api';
import { useRepoStore } from '../../store/repoStore';
import type { QueryType, SearchResultNode } from '../../types';
import './SearchView.css';

type SearchMode = 'semantic' | QueryType;

const SEARCH_MODES: { id: SearchMode; label: string; desc: string }[] = [
  { id: 'semantic', label: 'Semantic Search', desc: 'Natural language — find relevant code' },
  { id: 'callers_of', label: 'Callers Of', desc: 'What functions call X?' },
  { id: 'dependencies_of', label: 'Dependencies Of', desc: 'What files does Y import?' },
  { id: 'importers_of', label: 'Importers Of', desc: 'What files import module Z?' },
  { id: 'call_chain', label: 'Call Chain', desc: 'Execution path from function' },
  { id: 'impact_of', label: 'Impact Analysis', desc: 'What breaks if I modify file A?' },
];

const TYPE_COLORS: Record<string, string> = {
  function: 'badge-function',
  class: 'badge-class',
  file: 'badge-file',
  repository: 'badge-repo',
};

export function SearchView() {
  const { currentRepo, setSearchResults, setQueryResults, setHighlightedNodeIds, isSearching, setIsSearching } = useRepoStore();
  const [mode, setMode] = useState<SearchMode>('semantic');
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(10);
  const [results, setResults] = useState<SearchResultNode[]>([]);
  const [explanation, setExplanation] = useState('');
  const [error, setError] = useState('');

  const repoId = currentRepo?.repo_id;

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || !repoId) return;

    setIsSearching(true);
    setError('');
    setResults([]);
    setExplanation('');

    try {
      if (mode === 'semantic') {
        const res = await semanticSearch(repoId, { query, top_k: topK, expand: true });
        const allNodes = [...res.seed_nodes, ...res.expanded_nodes];
        setResults(allNodes);
        setExplanation(res.explanation);
        setSearchResults(res);
        setHighlightedNodeIds(new Set(allNodes.map((n) => n.id)));
      } else {
        const res = await executeQuery(repoId, { type: mode, target: query, depth: 4 });
        const allNodes = res.nodes.map((n) => ({
          id: n.id,
          type: n.type || 'unknown',
          name: n.name || n.label || n.id,
          file_path: n.file_path || n.path || '',
          start_line: n.start_line,
          end_line: n.end_line,
          docstring: n.docstring,
          score: 1.0,
          origin: 'semantic' as const,
        }));
        setResults(allNodes);
        setExplanation(res.explanation);
        setQueryResults(res);
        setHighlightedNodeIds(new Set(allNodes.map((n) => n.id)));
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Search failed. Please try again.');
    } finally {
      setIsSearching(false);
    }
  };

  const placeholder = mode === 'semantic'
    ? 'e.g. "authentication logic" or "database connection"'
    : SEARCH_MODES.find((m) => m.id === mode)?.desc || '';

  return (
    <div className="search-view">
      {/* Header */}
      <div className="search-header">
        <h2>Query Engine</h2>
        <p>Graph traversal + semantic search — no LLMs</p>
      </div>

      <div className="search-body">
        {/* Left: Query panel */}
        <div className="search-panel">
          {/* Mode tabs */}
          <div className="mode-tabs">
            {SEARCH_MODES.map((m) => (
              <button
                key={m.id}
                className={`mode-tab ${mode === m.id ? 'active' : ''}`}
                onClick={() => { setMode(m.id); setResults([]); setExplanation(''); }}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Search form */}
          <form onSubmit={handleSearch} className="search-form">
            <div className="search-input-row">
              <Search size={16} className="search-icon" />
              <input
                id="query-input"
                className="input search-input"
                type="text"
                placeholder={placeholder}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={isSearching}
              />
            </div>
            {mode === 'semantic' && (
              <div className="search-options">
                <label className="option-label">
                  Results:
                  <select
                    className="input option-select"
                    value={topK}
                    onChange={(e) => setTopK(Number(e.target.value))}
                  >
                    {[5, 10, 20, 30].map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </label>
              </div>
            )}
            <button
              id="search-btn"
              type="submit"
              className="btn btn-primary"
              disabled={isSearching || !query.trim()}
            >
              {isSearching ? <Loader2 size={15} className="spin-icon" /> : <Search size={15} />}
              {isSearching ? 'Searching...' : 'Search'}
            </button>
          </form>

          {error && <div className="search-error">{error}</div>}
        </div>

        {/* Right: Results */}
        <div className="results-panel">
          {explanation && (
            <div className="explanation-box fade-in">
              <div className="explanation-label">Explanation</div>
              <p>{explanation}</p>
            </div>
          )}

          {results.length > 0 && (
            <div className="results-count fade-in">
              {results.length} result{results.length !== 1 ? 's' : ''}
            </div>
          )}

          <div className="results-list">
            {results.map((node) => (
              <div key={node.id} className="result-card fade-in">
                <div className="result-header">
                  <span className={`badge ${TYPE_COLORS[node.type] || 'badge-file'}`}>
                    {node.type}
                  </span>
                  {node.score < 1 && (
                    <span className="result-score">{(node.score * 100).toFixed(0)}% match</span>
                  )}
                  {node.origin === 'graph_expansion' && (
                    <span className="result-origin">graph context</span>
                  )}
                </div>
                <div className="result-name">{node.name}</div>
                {node.file_path && (
                  <div className="result-path">
                    {node.file_path}
                    {node.start_line != null && <span className="result-lines"> L{node.start_line}–{node.end_line}</span>}
                  </div>
                )}
                {node.docstring && (
                  <div className="result-doc">{node.docstring.slice(0, 120)}{node.docstring.length > 120 ? '…' : ''}</div>
                )}
              </div>
            ))}
          </div>

          {!isSearching && results.length === 0 && !explanation && (
            <div className="empty-state">
              <Search size={36} />
              <p>Enter a query above to search the repository.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
