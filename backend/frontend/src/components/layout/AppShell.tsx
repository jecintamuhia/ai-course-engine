import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";

import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { useMoodleStatus } from "@/hooks/useMoodleStatus";

export function AppShell() {
  const moodle = useMoodleStatus();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      {/* Desktop sidebar */}
      <div className="hidden w-64 shrink-0 md:block" aria-hidden>
        <div className="fixed inset-y-0 left-0 w-64">
          <Sidebar moodle={moodle} />
        </div>
      </div>

      {/* Mobile drawer */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetTrigger asChild>
          <span className="sr-only" />
        </SheetTrigger>
        <SheetContent side="left" className="w-72 border-r-0 bg-burgundy-900 p-0 text-cream-100">
          <Sidebar moodle={moodle} onNavigate={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onOpenMobileNav={() => setMobileOpen(true)} moodle={moodle} />
        <main className="flex-1 px-4 py-7 sm:px-6 lg:px-8 lg:py-9">
          <div className="mx-auto w-full max-w-[1440px] animate-fade-in">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}