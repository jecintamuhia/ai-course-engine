import { useLocation, Link } from "react-router-dom";
import { Menu, Plus, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { moodleState } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { MoodleStatusState } from "@/hooks/useMoodleStatus";

const ROUTE_BREADCRUMB: Array<{ match: RegExp; group: string; label: string }> = [
  { match: /^\/dashboard/, group: "Workspace", label: "Overview" },
  { match: /^\/upload/, group: "Workspace", label: "Upload textbook" },
  { match: /^\/documents$/, group: "Workspace", label: "Textbooks" },
  { match: /^\/document\//, group: "Workspace", label: "AI analysis" },
  { match: /^\/curriculum\//, group: "Workspace", label: "Curriculum studio" },
  { match: /^\/publish\//, group: "Delivery", label: "Publish to Moodle" },
  { match: /^\/courses/, group: "Delivery", label: "Published courses" },
  { match: /^\/status/, group: "System", label: "System status" },
];

function crumbFor(pathname: string): { group: string; label: string } {
  for (const { match, group, label } of ROUTE_BREADCRUMB) {
    if (match.test(pathname)) return { group, label };
  }
  return { group: "Workspace", label: "Overview" };
}

interface TopBarProps {
  onOpenMobileNav: () => void;
  moodle: MoodleStatusState;
}

export function TopBar({ onOpenMobileNav, moodle }: TopBarProps) {
  const { pathname } = useLocation();
  const { group, label } = crumbFor(pathname);
  const state = moodleState(moodle.status);
  const connected = moodle.status?.connected === true;

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-4 border-b border-border bg-cream-50/85 px-4 backdrop-blur-md sm:px-6 lg:px-8">
      <div className="flex min-w-0 items-center gap-2.5">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={onOpenMobileNav}
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </Button>
        <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-sm">
          <span className="hidden text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground sm:block">
            {group}
          </span>
          <ChevronRight
            aria-hidden
            className="hidden h-3.5 w-3.5 text-muted-foreground/50 sm:block"
          />
          <span className="truncate font-semibold text-ink">{label}</span>
        </nav>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Link
          to="/status"
          className="hidden items-center gap-2 rounded-md border border-border bg-card px-2.5 py-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:border-oxford/25 hover:text-oxford-800 sm:inline-flex"
          title="Moodle connection"
        >
          <span
            aria-hidden
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              moodle.loading
                ? "animate-pulse-soft bg-cream-300"
                : connected
                  ? "bg-emerald-500"
                  : moodle.status?.configured
                    ? "bg-red-500"
                    : "bg-muted-foreground/40",
            )}
          />
          {moodle.loading ? "Checking…" : state.label}
        </Link>
        <Button asChild size="sm">
          <Link to="/upload">
            <Plus className="h-4 w-4" />
            Upload textbook
          </Link>
        </Button>
      </div>
    </header>
  );
}