"use client";

import React, { useEffect, useState } from "react";
import { Activity, AlertOctagon, CheckCircle2, ShieldAlert, Users } from "lucide-react";
import { opsService } from "@/services/ops";
import { useAuth } from "@/hooks/useAuth";
import { useLanguage } from "@/hooks/useLanguage";
import type { OverviewReport, Track } from "@/types/recova";
import { cn } from "@/lib/utils";

const TRACK_LABELS: Record<Track, string> = {
  core: "Recovery (Core)",
  loop: "Recova Loop",
  neuro: "Recova Neuro",
  worksafe: "Recova WorkSafe",
};

export function SubEngineSummaryBanner({ track }: { track: Track }) {
  const { session } = useAuth();
  const { t, tr } = useLanguage();
  const aggregateOnly = session?.role === "supervisor";
  const [overview, setOverview] = useState<OverviewReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (aggregateOnly) return;
    let active = true;
    opsService
      .getOverview()
      .then((res) => {
        if (active) setOverview(res);
      })
      .catch(() => {
        if (active) setOverview(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [track, aggregateOnly]);

  if (aggregateOnly) {
    return (
      <p className="text-sm text-slate-600">
        {t("Your department heatmap below protects individual privacy. Clinical actions are managed by the occupational health team.")}
      </p>
    );
  }

  const dist = overview?.track_risk_distribution?.[track] || {};
  const green = dist.GREEN || 0;
  const amber = dist.AMBER || 0;
  const red = (dist.RED || 0) + (dist.EMERGENCY_BYPASS || 0);
  const unscored = (dist.UNSCORED || 0) + (dist.INDETERMINATE || 0);
  const totalEnrolled = green + amber + red + unscored;

  const tiles = [
    {
      label: tr(`${TRACK_LABELS[track]} enrolled`, `المسجلون في ${t(TRACK_LABELS[track])}`),
      value: loading ? "—" : totalEnrolled,
      detail: t("Active programme enrolments"),
      icon: Users,
      featured: true,
    },
    {
      label: t("Stable (GREEN)"),
      value: loading ? "—" : green,
      detail: t("Within personal baseline"),
      icon: CheckCircle2,
      tone: "green",
    },
    {
      label: t("Early warning (AMBER)"),
      value: loading ? "—" : amber,
      detail: "1.0 <= |Z| < 1.96",
      icon: Activity,
      tone: "amber",
    },
    {
      label: t("Needs attention (RED)"),
      value: loading ? "—" : red,
      detail: t("|Z| >= 1.96 or Gate 2 bypass"),
      icon: AlertOctagon,
      tone: "rose",
    },
    {
      label: t("Awaiting baseline"),
      value: loading ? "—" : unscored,
      detail: t("Insufficient windows (<3) or unscored"),
      icon: ShieldAlert,
      tone: "blue",
    },
  ];

  return (
    <section aria-label={`${TRACK_LABELS[track]} sub-dashboard summary`} className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {tiles.map((tile) => (
        <div
          key={tile.label}
          className={cn(
            "dashboard-stat",
            tile.featured && "dashboard-stat-featured"
          )}
        >
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11px] font-medium leading-snug">{tile.label}</p>
            <span
              className={cn(
                "stat-symbol",
                tile.featured ? "stat-symbol-featured" : `stat-symbol-${tile.tone}`
              )}
            >
              <tile.icon className="h-4 w-4" strokeWidth={1.7} />
            </span>
          </div>
          <p className="my-2 text-2xl font-semibold leading-tight tracking-tight tabular-nums">
            {tile.value}
          </p>
          <p className="text-[10px] leading-relaxed opacity-75">{tile.detail}</p>
        </div>
      ))}
    </section>
  );
}
