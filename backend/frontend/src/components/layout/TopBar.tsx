import { useLocation } from "react-router-dom";
import { Menu, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";

const ROUTE_LABELS: Array<{ match: RegExp; label: string }> = [
  { match: /^\/dashboard/, label: "Dashboard" },
  { match: /^\/upload/, label: "Upload textbook" },
  { match: /^\/documents$/, label: "Documents" },
  { match: /^\/document\//, label: "Document" },
  { match: /^\/curriculum\//, label: "Curriculum studio" },
  { match: /^\/publish\//, label: "Publish to Moodle" },
  { match: /^\/courses/, label: "Published courses" },
  { match: /^\/status/, label: "System status" },
];

function labelFor(pathname: string): string {
  for (const { match, label } of ROUTE_LABELS) {
    if (match.test(pathname)) return label;
  }
  return "Dashboard";
}

interface TopBarProps {
  onOpenMobileNav: () => void;
}

export function TopBar({ onOpenMobileNav }: TopBarProps) {
  const { pathname } = useLocation();

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-4 border-b border-border bg-card/90 px-4 backdrop-blur sm:px-6">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={onOpenMobileNav}
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </Button>
        <span className="text-sm font-semibold text-foreground">
          {labelFor(pathname)}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Button asChild size="sm">
          <a href="/upload">
            <Plus className="h-4 w-4" />
            New upload
          </a>
        </Button>
      </div>
    </header>
  );
}