import { useMemo, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { TopicRead, DependencyGraphResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const NODE_WIDTH = 180;
const NODE_HEIGHT = 54;

interface DependencyGraphProps {
  topics: TopicRead[];
  graph: DependencyGraphResponse;
  selectedTopicId?: string | null;
  onSelectTopic?: (topicId: string) => void;
  className?: string;
}

function topicById(topics: TopicRead[]): Map<string, TopicRead> {
  const map = new Map<string, TopicRead>();
  const walk = (list: TopicRead[]) => {
    for (const t of list) {
      map.set(t.id, t);
      if (t.subtopics?.length) walk(t.subtopics);
    }
  };
  walk(topics);
  return map;
}

const difficultyBg: Record<number, string> = {
  1: "#DCFCE7",
  2: "#DBEAFE",
  3: "#FEF3C7",
  4: "#FFEDD5",
  5: "#FEE2E2",
};

const difficultyBorder: Record<number, string> = {
  1: "#86EFAC",
  2: "#93C5FD",
  3: "#FCD34D",
  4: "#FDBA74",
  5: "#FCA5A5",
};

function CustomNode({ data }: { data: Record<string, unknown> }) {
  const title = (data.topicTitle as string) ?? "";
  const selected = (data.selected as boolean) ?? false;
  const difficulty = (data.difficulty as number) ?? 3;

  return (
    <div
      className={cn(
        "rounded-lg border px-3 py-2 shadow-sm transition-colors cursor-pointer",
        selected && "ring-2 ring-oxford ring-offset-2",
      )}
      style={{
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        background: selected ? "#EFF4FA" : difficultyBg[difficulty],
        borderColor: selected ? "#002147" : difficultyBorder[difficulty],
      }}
    >
      <div className="truncate text-xs font-semibold text-foreground">{title}</div>
      <div className="mt-1 truncate text-[10px] text-muted-foreground">
        Difficulty {difficulty}/5
      </div>
    </div>
  );
}

const nodeTypes = { topicNode: CustomNode };

export function DependencyGraph({
  topics,
  graph,
  selectedTopicId,
  onSelectTopic,
  className,
}: DependencyGraphProps) {
  const topicMap = useMemo(() => topicById(topics), [topics]);

  const nodes: Node[] = useMemo(() => {
    const levels = new Map<string, number>();
    graph.topological_order.forEach((id, idx) => levels.set(id, idx));
    const cols = Math.min(graph.topological_order.length, 8);

    return graph.topological_order.map((topicId) => {
      const topic = topicMap.get(topicId);
      const level = levels.get(topicId) ?? 0;
      const row = Math.floor(level / cols);
      const col = level % cols;
      return {
        id: topicId,
        type: "topicNode",
        position: {
          x: col * (NODE_WIDTH + 32) + 16,
          y: row * (NODE_HEIGHT + 40) + 16,
        },
        data: {
          topicTitle: topic?.title ?? topicId.slice(0, 8),
          difficulty: topic?.difficulty ?? 3,
          selected: selectedTopicId === topicId,
        },
      };
    });
  }, [graph.topological_order, topicMap, selectedTopicId]);

  const edges: Edge[] = useMemo(() => {
    const edgeSet = new Set<string>();
    const result: Edge[] = [];
    topics.forEach((topic) => {
      topic.prerequisite_titles.forEach((prereqTitle) => {
        for (const target of topics) {
          if (target.title === prereqTitle) {
            const key = `${target.id}->${topic.id}`;
            if (!edgeSet.has(key)) {
              edgeSet.add(key);
              result.push({
                id: key,
                source: target.id,
                target: topic.id,
                animated: true,
                type: "smoothstep",
style: { stroke: "#002147", strokeWidth: 1.5 },
              });
            }
          }
        }
      });
    });
    return result;
  }, [topics]);

  const [reactNodes, setNodes, onNodesChange] = useNodesState(nodes);
  const [reactEdges, setEdges, onEdgesChange] = useEdgesState(edges);

  // Sync with prop changes
  useMemo(() => {
    setNodes(nodes);
    setEdges(edges);
  }, [nodes, edges, setNodes, setEdges]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (node.id && onSelectTopic) onSelectTopic(node.id);
    },
    [onSelectTopic],
  );

  return (
    <div className={`relative h-[520px] w-full overflow-hidden rounded-xl border border-border bg-cream-50 ${className ?? ""}`}>
      <ReactFlow
        nodes={reactNodes}
        edges={reactEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{
          type: "smoothstep",
          style: { stroke: "#002147", strokeWidth: 1.5 },
          animated: true,
        }}
      >
        <Background color="#E4DCD2" gap={16} />
        <Controls
          className="rounded-lg border border-border bg-card shadow-sm"
          showInteractive={false}
        />
        <MiniMap
          nodeColor={(n) => difficultyBg[(n.data as { difficulty?: number }).difficulty ?? 3]}
          className="rounded-lg border border-border bg-card shadow-sm"
          maskColor="rgba(248, 243, 234, 0.7)"
        />
      </ReactFlow>
    </div>
  );
}