import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { Tone } from "@/lib/status";

const toneToVariant: Record<Tone, BadgeProps["variant"]> = {
  neutral: "neutral",
  primary: "primary",
  success: "success",
  warning: "warning",
  danger: "danger",
  info: "info",
  ai: "ai",
};

interface StatusBadgeProps extends BadgeProps {
  tone: Tone;
  label: string;
}

export function StatusBadge({ tone, label, dot = true, ...props }: StatusBadgeProps) {
  return (
    <Badge variant={toneToVariant[tone]} dot={dot} {...props}>
      {label}
    </Badge>
  );
}