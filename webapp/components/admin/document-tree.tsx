"use client";

import { useMemo, useState, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { treeNodeTypes } from "@/components/admin/tree-node";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Search } from "lucide-react";
import type { TreeNode as TreeNodeType } from "@/types/api";

interface DocumentTreeProps {
  nodes: TreeNodeType[];
  documentTitle: string;
  maxDepth: number;
  onNodeClick?: (nodeId: string) => void;
}

function buildFlowData(treeNodes: TreeNodeType[]) {
  const nodeMap = new Map<string, TreeNodeType>();
  const childrenMap = new Map<string, string[]>();

  treeNodes.forEach((n) => {
    nodeMap.set(n.node_id, n);
    if (!childrenMap.has(n.node_id)) childrenMap.set(n.node_id, []);
  });

  treeNodes.forEach((n) => {
    if (n.parent_id && nodeMap.has(n.parent_id)) {
      const siblings = childrenMap.get(n.parent_id) || [];
      siblings.push(n.node_id);
      childrenMap.set(n.parent_id, siblings);
    }
  });

  // Build layout positions using simple tree layout
  const flowNodes: Node[] = [];
  const flowEdges: Edge[] = [];
  const Y_SPACING = 100;
  const X_SPACING = 240;

  function layoutSubtree(nodeId: string, x: number, y: number): number {
    const treeNode = nodeMap.get(nodeId);
    if (!treeNode) return x;

    const children = childrenMap.get(nodeId) || [];

    flowNodes.push({
      id: nodeId,
      type: "treeNode",
      position: { x: 0, y }, // Will be updated
      data: {
        label: treeNode.title,
        level: treeNode.level,
        childCount: treeNode.child_count,
        textLength: treeNode.text_length,
      },
    });

    if (children.length === 0) {
      // Leaf node: position at current x
      flowNodes[flowNodes.length - 1].position = { x, y };
      return x + X_SPACING;
    }

    // Layout children first to calculate width
    let childX = x;
    const childY = y + Y_SPACING;
    for (const childId of children) {
      childX = layoutSubtree(childId, childX, childY);
    }

    // Center parent over children
    const firstChild = flowNodes.find((n) => n.id === children[0]);
    const lastChild = flowNodes.find((n) => n.id === children[children.length - 1]);
    if (firstChild && lastChild) {
      const centerX = (firstChild.position.x + lastChild.position.x) / 2;
      flowNodes[flowNodes.length - 1].position = { x: centerX, y };
    }

    // Add edges from parent to children
    for (const childId of children) {
      flowEdges.push({
        id: `${nodeId}-${childId}`,
        source: nodeId,
        target: childId,
        animated: false,
        style: { stroke: "hsl(var(--muted-foreground))", strokeWidth: 1 },
      });
    }

    return childX;
  }

  // Find root nodes (no parent)
  const roots = treeNodes.filter((n) => !n.parent_id);
  let currentX = 0;
  for (const root of roots) {
    currentX = layoutSubtree(root.node_id, currentX, 0);
  }

  return { flowNodes, flowEdges };
}

export function DocumentTree({
  nodes,
  maxDepth,
  onNodeClick,
}: DocumentTreeProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const { flowNodes, flowEdges } = useMemo(
    () => buildFlowData(nodes),
    [nodes],
  );

  const [displayNodes, setDisplayNodes] = useNodesState(flowNodes);
  const [displayEdges] = useEdgesState(flowEdges);

  // Update nodes when search changes
  useMemo(() => {
    if (!searchQuery.trim()) {
      setDisplayNodes(flowNodes);
      return;
    }

    const q = searchQuery.toLowerCase();
    const matchedIds = new Set(
      nodes
        .filter(
          (n) =>
            n.title.toLowerCase().includes(q) ||
            n.breadcrumb.toLowerCase().includes(q),
        )
        .map((n) => n.node_id),
    );

    setDisplayNodes(
      flowNodes.map((n) => ({
        ...n,
        style: matchedIds.has(n.id)
          ? {
              ...n.style,
              boxShadow: "0 0 0 2px hsl(var(--primary))",
              opacity: 1,
            }
          : { ...n.style, opacity: matchedIds.size > 0 ? 0.3 : 1 },
      })),
    );
  }, [searchQuery, flowNodes, nodes, setDisplayNodes]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeClick?.(node.id);
    },
    [onNodeClick],
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Tìm kiếm node..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8"
          />
        </div>
        <Badge variant="outline">
          {nodes.length} nodes
        </Badge>
        <Badge variant="outline">
          Độ sâu {maxDepth}
        </Badge>
      </div>

      <div className="border rounded-lg" style={{ height: 500 }}>
        <ReactFlow
          nodes={displayNodes}
          edges={displayEdges}
          nodeTypes={treeNodeTypes}
          onNodeClick={handleNodeClick}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.1}
          maxZoom={2}
        >
          <Background />
          <Controls />
          <MiniMap
            nodeStrokeWidth={3}
            pannable
            zoomable
          />
        </ReactFlow>
      </div>
    </div>
  );
}
