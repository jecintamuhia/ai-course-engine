import { AlertCircle } from "lucide-react";

import { Button } from "@/components/ui/button";

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({ message, onRetry, className }: ErrorStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-4 rounded-2xl border border-red-200 bg-red-50/70 px-8 py-14 text-center ${className ?? ""}`}
    >
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-red-100 text-red-600">
        <AlertCircle className="h-7 w-7" />
      </span>
      <p className="max-w-md text-sm whitespace-pre-wrap text-red-900">{message}</p>
      {onRetry && (
        <Button variant="outline" onClick={onRetry} className="border-red-200 text-red-700 hover:bg-red-50">
          Try again
        </Button>
      )}
    </div>
  );
}