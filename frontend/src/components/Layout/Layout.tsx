import React, { useState } from 'react';
import { GitBranch, Search, Network, Share2, Home, ChevronRight, Trash2, Clock } from 'lucide-react';
import { useRepoStore } from '../../store/repoStore';
import type { ActiveView } from '../../types';
import './Layout.css';

interface NavItem {
  id: ActiveView['type'];
  label: string;
  icon: React.ReactNode;
  requiresRepo: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'home',   label: 'Repository',    icon: <Home size={16} />,    requiresRepo: false },
  { id: 'tree',   label: 'File Tree',     icon: <GitBranch size={16} />, requiresRepo: true },
  { id: 'deps',   label: 'Import Graph',  icon: <Network size={16} />, requiresRepo: true },
  { id: 'calls',  label: 'Call Graph',    icon: <Share2 size={16} />,  requiresRepo: true },
  { id: 'search', label: 'Semantic Search', icon: <Search size={16} />, requiresRepo: true },
];

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const { currentRepo, activeView, setActiveView, reset, setCurrentRepo } = useRepoStore();
  const isComplete = currentRepo?.status === 'complete';

  return (
    <div className="layout">
      {/* Sidebar */}
      <aside className="sidebar">
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="logo-icon">
            <Network size={18} strokeWidth={2.5} />
          </div>
          <div>
            <div className="logo-name">GitParse</div>
            <div className="logo-tagline">Repo Intelligence</div>
          </div>
        </div>

        {/* Repo info */}
        {currentRepo && (
          <div className="sidebar-repo-card">
            <div className="repo-card-header">
              <div className="status-dot-wrap">
                <div className={`status-dot ${
                  currentRepo.status === 'complete' ? 'complete' :
                  currentRepo.status === 'failed' ? 'error' :
                  currentRepo.status === 'pending' ? 'pending' : 'running'
                }`} />
              </div>
              <span className="repo-card-name">{currentRepo.name}</span>
            </div>
            <div className="repo-card-meta">
              <span>{currentRepo.python_files} Python files</span>
              <span>·</span>
              <span>{currentRepo.total_files} total</span>
            </div>
          </div>
        )}

        {/* Navigation */}
        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => {
            const disabled = item.requiresRepo && !isComplete;
            const active = activeView.type === item.id;
            return (
              <button
                key={item.id}
                className={`nav-item ${active ? 'active' : ''} ${disabled ? 'disabled' : ''}`}
                onClick={() => !disabled && setActiveView({ type: item.id })}
                disabled={disabled}
                title={disabled ? 'Complete analysis first' : item.label}
              >
                {item.icon}
                <span>{item.label}</span>
                {active && <ChevronRight size={14} className="nav-chevron" />}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-spacer" />

        {/* Footer actions */}
        {currentRepo && (
          <div className="sidebar-footer">
            <button
              className="btn btn-ghost btn-sm sidebar-clear"
              onClick={() => {
                reset();
              }}
            >
              <Trash2 size={14} />
              Clear session
            </button>
          </div>
        )}
      </aside>

      {/* Main content */}
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}
