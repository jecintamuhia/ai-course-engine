import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold tracking-wide transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-oxford text-cream-50 shadow-sm",
        primary:
          "border-oxford/20 bg-cream-200 text-oxford-900",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground",
        success:
          "border-emerald-200 bg-emerald-100 text-emerald-800",
        warning:
          "border-amber-200 bg-amber-100 text-amber-800",
        danger:
          "border-red-200 bg-red-100 text-red-800",
        info:
          "border-sky-200 bg-sky-100 text-sky-800",
        ai:
          "border-ai/25 bg-ai/10 text-ai",
        outline:
          "border-border bg-card text-foreground",
        neutral:
          "border-transparent bg-muted text-muted-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  dot?: boolean;
}

function Badge({ className, variant, dot = false, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props}>
      {dot && <span aria-hidden className="size-1.5 rounded-full bg-current" />}
      {props.children}
    </span>
  );
}

export { Badge, badgeVariants };