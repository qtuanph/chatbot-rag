"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Badge } from "@/components/ui/badge";
import type { Node } from "@xyflow/react";

type TreeNodeData = {
  label: string;
  level: number;
  childCount: number;
  textLength: number;
};

type TreeNodeType = Node<TreeNodeData, "treeNode">;

const levelColors: Record<number, string> = {
  0: "bg-slate-100 dark:bg-slate-800 border-slate-300 dark:border-slate-600",
  1: "bg-blue-50 dark:bg-blue-900/30 border-blue-300 dark:border-blue-700",
  2: "bg-green-50 dark:bg-green-900/30 border-green-300 dark:border-green-700",
  3: "bg-yellow-50 dark:bg-yellow-900/30 border-yellow-300 dark:border-yellow-700",
  4: "bg-purple-50 dark:bg-purple-900/30 border-purple-300 dark:border-purple-700",
};

export function DocumentTreeNode({ data }: NodeProps<TreeNodeType>) {
  const colorClass = levelColors[data.level] || levelColors[4];

  return (
    <div
      className={`px-3 py-2 rounded-lg border-2 ${colorClass} min-w-[120px] max-w-[220px]`}
    >
      <Handle type="target" position={Position.Top} className="!bg-muted-foreground" />
      <div className="text-xs font-medium truncate">{data.label || "Untitled"}</div>
      <div className="flex items-center gap-1 mt-1">
        <Badge variant="outline" className="text-[9px] px-1 py-0">
          L{data.level}
        </Badge>
        {data.childCount > 0 && (
          <Badge variant="secondary" className="text-[9px] px-1 py-0">
            {data.childCount} con
          </Badge>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-muted-foreground" />
    </div>
  );
}

export const treeNodeTypes = {
  treeNode: DocumentTreeNode,
};
