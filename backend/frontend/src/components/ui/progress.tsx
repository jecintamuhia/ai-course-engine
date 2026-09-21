import * as React from "react";
import * as ProgressPrimitive from "@radix-ui/react-progress";

import { cn } from "@/lib/utils";

const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & {
    indicatorClassName?: string;
    /** Renders an animated, indeterminate sweep — used for AI processing. */
    indeterminate?: boolean;
  }
>(({ className, value, indicatorClassName, indeterminate = false, ...props }, ref) => (
  <ProgressPrimitive.Root
    ref={ref}
    className={cn(
      "relative h-2 w-full overflow-hidden rounded-full bg-secondary",
      className,
    )}
    {...props}
  >
    {indeterminate ? (
      <div
        aria-hidden
        className={cn(
          "absolute inset-y-0 w-1/3 animate-progress-indeterminate rounded-full bg-burgundy/80",
          indicatorClassName,
        )}
      />
    ) : (
      <ProgressPrimitive.Indicator
        className={cn(
          "h-full w-full flex-1 rounded-full bg-burgundy transition-all duration-300 ease-in-out",
          indicatorClassName,
        )}
        style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
      />
    )}
  </ProgressPrimitive.Root>
));
Progress.displayName = ProgressPrimitive.Root.displayName;

export { Progress };