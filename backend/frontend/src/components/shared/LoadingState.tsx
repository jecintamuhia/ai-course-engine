import { Loader2 } from "lucide-react";

interface LoadingStateProps {
  message?: string;
  className?: string;
}

export function LoadingState({ message = "Loading…", className }: LoadingStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 py-24 text-muted-foreground ${className ?? ""}`}>
      <Loader2 className="h-6 w-6 animate-spin" />
      <span className="text-sm">{message}</span>
    </div>
  );
}