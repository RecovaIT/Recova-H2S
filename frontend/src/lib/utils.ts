import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const TRACK_META: Record<
  string,
  { name: string; subtitle: string; badgeClass: string; accent: string }
> = {
  core: {
    name: "Recova Core",
    subtitle: "Relapse Prevention & Rehabilitation",
    badgeClass: "bg-teal-50 text-teal-800 border-teal-200",
    accent: "text-teal-700",
  },
  loop: {
    name: "Recova Loop",
    subtitle: "IFHAS Screening-to-Care Navigation",
    badgeClass: "bg-indigo-50 text-indigo-800 border-indigo-200",
    accent: "text-indigo-700",
  },
  neuro: {
    name: "Recova Neuro",
    subtitle: "Cognitive Assessment (50-75) & Brain Health",
    badgeClass: "bg-violet-50 text-violet-800 border-violet-200",
    accent: "text-violet-700",
  },
  worksafe: {
    name: "Recova WorkSafe",
    subtitle: "Workforce Fatigue & Heat-Stress Prevention",
    badgeClass: "bg-amber-50 text-amber-800 border-amber-200",
    accent: "text-amber-700",
  },
};

export function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatRelativeCountdown(targetIso?: string | null): string {
  if (!targetIso) return "No SLA deadline";
  const diffMs = new Date(targetIso).getTime() - Date.now();
  const absHours = Math.floor(Math.abs(diffMs) / 3600000);
  const absMins = Math.floor((Math.abs(diffMs) % 3600000) / 60000);
  if (diffMs < 0) {
    return absHours >= 24
      ? `Overdue by ${Math.floor(absHours / 24)}d ${absHours % 24}h`
      : `Overdue by ${absHours}h ${absMins}m`;
  }
  return absHours >= 24
    ? `${Math.floor(absHours / 24)}d ${absHours % 24}h remaining`
    : `${absHours}h ${absMins}m remaining`;
}

export function formatLabel(raw?: string | null): string {
  if (!raw) return "—";
  return raw
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function downloadJsonFile(filename: string, payload: unknown): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function nowTimestampMs(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}
