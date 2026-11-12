import React from "react";
import { cn } from "@/lib/utils";

type BadgeVariant = "default" | "secondary" | "outline" | "success" | "warning" | "danger" | "info";

const BADGE_CLASSES: Record<BadgeVariant, string> = {
  default: "bg-slate-900 text-white border-transparent",
  secondary: "bg-slate-100 text-slate-800 border-slate-200",
  outline: "bg-white text-slate-700 border-slate-300",
  success: "bg-emerald-50 text-emerald-800 border-emerald-200",
  warning: "bg-amber-50 text-amber-800 border-amber-300",
  danger: "bg-red-50 text-red-800 border-red-300",
  info: "bg-sky-50 text-sky-800 border-sky-200",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

export function Badge({ className, variant = "secondary", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        BADGE_CLASSES[variant],
        className
      )}
      {...props}
    />
  );
}
