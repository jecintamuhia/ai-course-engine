import { NavLink } from "react-router-dom";
import {
  BookOpen,
  GraduationCap,
  Activity,
  LayoutDashboard,
  Upload,
  Loader2,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { moodleState } from "@/lib/status";
import type { MoodleStatusState } from "@/hooks/useMoodleStatus";

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  end?: boolean;
}

const NAV_SECTIONS: Array<{ label: string; items: NavItem[] }> = [
  {
    label: "Workspace",
    items: [
      { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, end: true },
      { to: "/upload", label: "Upload textbook", icon: Upload },
      { to: "/documents", label: "Documents", icon: BookOpen },
    ],
  },
  {
    label: "Publish & operate",
    items: [
      { to: "/courses", label: "Published courses", icon: GraduationCap },
      { to: "/status", label: "System status", icon: Activity },
    ],
  },
];

function NavLinkItem({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const Icon = item.icon;
  return (
    <NavLink
      key={item.to}
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cream-100/60",
          isActive
            ? "bg-gradient-to-r from-burgundy-700 to-burgundy-800 text-cream-50 shadow-sm ring-1 ring-cream-100/10"
            : "text-cream-100/70 hover:bg-burgundy-800/70 hover:text-cream-50",
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span
              aria-hidden
              className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-md bg-cream-100"
            />
          )}
          <Icon className="h-4 w-4 shrink-0 transition-colors group-hover:text-cream-100" />
          {item.label}
        </>
      )}
    </NavLink>
  );
}

export function Sidebar({
  moodle,
  onNavigate,
}: {
  moodle: MoodleStatusState;
  onNavigate?: () => void;
}) {
  const state = moodleState(moodle.status);

  return (
    <aside className="relative flex h-full w-full flex-col overflow-hidden border-r border-cream-100/5 bg-burgundy-900 text-cream-100">
      {/* Soft burgundy glow at the top for depth */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-48 bg-[radial-gradient(120%_80%_at_50%_-10%,rgba(107,31,50,0.45)_0%,transparent_60%)]"
      />

      {/* Brand */}
      <div className="relative z-10 flex items-center gap-3 border-b border-cream-100/10 px-5 py-5">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-burgundy-600 to-burgundy-800 text-cream-50 shadow-sm ring-1 ring-cream-100/15">
          <GraduationCap className="h-[22px] w-[22px]" />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-bold tracking-wide text-cream-50">AI Course Engine</div>
          <div className="text-[11px] text-cream-100/60">
            Textbook &rarr; Curriculum &rarr; Moodle
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="relative z-10 flex flex-1 flex-col gap-1 overflow-y-auto px-3 py-2">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="mt-3 first:mt-1">
            <div className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-cream-100/40">
              {section.label}
            </div>
            <div className="flex flex-col gap-0.5">
              {section.items.map((item) => (
                <NavLinkItem key={item.to} item={item} onNavigate={onNavigate} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Moodle status */}
      <div className="relative z-10 border-t border-cream-100/10 px-4 py-3.5">
        <div className="flex items-center gap-2.5 rounded-lg bg-burgundy-800/60 px-3 py-2 text-xs text-cream-100/80 ring-1 ring-cream-100/5">
          {moodle.loading ? (
            <Loader2 className="h-3 w-3 shrink-0 animate-spin" />
          ) : (
            <span
              className={cn(
                "h-2 w-2 shrink-0 rounded-full",
                state.tone === "success" && "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]",
                state.tone === "danger" && "bg-red-400",
                state.tone === "neutral" && "bg-cream-100/40",
              )}
            />
          )}
          <span className="truncate">{state.label}</span>
        </div>
      </div>
    </aside>
  );
}