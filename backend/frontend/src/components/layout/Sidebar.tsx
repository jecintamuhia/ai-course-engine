import { NavLink } from "react-router-dom";
import {
  BookOpen,
  GraduationCap,
  Activity,
  LayoutDashboard,
  Upload,
  Loader2,
  Sparkles,
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
      { to: "/dashboard", label: "Overview", icon: LayoutDashboard, end: true },
      { to: "/documents", label: "Textbooks", icon: BookOpen },
      { to: "/upload", label: "Upload textbook", icon: Upload },
    ],
  },
  {
    label: "Delivery",
    items: [{ to: "/courses", label: "Published courses", icon: GraduationCap }],
  },
  {
    label: "System",
    items: [{ to: "/status", label: "System status", icon: Activity }],
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
          "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cream-100/40",
          isActive
            ? "bg-cream-100 text-burgundy-900 shadow-sm"
            : "text-cream-100/65 hover:bg-burgundy-800/60 hover:text-cream-50",
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon
            className={cn(
              "h-4 w-4 shrink-0 transition-colors",
              isActive ? "text-burgundy-700" : "text-cream-100/50 group-hover:text-cream-100",
            )}
          />
          {item.label}
          {isActive && (
            <span
              aria-hidden
              className="absolute right-2 h-1.5 w-1.5 rounded-full bg-burgundy"
            />
          )}
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
    <aside className="relative flex h-full w-full flex-col overflow-hidden bg-burgundy-900 text-cream-100">
      {/* Brand wash */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-44 bg-[radial-gradient(130%_90%_at_20%_-20%,rgba(107,31,50,0.55)_0%,rgba(53,16,26,0)_62%)]"
      />
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-[radial-gradient(120%_100%_at_50%_120%,rgba(107,31,50,0.35)_0%,rgba(53,16,26,0)_60%)]"
      />

      {/* Brand */}
      <div className="relative z-10 flex items-center gap-3 border-b border-cream-100/10 px-5 py-5">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-burgundy-500 to-burgundy-800 text-cream-50 shadow-md ring-1 ring-cream-100/20">
          <GraduationCap className="h-5 w-5" />
        </div>
        <div className="leading-tight">
          <div className="text-[13px] font-extrabold tracking-[0.08em] text-cream-50">
            SKILLUP&nbsp;AI
          </div>
          <div className="text-[11px] font-medium text-cream-100/55">
            Course Intelligence
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="relative z-10 flex flex-1 flex-col overflow-y-auto px-3 py-3">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="mt-4 first:mt-1">
            <div className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-cream-100/35">
              {section.label}
            </div>
            <div className="flex flex-col gap-0.5">
              {section.items.map((item) => (
                <NavLinkItem key={item.to} item={item} onNavigate={onNavigate} />
              ))}
            </div>
          </div>
        ))}

        {/* Product narrative footer */}
        <div className="mt-auto pt-5">
          <div className="mb-3 flex items-center gap-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-cream-100/35">
            <Sparkles className="h-3 w-3" />
            Flow
          </div>
          <div className="mx-3 rounded-xl border border-cream-100/10 bg-burgundy-800/40 p-3 text-[10px] leading-relaxed text-cream-100/55">
            Textbook &rarr; AI understanding &rarr; knowledge map &rarr; curriculum &rarr;
            review &rarr; Moodle
          </div>
        </div>
      </nav>

      {/* Moodle connection */}
      <div className="relative z-10 border-t border-cream-100/10 px-4 py-3.5">
        <div className="flex items-center gap-2.5 rounded-lg bg-burgundy-800/60 px-3 py-2 text-xs text-cream-100/75 ring-1 ring-cream-100/5">
          {moodle.loading ? (
            <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
          ) : (
            <span
              className={cn(
                "h-2 w-2 shrink-0 rounded-full",
                state.tone === "success" && "bg-emerald-400",
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