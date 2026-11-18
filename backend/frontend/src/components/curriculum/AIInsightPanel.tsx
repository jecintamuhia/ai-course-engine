import { Sparkles, Info } from "lucide-react";

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
    <div className="flex flex-col gap-4 rounded-xl border border-ai/15 bg-card p-4 shadow-card">
      <div className="relative overflow-hidden">
        <span
          aria-hidden
          className="pointer-events-none absolute right-2 top-0 h-16 w-16 rounded-full bg-ai/[0.07] blur-2xl"
        />
        <div className="relative inline-flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-ai/10 text-ai">
            <Sparkles className="h-3.5 w-3.5" />
          </span>
          <div>
            <div className="text-sm font-semibold text-ink">Curriculum intelligence</div>
            <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-ai">
              AI-generated planning view
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2.5">
        <InsightStat value={curriculum.total_weeks} label="Weeks" />
        <InsightStat value={formatMinutes(total)} label="Total workload" />
        <InsightStat value={formatMinutes(avg)} label="Avg / week" />
        <InsightStat value={uniqueTopics.size} label="Unique topics" />
        <InsightStat value={`${curriculum.learning_days_per_week}d/wk`} label="Learning days" />
        <InsightStat value={`${curriculum.hours_per_day}h/day`} label="Daily hours" />
      </div>

      <div className="rounded-lg border border-amber-100 bg-amber-50 p-3 text-xs leading-relaxed text-amber-800">
        <strong className="font-semibold">Workload spread:</strong> {formatMinutes(minW)} to{" "}
        {formatMinutes(maxW)} per week —
        {maxW > minW * 2
          ? " consider rebalancing as the variance is significant."
          : " the workload distribution is well-balanced."}
      </div>

      {selectedUnit && selectedUnit.topics.length > 0 && (
        <div className="rounded-lg border border-brand/15 bg-brand-50/60 p-3 text-xs leading-relaxed text-brand-900">
          <strong className="font-semibold">Week {selectedUnit.week_number}:</strong>{" "}
          {selectedUnit.topics.length} topic{selectedUnit.topics.length !== 1 && "s"} covering{" "}
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
    <div className="rounded-lg bg-sand-100/70 px-2 py-2.5 text-center">
      <div className="tnum text-base font-bold text-ink">{value}</div>
      <div className="mt-0.5 text-[10px] font-medium text-muted-foreground">{label}</div>
    </div>
  );
}