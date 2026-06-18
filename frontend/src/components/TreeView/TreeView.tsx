import React, { useState } from 'react';
import { ChevronRight, ChevronDown, File, Folder, Code } from 'lucide-react';
import { useRepoStore } from '../../store/repoStore';
import type { FileNode } from '../../types';
import './TreeView.css';

interface TreeNode {
  name: string;
  path: string;
  isDir: boolean;
  language?: string;
  lines?: number;
  children: TreeNode[];
}

function buildTree(files: FileNode[]): TreeNode[] {
  const root: TreeNode = { name: '', path: '', isDir: true, children: [] };

  for (const file of files) {
    const parts = file.path.split('/');
    let current = root;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLast = i === parts.length - 1;
      const childPath = parts.slice(0, i + 1).join('/');

      let child = current.children.find((c) => c.name === part);
      if (!child) {
        child = {
          name: part,
          path: childPath,
          isDir: !isLast,
          language: isLast ? file.language : undefined,
          lines: isLast ? file.lines : undefined,
          children: [],
        };
        current.children.push(child);
      }
      current = child;
    }
  }

  // Sort: dirs first, then files
  const sortNodes = (nodes: TreeNode[]): TreeNode[] => {
    nodes.forEach((n) => sortNodes(n.children));
    return nodes.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
  };

  return sortNodes(root.children);
}

const LANG_COLORS: Record<string, string> = {
  python: 'var(--color-function)',
  javascript: '#f7df1e',
  typescript: '#3178c6',
  markdown: '#94a3b8',
  json: '#fb923c',
};

function TreeNodeItem({ node, depth }: { node: TreeNode; depth: number }) {
  const [open, setOpen] = useState(depth < 1);
  const indent = depth * 14;

  if (node.isDir) {
    return (
      <div>
        <button
          className="tree-item tree-dir"
          style={{ paddingLeft: 12 + indent }}
          onClick={() => setOpen(!open)}
        >
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          <Folder size={13} className="tree-icon dir-icon" />
          <span>{node.name}</span>
        </button>
        {open && (
          <div>
            {node.children.map((child) => (
              <TreeNodeItem key={child.path} node={child} depth={depth + 1} />
            ))}
          </div>
        )}
      </div>
    );
  }

  const dotColor = LANG_COLORS[node.language || ''] || 'var(--text-muted)';

  return (
    <div
      className="tree-item tree-file"
      style={{ paddingLeft: 12 + indent + 16 }}
      title={node.path}
    >
      <div className="lang-dot" style={{ background: dotColor }} />
      <File size={12} className="tree-icon file-icon" />
      <span className="file-name">{node.name}</span>
      {node.lines != null && node.lines > 0 && (
        <span className="file-lines">{node.lines}L</span>
      )}
    </div>
  );
}

export function TreeView() {
  const { fileTree, currentRepo } = useRepoStore();

  if (!fileTree || fileTree.length === 0) {
    return (
      <div className="tree-view">
        <div className="tree-header">
          <h2>File Tree</h2>
        </div>
        <div className="empty-state">
          <p>File tree not yet loaded.</p>
        </div>
      </div>
    );
  }

  const tree = buildTree(fileTree as FileNode[]);

  return (
    <div className="tree-view">
      <div className="tree-header">
        <h2>File Tree</h2>
        <div className="tree-meta">
          <span>{currentRepo?.python_files} Python</span>
          <span>·</span>
          <span>{currentRepo?.total_files} total</span>
        </div>
      </div>
      <div className="tree-body">
        {tree.map((node) => (
          <TreeNodeItem key={node.path} node={node} depth={0} />
        ))}
      </div>
    </div>
  );
}
