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
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-card px-8 py-16 text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-burgundy-50 text-burgundy">
        {icon || <FileText className="h-7 w-7" />}
      </div>
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      {description && (
        <p className="mt-2 max-w-sm text-sm text-muted-foreground">{description}</p>
      )}
      {(actionLabel && (actionTo || onAction)) && (
        <Button
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