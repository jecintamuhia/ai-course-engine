import { Loader2 } from "lucide-react";

interface LoadingStateProps {
  message?: string;
  className?: string;
}

export function LoadingState({ message = "Loading…", className }: LoadingStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-4 py-28 text-muted-foreground ${className ?? ""}`}
    >
      <span className="relative flex h-12 w-12 items-center justify-center">
        <span aria-hidden className="absolute inset-0 animate-ping rounded-full bg-burgundy/10" />
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-burgundy-50 text-burgundy ring-1 ring-burgundy/10">
          <Loader2 className="h-5 w-5 animate-spin" />
        </span>
      </span>
      <span className="text-sm text-ink/60">{message}</span>
    </div>
  );
}