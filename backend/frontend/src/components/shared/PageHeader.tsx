import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  eyebrow?: ReactNode;
  meta?: ReactNode;
}

export function PageHeader({ title, description, actions, eyebrow, meta }: PageHeaderProps) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
      <div className="min-w-0 max-w-3xl">
        {eyebrow && (
          <div className="mb-3 inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-oxford-700">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-oxford" />
            {eyebrow}
          </div>
        )}
        <h1 className="text-3xl font-bold tracking-tight text-ink sm:text-[34px] sm:leading-[1.15]">
          {title}
        </h1>
        {(description || meta) && (
          <div className="mt-2.5 space-y-1">
            {description && (
              <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
                {description}
              </p>
            )}
            {meta && <p className="text-xs text-muted-foreground/80">{meta}</p>}
          </div>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}