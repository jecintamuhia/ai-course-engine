import { cn } from "@/lib/utils";

interface LoaderProps {
  className?: string;
}

/** Compact inline spinner (border-trim technique) used inside panels. */
export function Loader({ className }: LoaderProps) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent",
        className,
      )}
    />
  );
}