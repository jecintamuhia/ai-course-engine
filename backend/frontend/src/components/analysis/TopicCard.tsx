import { Target, Clock, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";
import { formatMinutes } from "@/lib/format";
import type { TopicRead } from "@/lib/types";

const difficultyLabels: Record<number, string> = {
  1: "Foundational",
  2: "Introductory",
  3: "Intermediate",
  4: "Advanced",
  5: "Expert",
};

const difficultyColors: Record<number, string> = {
  1: "bg-emerald-50 text-emerald-700 border-emerald-200",
  2: "bg-blue-50 text-blue-700 border-blue-200",
  3: "bg-amber-50 text-amber-700 border-amber-200",
  4: "bg-orange-50 text-orange-700 border-orange-200",
  5: "bg-red-50 text-red-700 border-red-200",
};

interface TopicCardProps {
  topic: TopicRead;
  selected?: boolean;
  onClick?: () => void;
}

export function TopicCard({ topic, selected = false, onClick }: TopicCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group w-full text-left rounded-lg border p-4 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2",
        selected
          ? "border-brand/50 bg-brand-50 shadow-sm ring-1 ring-brand/20"
          : "border-border bg-card hover:border-brand/30 hover:bg-brand-50/50",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-foreground line-clamp-2">{topic.title}</h3>
          <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatMinutes(topic.estimated_workload_minutes)}
            </span>
            <span aria-hidden className="text-border">·</span>
            <span className={cn("inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium", difficultyColors[topic.difficulty])}>
              {difficultyLabels[topic.difficulty] ?? `Level ${topic.difficulty}`}
            </span>
          </div>
        </div>
        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      </div>

      {topic.learning_objectives.length > 0 && (
        <div className="mt-2.5">
          <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
            <Target className="h-3 w-3" />
            Learning objectives
          </div>
          <ul className="mt-1 space-y-0.5 pl-1">
            {topic.learning_objectives.slice(0, 3).map((obj) => (
              <li key={obj} className="text-xs text-foreground/80 line-clamp-1">
                {obj}
              </li>
            ))}
          </ul>
          {topic.learning_objectives.length > 3 && (
            <div className="mt-1 text-[11px] text-muted-foreground">
              +{topic.learning_objectives.length - 3} more
            </div>
          )}
        </div>
      )}

      {topic.prerequisite_titles.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1">
          <span className="text-[10px] uppercase font-semibold tracking-wide text-muted-foreground mr-1">Prereqs:</span>
          {topic.prerequisite_titles.map((pre) => (
            <span key={pre} className="inline-block rounded-md bg-sand-200 px-1.5 py-0.5 text-[10px] font-medium text-brand-900">
              {pre}
            </span>
          ))}
        </div>
      )}

      {topic.concepts.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1">
          {topic.concepts.slice(0, 4).map((c) => (
            <span key={c.id} className="inline-block rounded-full bg-secondary/80 px-2 py-0.5 text-[10px] font-medium text-secondary-foreground">
              {c.name}
            </span>
          ))}
          {topic.concepts.length > 4 && (
            <span className="inline-block rounded-full bg-secondary/60 px-2 py-0.5 text-[10px] text-muted-foreground">
              +{topic.concepts.length - 4}
            </span>
          )}
        </div>
      )}
    </button>
  );
}