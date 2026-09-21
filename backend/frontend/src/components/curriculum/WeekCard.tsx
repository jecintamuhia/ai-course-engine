import { Clock, Target, BookOpen } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMinutes } from "@/lib/format";
import type { CurriculumUnitRead } from "@/lib/types";

interface WeekCardProps {
  unit: CurriculumUnitRead;
}

export function WeekCard({ unit }: WeekCardProps) {
  return (
    <Card className="border-oxford/20 bg-card">
      <CardHeader className="border-b border-border bg-oxford-50/60 pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">
            <span className="text-[11px] font-bold tabular-nums text-muted-foreground">WEEK {String(unit.week_number).padStart(2, "0")}</span>
            <span className="mx-2 text-border" aria-hidden>·</span>
            {unit.title}
          </CardTitle>
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-oxford-700">
            <Clock className="h-3.5 w-3.5" />
            {formatMinutes(unit.estimated_workload_minutes)}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-5 pt-5">
        {unit.description && (
          <p className="text-sm text-foreground/80">{unit.description}</p>
        )}

        {unit.topics.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <BookOpen className="h-3 w-3" />
              Topics
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {unit.topics.map((t) => (
                <span
                  key={t.topic_id}
                  className="inline-flex items-center rounded-md border border-oxford/20 bg-oxford-50 px-2.5 py-1 text-xs font-medium text-oxford-800"
                >
                  {t.title}
                </span>
              ))}
            </div>
          </div>
        )}

        {unit.learning_objectives.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <Target className="h-3 w-3" />
              Learning Objectives
            </div>
            <ul className="mt-2 space-y-1 pl-1">
              {unit.learning_objectives.map((obj) => (
                <li key={obj} className="flex items-start gap-2 text-sm text-foreground/80">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-oxford-600" />
                  {obj}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}