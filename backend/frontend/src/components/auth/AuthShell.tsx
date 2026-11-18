import type { ReactNode } from "react";

import { BRAND } from "@/lib/brand";
import { cn } from "@/lib/utils";

interface AuthShellProps {
  /** Heading of the form column. */
  title: string;
  /** One-line explanation under the heading. */
  subtitle: string;
  /** The form or other primary content. */
  children: ReactNode;
  /** Optional content pinned under the form (links, hints). */
  footer?: ReactNode;
  /** Accessible name for the brand panel landmark. */
  brandLabel?: string;
}

const BRAND_POINTS = [
  "Turn a textbook into a structured 16-week course.",
  "Map concepts, prerequisites and learning objectives automatically.",
  "Review every lesson before it reaches your learners.",
];

/**
 * Two-column branded frame for the authentication pages.
 *
 * The brand panel carries the organisation's real artwork and the
 * official palette (navy #283890 with the red #ED1B24 accent). On small
 * screens it collapses to a compact banner above the form so the fields
 * stay reachable without scrolling past a full-height panel.
 */
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
  brandLabel = `About ${BRAND.name}`,
}: AuthShellProps) {
  return (
    <div className="min-h-svh lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] xl:grid-cols-[minmax(0,1fr)_minmax(0,30rem)]">
      {/* Brand panel */}
      <section
        aria-label={brandLabel}
        className="relative overflow-hidden bg-navy-950 px-6 py-10 text-sand-50 sm:px-10 lg:flex lg:flex-col lg:justify-between lg:px-14 lg:py-14"
      >
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-56 bg-[radial-gradient(120%_90%_at_18%_-20%,rgba(40,56,144,0.85)_0%,rgba(18,23,56,0)_62%)]"
        />
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-64 bg-[radial-gradient(110%_90%_at_85%_120%,rgba(237,27,36,0.28)_0%,rgba(18,23,56,0)_62%)]"
        />

        <div className="relative z-10">
          <img
            src={BRAND.logoSmall}
            alt={`${BRAND.name} logo`}
            className="h-11 w-auto rounded-md bg-white/95 p-1.5 shadow-sm ring-1 ring-white/15"
          />
        </div>

        <div className="relative z-10 mt-8 hidden lg:block">
          <h2 className="font-display text-[2.6rem] font-bold leading-[1.08] tracking-tight text-white">
            Build courses that teach
            <span className="block text-brand-400">real skills.</span>
          </h2>
          <p className="mt-4 max-w-md text-[0.98rem] leading-relaxed text-sand-100/70">
            {BRAND.name} turns any textbook into a reviewed, teachable
            curriculum — then delivers it to your learners.
          </p>
          <ul className="mt-8 space-y-3.5">
            {BRAND_POINTS.map((point) => (
              <li
                key={point}
                className="flex items-start gap-3 text-[0.95rem] leading-relaxed text-sand-100/80"
              >
                <span
                  aria-hidden
                  className="mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-brand-400/60 bg-brand/20"
                >
                  <svg viewBox="0 0 10 10" className="h-2.5 w-2.5" aria-hidden>
                    <path
                      d="M1.5 5.2 4 7.5 8.5 2.5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="text-brand-300"
                    />
                  </svg>
                </span>
                {point}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative z-10 mt-8 hidden text-xs text-sand-100/40 lg:block">
          {BRAND.name} &middot; {BRAND.product}
        </p>
      </section>

      {/* Form column */}
      <main className="flex items-center justify-center bg-sand px-5 py-10 sm:px-8 sm:py-14">
        <div className="w-full max-w-sm">
          <div className="mb-6 lg:mb-8">
            {/* Compact brand lockup for small screens, where the panel is hidden. */}
            <img
              src={BRAND.logoSmall}
              alt=""
              aria-hidden
              className="mb-6 h-9 w-auto rounded-md bg-white p-1 shadow-sm ring-1 ring-border lg:hidden"
            />
            <h1
              className={cn(
                "font-display text-2xl font-bold tracking-tight text-navy-900",
              )}
            >
              {title}
            </h1>
            <p className="mt-1.5 text-sm text-muted-foreground">{subtitle}</p>
          </div>

          {children}

          {footer ? <div className="mt-6">{footer}</div> : null}
        </div>
      </main>
    </div>
  );
}
