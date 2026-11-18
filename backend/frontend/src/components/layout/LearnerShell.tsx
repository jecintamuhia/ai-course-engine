import { useEffect, useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { LogOut, LayoutDashboard, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { BRAND } from "@/lib/brand";
import { clearToken, getRole, isStaff } from "@/lib/auth";
import { api } from "@/lib/api";
import type { LearnerProfileRead } from "@/lib/types";

/**
 * Chrome for the learner portal.
 *
 * Deliberately much lighter than the authoring workspace: a learner has
 * no textbooks, no curricula and no publishing controls, so none of that
 * navigation is offered. The Moodle link is kept because Moodle is where
 * the course content itself is delivered.
 */
export function LearnerShell() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<LearnerProfileRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const staff = isStaff();

  useEffect(() => {
    let active = true;
    api
      .learnerProfile()
      .then((response) => {
        if (active) setProfile(response);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not load your learner profile.",
        );
      });
    return () => {
      active = false;
    };
  }, []);

  function handleSignOut() {
    clearToken();
    navigate("/login", { replace: true });
  }

  const role = getRole();

  return (
    <div className="flex min-h-screen w-full flex-col bg-background text-foreground">
      <header className="sticky top-0 z-20 bg-navy-950 text-sand-100">
        <div className="mx-auto flex h-16 w-full max-w-[1180px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <img
              src={BRAND.logoSmall}
              alt={`${BRAND.name} logo`}
              className="h-9 w-auto shrink-0 rounded-md bg-white/95 p-1 shadow-sm ring-1 ring-sand-100/15"
            />
            <div className="hidden min-w-0 leading-tight sm:block">
              <div className="truncate text-[12px] font-extrabold tracking-[0.08em] text-sand-50">
                {BRAND.shortName.toUpperCase()}
              </div>
              <div className="truncate text-[11px] font-medium text-sand-100/55">
                Learner portal
              </div>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {staff && (
              <Button
                asChild
                variant="ghost"
                size="sm"
                className="text-sand-100/80 hover:bg-navy-800 hover:text-sand-50"
              >
                <a href="/dashboard">
                  <LayoutDashboard className="h-4 w-4" />
                  Workspace
                </a>
              </Button>
            )}
            <div className="hidden text-right leading-tight sm:block">
              <div className="max-w-[12rem] truncate text-[13px] font-semibold text-sand-50">
                {profile?.full_name ?? "—"}
              </div>
              <div className="text-[11px] capitalize text-sand-100/50">
                {role ?? "learner"}
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="text-sand-100/80 hover:bg-navy-800 hover:text-sand-50"
              onClick={handleSignOut}
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1 px-4 py-7 sm:px-6 lg:px-8 lg:py-10">
        <div className="mx-auto w-full max-w-[1180px] animate-fade-in">
          {error && (
            <div className="mb-6 rounded-lg border border-brand/30 bg-brand/5 px-4 py-3 text-sm text-brand-800">
              {error}
            </div>
          )}
          <Outlet />
        </div>
      </main>

      <footer className="border-t border-border bg-sand-50 px-4 py-5 text-center text-[11px] text-muted-foreground sm:px-6">
        {BRAND.name} &middot; learner portal &middot; course content is
        delivered on Moodle
      </footer>
    </div>
  );
}

/** Small spinner used while the portal loads its first payload. */
export function LearnerLoading() {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      Loading your learning plan…
    </div>
  );
}
