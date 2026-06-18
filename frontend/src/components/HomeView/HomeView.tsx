import React, { useState, useEffect, useRef } from 'react';
import { Github, ArrowRight, Loader2, CheckCircle2, AlertCircle, Info } from 'lucide-react';
import { analyzeRepo, getRepoStatus, getRepoTree, getDepsGraph } from '../../services/api';
import { useRepoStore } from '../../store/repoStore';
import { STATUS_LABELS } from '../../types';
import type { AnalysisStatus } from '../../types';
import './HomeView.css';

const EXAMPLE_REPOS = [
  'https://github.com/tiangolo/fastapi',
  'https://github.com/pallets/flask',
  'https://github.com/psf/requests',
  'https://github.com/scrapy/scrapy',
];

export function HomeView() {
  const [url, setUrl] = useState('');
  const [localError, setLocalError] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const {
    currentRepo, setCurrentRepo, updateRepoStatus,
    setGraphData, setFileTree, setActiveView, setIsAnalyzing, isAnalyzing,
  } = useRepoStore();

  // Clean up polling on unmount
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const startPolling = (repoId: string) => {
    pollRef.current = setInterval(async () => {
      try {
        const status = await getRepoStatus(repoId);
        setCurrentRepo(status);
        updateRepoStatus(status.status);

        if (status.status === 'complete') {
          stopPolling();
          setIsAnalyzing(false);
          // Pre-fetch graph + tree
          try {
            const [graphData, treeData] = await Promise.all([
              getDepsGraph(repoId),
              getRepoTree(repoId),
            ]);
            setGraphData(graphData);
            setFileTree(treeData.file_tree);
          } catch { /* non-fatal */ }
        } else if (status.status === 'failed') {
          stopPolling();
          setIsAnalyzing(false);
          setLocalError('Analysis failed. Please try again.');
        }
      } catch {
        stopPolling();
        setIsAnalyzing(false);
      }
    }, 2500);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError('');
    const trimmed = url.trim();
    if (!trimmed) return;

    setIsAnalyzing(true);
    try {
      const response = await analyzeRepo(trimmed);
      // If already complete, just fetch the status
      const status = await getRepoStatus(response.repo_id);
      setCurrentRepo(status);

      if (status.status === 'complete') {
        setIsAnalyzing(false);
        const [graphData, treeData] = await Promise.all([
          getDepsGraph(response.repo_id),
          getRepoTree(response.repo_id),
        ]);
        setGraphData(graphData);
        setFileTree(treeData.file_tree);
      } else {
        startPolling(response.repo_id);
      }
    } catch (err: unknown) {
      setIsAnalyzing(false);
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setLocalError(msg || 'Failed to start analysis. Check the URL and try again.');
    }
  };

  const statusPhase = currentRepo?.status;
  const isRunning = statusPhase && statusPhase !== 'complete' && statusPhase !== 'failed';

  return (
    <div className="home-view">
      {/* Hero */}
      <div className="home-hero fade-in">
        <div className="hero-badge">
          <span className="hero-badge-dot" />
          Graph-RAG · No LLMs · Deterministic
        </div>
        <h1 className="hero-title">
          Understand Any
          <span className="hero-accent"> Codebase</span>
        </h1>
        <p className="hero-description">
          Analyze GitHub repositories with AST parsing, dependency graphs, semantic embeddings,
          and vector retrieval — without a single LLM call.
        </p>
      </div>

      {/* Input card */}
      <div className="home-card fade-in">
        <form onSubmit={handleSubmit} className="analyze-form">
          <div className="input-group">
            <Github size={18} className="input-icon" />
            <input
              id="repo-url-input"
              className="input repo-input"
              type="url"
              placeholder="https://github.com/owner/repository"
              value={url}
              onChange={(e) => { setUrl(e.target.value); setLocalError(''); }}
              disabled={isAnalyzing}
            />
          </div>
          <button
            id="analyze-btn"
            type="submit"
            className="btn btn-primary analyze-btn"
            disabled={isAnalyzing || !url.trim()}
          >
            {isAnalyzing ? (
              <>
                <Loader2 size={16} className="spin-icon" />
                Analyzing...
              </>
            ) : (
              <>
                Analyze Repository
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </form>

        {/* Error */}
        {localError && (
          <div className="alert alert-error fade-in">
            <AlertCircle size={15} />
            {localError}
          </div>
        )}

        {/* Status progress */}
        {currentRepo && (
          <div className="analysis-status fade-in">
            <div className="status-header">
              {currentRepo.status === 'complete' ? (
                <CheckCircle2 size={16} className="status-icon success" />
              ) : currentRepo.status === 'failed' ? (
                <AlertCircle size={16} className="status-icon error" />
              ) : (
                <div className="spinner" style={{ width: 16, height: 16 }} />
              )}
              <span className="status-text">
                {STATUS_LABELS[currentRepo.status as AnalysisStatus]}
              </span>
            </div>

            {/* Progress bar */}
            <div className="progress-track">
              <div
                className={`progress-bar ${currentRepo.status === 'complete' ? 'complete' : 'running'}`}
                style={{
                  width: `${getProgressPct(currentRepo.status as AnalysisStatus)}%`,
                }}
              />
            </div>

            {/* Pipeline stages */}
            <div className="pipeline-stages">
              {PIPELINE_STAGES.map((stage) => (
                <div
                  key={stage.id}
                  className={`pipeline-stage ${getStageCls(stage.id, currentRepo.status as AnalysisStatus)}`}
                >
                  <div className="stage-dot" />
                  <span>{stage.label}</span>
                </div>
              ))}
            </div>

            {/* CTA when complete */}
            {currentRepo.status === 'complete' && (
              <div className="complete-actions fade-in">
                <div className="complete-info">
                  <Info size={14} />
                  <span>
                    {currentRepo.python_files} Python files analyzed across {currentRepo.total_files} total files
                  </span>
                </div>
                <div className="complete-btns">
                  <button className="btn btn-primary btn-sm" onClick={() => setActiveView({ type: 'deps' })}>
                    View Dependency Graph →
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => setActiveView({ type: 'search' })}>
                    Semantic Search
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Examples */}
      {!currentRepo && (
        <div className="examples fade-in">
          <p className="examples-label">Try an example:</p>
          <div className="examples-list">
            {EXAMPLE_REPOS.map((repo) => (
              <button
                key={repo}
                className="example-chip"
                onClick={() => setUrl(repo)}
              >
                {repo.replace('https://github.com/', '')}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Feature grid */}
      {!currentRepo && (
        <div className="features-grid fade-in">
          {FEATURES.map((f) => (
            <div key={f.title} className="feature-card">
              <div className="feature-icon" style={{ background: f.color }}>{f.icon}</div>
              <h4>{f.title}</h4>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────

const PIPELINE_STAGES = [
  { id: 'cloning',       label: 'Clone' },
  { id: 'parsing',       label: 'Parse' },
  { id: 'building_graph', label: 'Graph' },
  { id: 'embedding',     label: 'Embed' },
  { id: 'indexing',      label: 'Index' },
  { id: 'complete',      label: 'Done' },
];

const STAGE_ORDER: AnalysisStatus[] = [
  'pending', 'cloning', 'parsing', 'building_graph', 'embedding', 'indexing', 'complete',
];

function getStageCls(stageId: string, currentStatus: AnalysisStatus): string {
  const stageIdx = STAGE_ORDER.indexOf(stageId as AnalysisStatus);
  const currentIdx = STAGE_ORDER.indexOf(currentStatus);
  if (stageIdx < currentIdx) return 'done';
  if (stageIdx === currentIdx) return 'active';
  return '';
}

function getProgressPct(status: AnalysisStatus): number {
  const map: Record<AnalysisStatus, number> = {
    pending: 5, cloning: 15, parsing: 35, building_graph: 55,
    embedding: 75, indexing: 90, complete: 100, failed: 0,
  };
  return map[status] ?? 0;
}

const FEATURES = [
  { title: 'Dependency Graph', desc: 'Visualize file import chains and module dependencies.', icon: '⬡', color: 'rgba(251,146,60,0.15)' },
  { title: 'Call Graph', desc: 'Trace function call chains and execution paths.', icon: '→', color: 'rgba(56,189,248,0.15)' },
  { title: 'Semantic Search', desc: 'Find relevant code using natural language queries.', icon: '◎', color: 'rgba(124,107,255,0.15)' },
  { title: 'Impact Analysis', desc: 'Know what breaks before you make a change.', icon: '⚡', color: 'rgba(239,68,68,0.15)' },
];
