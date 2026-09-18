import { Lightbulb, Info } from "lucide-react";

import { formatMinutes } from "@/lib/format";
import type { CurriculumDetailRead, CurriculumUnitRead, TopicRead } from "@/lib/types";

interface AIInsightPanelProps {
  curriculum?: CurriculumDetailRead | null;
  topics?: TopicRead[];
  selectedUnit?: CurriculumUnitRead | null;
}

export function AIInsightPanel({ curriculum, topics, selectedUnit }: AIInsightPanelProps) {
  if (!curriculum) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-muted/30 p-6 text-center">
        <Info className="mx-auto h-6 w-6 text-muted-foreground/60" />
        <p className="mt-2 text-sm text-muted-foreground">
          No curriculum loaded — generate one from a document workspace to see insights.
        </p>
      </div>
    );
  }

  const units = curriculum.units;
  const total = units.reduce((a, u) => a + (u.estimated_workload_minutes || 0), 0);
  const avg = units.length ? Math.round(total / units.length) : 0;
  const minW = units.length ? Math.min(...units.map((u) => u.estimated_workload_minutes)) : 0;
  const maxW = units.length ? Math.max(...units.map((u) => u.estimated_workload_minutes)) : 0;

  const uniqueTopics = new Set<string>();
  units.forEach((u) => u.topics.forEach((t) => uniqueTopics.add(t.title)));

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <Lightbulb className="h-4 w-4 text-amber-500" />
        Curriculum intelligence
      </div>

      <div className="grid grid-cols-2 gap-3 text-center">
        <InsightStat value={curriculum.total_weeks} label="Weeks" />
        <InsightStat value={formatMinutes(total)} label="Total workload" />
        <InsightStat value={formatMinutes(avg)} label="Avg / week" />
        <InsightStat value={uniqueTopics.size} label="Unique topics" />
        <InsightStat value={`${curriculum.learning_days_per_week}d/wk`} label="Learning days" />
        <InsightStat value={`${curriculum.hours_per_day}h/day`} label="Daily hours" />
      </div>

      <div className="rounded-lg border border-amber-100 bg-amber-50 p-3 text-xs text-amber-800">
        <strong>Workload spread:</strong> {formatMinutes(minW)} to {formatMinutes(maxW)} per week —
        {maxW > minW * 2
          ? " consider rebalancing as the variance is significant."
          : " the workload distribution is well-balanced."}
      </div>

      {selectedUnit && selectedUnit.topics.length > 0 && (
        <div className="rounded-lg border border-burgundy/15 bg-burgundy-50/60 p-3 text-xs text-burgundy-900">
          <strong>Week {selectedUnit.week_number}:</strong> {selectedUnit.topics.length} topic{selectedUnit.topics.length !== 1 && "s"} covering{" "}
          {selectedUnit.topics.map((t) => t.title).join(", ")}.
        </div>
      )}

      {topics && topics.length > 0 && (
        <div className="text-[11px] text-muted-foreground">
          Source topics: {topics.length} analyzed with{" "}
          {topics.reduce((a, t) => a + t.concepts.length, 0)} concepts extracted.
        </div>
      )}
    </div>
  );
}

function InsightStat({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="rounded-lg bg-muted/40 px-2 py-2">
      <div className="text-base font-bold text-foreground">{value}</div>
      <div className="text-[10px] text-muted-foreground">{label}</div>
    </div>
  );
}