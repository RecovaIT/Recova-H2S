import React from "react";
import { Badge } from "@/components/ui/badge";
import { cn, formatLabel } from "@/lib/utils";

const RISK_CLASSES: Record<string, string> = {
  GREEN: "bg-emerald-50 text-emerald-800 border-emerald-300",
  AMBER: "bg-amber-50 text-amber-800 border-amber-300",
  RED: "bg-red-50 text-red-800 border-red-300",
  EMERGENCY_BYPASS: "bg-red-600 text-white border-red-700 animate-pulse",
  INDETERMINATE: "bg-slate-100 text-slate-700 border-slate-300",
};

export function RiskBadge({
  tier,
  className,
}: {
  tier?: string | null;
  className?: string;
}) {
  const key = (tier || "INDETERMINATE").toUpperCase();
  const label = key === "EMERGENCY_BYPASS" ? "EMERGENCY BYPASS" : key;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold tracking-wide",
        RISK_CLASSES[key] || RISK_CLASSES.INDETERMINATE,
        className
      )}
    >
      {label}
    </span>
  );
}

export function StatusBadge({ status }: { status?: string | null }) {
  const s = (status || "").toLowerCase();
  if (["completed", "succeeded", "delivered", "outcome_verified", "met", "granted", "resolved", "verified"].includes(s)) {
    return <Badge variant="success">{formatLabel(status)}</Badge>;
  }
  if (["amber", "at_risk", "queued", "running", "patient_notified", "booked", "approved", "acknowledged", "in_progress", "configured"].includes(s)) {
    return <Badge variant="info">{formatLabel(status)}</Badge>;
  }
  if (["proposed", "waiting", "planned", "pending", "consultation_completed"].includes(s)) {
    return <Badge variant="warning">{formatLabel(status)}</Badge>;
  }
  if (["failed", "blocked", "emergency_bypass", "flagged", "breached", "missed", "escalated", "revoked", "rejected", "open", "error", "dead"].includes(s)) {
    return <Badge variant="danger">{formatLabel(status)}</Badge>;
  }
  return <Badge variant="secondary">{formatLabel(status || "unknown")}</Badge>;
}
