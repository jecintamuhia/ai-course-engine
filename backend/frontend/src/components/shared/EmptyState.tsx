import type { ReactNode } from "react";
import { FileText, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  actionLabel?: string;
  actionTo?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  actionTo,
  onAction,
}: EmptyStateProps) {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-sand-300 bg-card/60 px-8 py-16 text-center shadow-inset-line">
      <span className="relative mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-50 text-brand ring-8 ring-brand/[0.04]">
        {icon || <FileText className="h-8 w-8" />}
      </span>
      <h3 className="text-lg font-semibold tracking-tight text-ink">{title}</h3>
      {description && (
        <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
          {description}
        </p>
      )}
      {(actionLabel && (actionTo || onAction)) && (
        <Button
          size="lg"
          className="mt-6"
          onClick={() => {
            if (onAction) onAction();
            else if (actionTo) navigate(actionTo);
          }}
        >
          {actionLabel}
          <ArrowRight className="ml-1 h-4 w-4" />
        </Button>
      )}
    </div>
  );
}