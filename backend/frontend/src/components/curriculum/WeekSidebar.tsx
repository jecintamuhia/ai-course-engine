import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { formatMinutes } from "@/lib/format";
import type { CurriculumUnitRead } from "@/lib/types";
import { Check, Circle } from "lucide-react";

interface WeekSidebarProps {
  units: CurriculumUnitRead[];
  selectedWeek: number;
  onSelect: (weekNumber: number) => void;
}

export function WeekSidebar({ units, selectedWeek, onSelect }: WeekSidebarProps) {
  return (
    <div className="flex flex-col gap-1">
      <div className="mb-2 px-2 text-xs font-bold uppercase tracking-wider text-oxford-700">
        Weeks
      </div>
      <ScrollArea className="h-[calc(100vh-240px)] pr-1">
        <div className="flex flex-col gap-0.5">
          {units.map((unit) => {
            const active = unit.week_number === selectedWeek;
            return (
              <button
                key={unit.id}
                type="button"
                onClick={() => onSelect(unit.week_number)}
                className={cn(
                  "group flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm font-medium transition-colors",
                  active
                    ? "bg-oxford-50 text-oxford-900"
                    : "text-foreground hover:bg-muted",
                )}
              >
                {active ? (
                  <Check className="h-3.5 w-3.5 shrink-0 text-oxford-700" />
                ) : (
                  <Circle className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
                )}
                <div className="min-w-0 flex-1 truncate">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] font-bold tabular-nums text-muted-foreground">
                      {String(unit.week_number).padStart(2, "0")}
                    </span>
                    <span className="truncate">{unit.title}</span>
                  </div>
                  <div className="mt-0.5 text-[10px] text-muted-foreground">
                    {formatMinutes(unit.estimated_workload_minutes)}
                    {unit.topics.length > 0 && (
                      <span> · {unit.topics.length} topic{unit.topics.length !== 1 && "s"}</span>
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </ScrollArea>
    </div>
  );
}