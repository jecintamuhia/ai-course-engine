import { NavLink } from "react-router-dom";
import {
  BookOpen,
  GraduationCap,
  Activity,
  LayoutDashboard,
  Upload,
  Loader2,
  Sparkles,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { BRAND } from "@/lib/brand";
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
    items: [
      { to: "/courses", label: "Published courses", icon: GraduationCap },
      { to: "/reviews", label: "Learner review", icon: Users },
    ],
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
          "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sand-100/40",
          isActive
            ? "bg-sand-100 text-navy-900 shadow-sm"
            : "text-sand-100/65 hover:bg-navy-800/60 hover:text-sand-50",
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon
            className={cn(
              "h-4 w-4 shrink-0 transition-colors",
              isActive ? "text-brand-700" : "text-sand-100/50 group-hover:text-sand-100",
            )}
          />
          {item.label}
          {isActive && (
            <span
              aria-hidden
              className="absolute right-2 h-1.5 w-1.5 rounded-full bg-brand"
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
    <aside className="relative flex h-full w-full flex-col overflow-hidden bg-navy-950 text-sand-100">
      {/* Brand wash */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-44 bg-[radial-gradient(130%_90%_at_20%_-20%,rgba(40,56,144,0.55)_0%,rgba(18,23,56,0)_62%)]"
      />
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-[radial-gradient(120%_100%_at_50%_120%,rgba(237,27,36,0.22)_0%,rgba(18,23,56,0)_60%)]"
      />

      {/* Brand */}
      <div className="relative z-10 flex items-center gap-3 border-b border-sand-100/10 px-5 py-5">
        <img
          src={BRAND.logoSmall}
          alt={`${BRAND.name} logo`}
          className="h-9 w-auto shrink-0 rounded-md bg-white/95 p-1 shadow-sm ring-1 ring-sand-100/15"
        />
        <div className="min-w-0 leading-tight">
          <div className="truncate text-[12px] font-extrabold tracking-[0.08em] text-sand-50">
            {BRAND.shortName.toUpperCase()}
          </div>
          <div className="truncate text-[11px] font-medium text-sand-100/55">
            Action Africa
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="relative z-10 flex flex-1 flex-col overflow-y-auto px-3 py-3">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="mt-4 first:mt-1">
            <div className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-sand-100/35">
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
          <div className="mb-3 flex items-center gap-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-sand-100/35">
            <Sparkles className="h-3 w-3" />
            Flow
          </div>
          <div className="mx-3 rounded-xl border border-sand-100/10 bg-navy-800/40 p-3 text-[10px] leading-relaxed text-sand-100/55">
            Textbook &rarr; AI understanding &rarr; knowledge map &rarr; curriculum &rarr;
            review &rarr; Moodle
          </div>
        </div>
      </nav>

      {/* Moodle connection */}
      <div className="relative z-10 border-t border-sand-100/10 px-4 py-3.5">
        <div className="flex items-center gap-2.5 rounded-lg bg-navy-800/60 px-3 py-2 text-xs text-sand-100/75 ring-1 ring-sand-100/5">
          {moodle.loading ? (
            <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
          ) : (
            <span
              className={cn(
                "h-2 w-2 shrink-0 rounded-full",
                state.tone === "success" && "bg-emerald-400",
                state.tone === "danger" && "bg-red-400",
                state.tone === "neutral" && "bg-sand-100/40",
              )}
            />
          )}
          <span className="truncate">{state.label}</span>
        </div>
      </div>
    </aside>
  );
}