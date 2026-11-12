import React from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { cn } from "@/lib/utils";

type AlertVariant = "info" | "success" | "warning" | "danger";

const STYLES: Record<AlertVariant, { wrap: string; icon: React.ReactNode }> = {
  info: {
    wrap: "border-sky-200 bg-sky-50 text-sky-900",
    icon: <Info className="h-4 w-4 shrink-0 text-sky-600" />,
  },
  success: {
    wrap: "border-emerald-200 bg-emerald-50 text-emerald-900",
    icon: <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />,
  },
  warning: {
    wrap: "border-amber-300 bg-amber-50 text-amber-950",
    icon: <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />,
  },
  danger: {
    wrap: "border-red-300 bg-red-50 text-red-950",
    icon: <AlertCircle className="h-4 w-4 shrink-0 text-red-600" />,
  },
};

export function Alert({
  variant = "info",
  title,
  children,
  className,
}: {
  variant?: AlertVariant;
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  const s = STYLES[variant];
  return (
    <div className={cn("flex gap-3 rounded-lg border p-3.5 text-sm", s.wrap, className)}>
      <div className="mt-0.5">{s.icon}</div>
      <div className="flex-1 space-y-1">
        {title && <div className="font-semibold leading-tight">{title}</div>}
        <div className="text-xs leading-relaxed opacity-95">{children}</div>
      </div>
    </div>
  );
}
