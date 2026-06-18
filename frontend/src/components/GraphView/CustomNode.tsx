import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { NodeType } from '../../types';

interface CustomNodeData {
  type: NodeType;
  name?: string;
  label?: string;
  file_path?: string;
  path?: string;
  borderColor: string;
  highlighted: boolean;
  start_line?: number;
  end_line?: number;
}

const TYPE_ICONS: Record<NodeType, string> = {
  repository: '◈',
  file: '▣',
  class: '◉',
  function: '▶',
};

export const CustomNode = memo(({ data }: NodeProps) => {
  const d = data as CustomNodeData;
  const displayName = d.name || d.label || d.path || 'unknown';
  const filePath = d.file_path || d.path || '';
  const icon = TYPE_ICONS[d.type] || '·';

  const truncate = (s: string, max: number) =>
    s.length > max ? `…${s.slice(-max + 1)}` : s;

  return (
    <div
      className={`custom-node type-${d.type} ${d.highlighted ? 'highlighted' : ''}`}
      style={{ '--node-color': d.borderColor } as React.CSSProperties}
    >
      <Handle type="target" position={Position.Top} className="node-handle" />

      <div className="node-header">
        <span className="node-icon">{icon}</span>
        <span className="node-type-label">{d.type}</span>
      </div>

      <div className="node-name" title={displayName}>
        {truncate(displayName, 22)}
      </div>

      {filePath && d.type !== 'file' && d.type !== 'repository' && (
        <div className="node-file" title={filePath}>
          {truncate(filePath, 28)}
        </div>
      )}

      {d.start_line != null && (
        <div className="node-lines">L{d.start_line}–{d.end_line}</div>
      )}

      <Handle type="source" position={Position.Bottom} className="node-handle" />
    </div>
  );
});

CustomNode.displayName = 'CustomNode';
