"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useReducedMotion } from "framer-motion";
import {
  Activity,
  AlertOctagon,
  ArrowRight,
  Brain,
  CheckCircle2,
  ClipboardCheck,
  GitBranch,
  HardHat,
  HeartPulse,
  Users,
  Workflow,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useAuth } from "@/hooks/useAuth";
import { engineService } from "@/services/engine";
import { opsService } from "@/services/ops";
import type { OverviewReport, PipelineRun, PlatformOverviewReport, Track } from "@/types/recova";
import { cn, formatDateTime } from "@/lib/utils";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { RiskBadge, StatusBadge } from "@/components/RiskBadge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const TRACKS = [
  {
    key: "core",
    title: "Recova Core",
    name: "Core",
    description: "Recovery & relapse prevention",
    icon: HeartPulse,
    href: "/core",
  },
  {
    key: "loop",
    title: "Recova Loop",
    name: "Loop",
    description: "Screening & care navigation",
    icon: Workflow,
    href: "/loop",
  },
  {
    key: "neuro",
    title: "Recova Neuro",
    name: "Neuro",
    description: "Cognitive health & baselines",
    icon: Brain,
    href: "/neuro",
  },
  {
    key: "worksafe",
    title: "Recova WorkSafe",
    name: "WorkSafe",
    description: "Workforce readiness & safety",
    icon: HardHat,
    href: "/worksafe",
  },
];

const RISK_SERIES = [
  {
    key: "GREEN",
    label: "Stable",
    color: "#4eaa86",
    gradient: "risk-stable",
    end: "#83cfac",
  },
  {
    key: "AMBER",
    label: "Early warning",
    color: "#d39b43",
    gradient: "risk-amber",
    end: "#efc878",
  },
  {
    key: "RED",
    label: "Needs attention",
    color: "#d66f71",
    gradient: "risk-red",
    end: "#eda5a1",
  },
  {
    key: "UNSCORED",
    label: "Awaiting score",
    color: "#8caabb",
    gradient: "risk-unscored",
    end: "#bbced9",
  },
];

export default function DashboardPage() {
  const { session, hasPermission, hasTrack, refreshSession } = useAuth();
  const reduceMotion = useReducedMotion();
  const [overview, setOverview] = useState<OverviewReport | null>(null);
  const [platformOverview, setPlatformOverview] = useState<PlatformOverviewReport | null>(null);
  const [selectedSubEngine, setSelectedSubEngine] = useState<Track>("core");
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [legacyProgramme, setLegacyProgramme] = useState<Track>("core");
  const [selectingLegacy, setSelectingLegacy] = useState(false);

  const isPlatformAdmin = Boolean(session?.user?.is_platform_admin);

  useEffect(() => {
    if (!session) return;
    let active = true;
    Promise.all([
      opsService.getOverview(),
      hasPermission("pipeline:read")
        ? engineService
            .listRuns({ page: 1, page_size: 5 })
            .then((result) => result.items)
        : Promise.resolve([]),
      session.user?.is_platform_admin
        ? opsService.getPlatformOverview().catch(() => null)
        : Promise.resolve(null),
    ])
      .then(([result, recentRuns, platRes]) => {
        if (!active) return;
        setOverview(result);
        setRuns(recentRuns);
        setPlatformOverview(platRes);
        setError(false);
      })
      .catch(() => {
        if (active) setError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [session, hasPermission]);

  const primaryProgramme = session?.active_organization?.primary_programme;
  const tracks = TRACKS.filter((track) => {
    if (isPlatformAdmin) return hasTrack(track.key);
    if (primaryProgramme && (session?.active_organization?.enabled_tracks?.length ?? 0) <= 1) {
      return track.key === primaryProgramme;
    }
    return hasTrack(track.key);
  });
  const chartData = tracks.map((track) => {
    const counts = overview?.track_risk_distribution[track.key] || {};
    return {
      track: track.name,
      GREEN: counts.GREEN || 0,
      AMBER: counts.AMBER || 0,
      RED: (counts.RED || 0) + (counts.EMERGENCY_BYPASS || 0),
      UNSCORED: (counts.UNSCORED || 0) + (counts.INDETERMINATE || 0),
    };
  });
  const totals = RISK_SERIES.map((series) => ({
    ...series,
    total: chartData.reduce(
      (sum, track) => sum + Number(track[series.key as keyof typeof track]),
      0,
    ),
  }));
  const enrollments = totals.reduce((sum, series) => sum + series.total, 0);
  const statistics = [
    {
      label: "Active participants",
      value: overview?.active_patients,
      icon: Users,
      detail: "Across your care pathways",
      featured: true,
    },
    {
      label: "Open emergencies",
      value: overview?.open_emergencies,
      icon: AlertOctagon,
      detail: "Immediate clinical triage",
      tone: "rose",
    },
    {
      label: "Pending reviews",
      value: overview?.pending_clinician_reviews,
      icon: ClipboardCheck,
      detail: "Awaiting clinician sign-off",
      tone: "amber",
    },
    {
      label: "Open referrals",
      value: overview?.open_referrals,
      icon: GitBranch,
      detail: `${overview?.sla_breaches ?? 0} overdue follow-ups`,
      tone: "blue",
    },
    {
      label: "Verified outcomes",
      value: overview?.verified_outcomes,
      icon: CheckCircle2,
      detail: "Care loops completed",
      tone: "green",
    },
  ];
  const attentionItems = [
    {
      label: "Emergency triage",
      value: overview?.open_emergencies ?? 0,
      href: "/agents",
      icon: AlertOctagon,
      permission: "pipeline:read",
      tone: "rose",
    },
    {
      label: "Clinical review",
      value: overview?.pending_clinician_reviews ?? 0,
      href: "/reviews",
      icon: ClipboardCheck,
      permission: "reviews:read",
      tone: "amber",
    },
    {
      label: "Overdue follow-ups",
      value: overview?.sla_breaches ?? 0,
      href: "/referrals",
      icon: GitBranch,
      permission: "referrals:read",
      tone: "blue",
    },
  ].filter((item) => hasPermission(item.permission));

  return (
    <AuthGuard requiredPermission="org:read">
      <AppShell
        title="Care overview"
        subtitle={
          session?.active_organization?.name || "Your connected care workspace"
        }
        actions={
          <div className="flex items-center gap-2">
            {hasPermission("benchmarks:read") && (
              <Link href="/benchmarks">
                <Button size="sm" variant="ghost">
                  Benchmarks
                </Button>
              </Link>
            )}
            {hasPermission("patients:read") && (
              <Link href="/patients">
                <Button size="sm">
                  <Users className="h-3.5 w-3.5" /> View participants
                </Button>
              </Link>
            )}
          </div>
        }
      >
        <div className="care-dashboard space-y-6">
          {session?.programme_configuration_status === "pending_selection" &&
            session.active_organization &&
            hasPermission("org:manage") && (
              <Card className="border-amber-200 bg-amber-50/70">
                <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-5">
                  <div>
                    <p className="text-sm font-semibold text-amber-950">
                      Legacy Multi-Programme Configuration Awaiting Selection
                    </p>
                    <p className="mt-1 text-xs text-amber-900">
                      Select your facility&apos;s primary Recova programme to complete unified platform configuration while preserving historical records.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      aria-label="Primary programme selection"
                      value={legacyProgramme}
                      onChange={(e) => setLegacyProgramme(e.target.value as Track)}
                      className="h-9 rounded-lg border border-amber-300 bg-white px-3 text-xs font-medium text-slate-900"
                    >
                      {TRACKS.map((t) => (
                        <option key={t.key} value={t.key}>
                          {t.title}
                        </option>
                      ))}
                    </select>
                    <Button
                      size="sm"
                      disabled={selectingLegacy}
                      onClick={async () => {
                        if (!session.active_organization) return;
                        setSelectingLegacy(true);
                        try {
                          await opsService.selectPrimaryProgramme(session.active_organization.id, {
                            primary_programme: legacyProgramme,
                            reason: "Administrator confirmed primary facility programme",
                          });
                          await refreshSession();
                        } finally {
                          setSelectingLegacy(false);
                        }
                      }}
                    >
                      {selectingLegacy ? "Saving..." : "Confirm Primary Programme"}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          {error && (
            <div
              role="alert"
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-red-50 p-4 text-sm text-red-800"
            >
              <span>Dashboard data could not be loaded.</span>
              <Button
                size="sm"
                variant="outline"
                onClick={() => window.location.reload()}
              >
                Try again
              </Button>
            </div>
          )}

          <section
            aria-label="Care statistics"
            className="dashboard-statistics"
          >
            {statistics.map((statistic) => (
              <div
                key={statistic.label}
                className={cn(
                  "dashboard-stat",
                  statistic.featured && "dashboard-stat-featured",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[11px] font-medium leading-relaxed">
                    {statistic.label}
                  </p>
                  <span
                    className={cn(
                      "stat-symbol",
                      statistic.featured
                        ? "stat-symbol-featured"
                        : `stat-symbol-${statistic.tone}`,
                    )}
                  >
                    <statistic.icon className="h-4 w-4" strokeWidth={1.7} />
                  </span>
                </div>
                {loading ? (
                  <div className="my-3 h-9 w-12 animate-pulse rounded-lg bg-slate-200/60" />
                ) : (
                  <p className="my-2 text-[34px] font-semibold leading-tight tracking-tight tabular-nums">
                    {statistic.value ?? "—"}
                  </p>
                )}
                <p className="text-[10px] leading-relaxed opacity-70">
                  {statistic.detail}
                </p>
              </div>
            ))}
          </section>

          <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1.8fr)_minmax(280px,1fr)]">
            <Card className="dashboard-panel min-w-0">
              <CardHeader className="gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <CardTitle>Population health</CardTitle>
                  <CardDescription className="mt-1">
                    Risk distribution across your active pathways
                  </CardDescription>
                </div>
                <div className="flex shrink-0 items-baseline gap-1.5 rounded-lg bg-slate-100 px-3 py-1.5">
                  <span className="text-lg font-semibold tabular-nums">
                    {loading ? "…" : enrollments}
                  </span>
                  <span className="text-[10px] text-slate-500">enrolments</span>
                </div>
              </CardHeader>
              <CardContent>
                <div
                  className="mb-5 flex flex-wrap gap-x-5 gap-y-2"
                  aria-label="Risk legend"
                >
                  {RISK_SERIES.map((series) => (
                    <span
                      key={series.key}
                      className="flex items-center gap-1.5 text-[10px] text-slate-600"
                    >
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ background: series.color }}
                      />
                      {series.label}
                    </span>
                  ))}
                </div>
                {loading ? (
                  <div
                    aria-label="Loading risk distribution"
                    className="h-[260px] animate-pulse rounded-xl bg-slate-100"
                  />
                ) : enrollments === 0 ? (
                  <EmptyState
                    icon={<Activity className="h-5 w-5" />}
                    title="Your population view starts here"
                    description="Enrol a participant in a care pathway to see their risk distribution."
                    action={
                      hasPermission("patients:read") && (
                        <Link
                          className="text-xs font-semibold text-teal-700"
                          href="/patients"
                        >
                          View participants →
                        </Link>
                      )
                    }
                  />
                ) : (
                  <div
                    className="risk-chart h-[260px] min-w-0"
                    role="img"
                    aria-label={`Risk distribution for ${enrollments} enrolments. ${totals.map((series) => `${series.label}: ${series.total}`).join(". ")}`}
                  >
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={chartData}
                        barSize={32}
                        margin={{ top: 12, right: 8, left: -24, bottom: 0 }}
                        accessibilityLayer
                      >
                        <defs>
                          {RISK_SERIES.map((series) => (
                            <linearGradient
                              key={series.key}
                              id={series.gradient}
                              x1="0"
                              y1="0"
                              x2="0"
                              y2="1"
                            >
                              <stop offset="0%" stopColor={series.end} />
                              <stop offset="100%" stopColor={series.color} />
                            </linearGradient>
                          ))}
                        </defs>
                        <CartesianGrid
                          vertical={false}
                          stroke="#e5edf1"
                          strokeDasharray="3 6"
                        />
                        <XAxis
                          dataKey="track"
                          axisLine={false}
                          tickLine={false}
                          tickMargin={14}
                          tick={{ fontSize: 11, fill: "#5a7d93" }}
                          height={38}
                        />
                        <YAxis
                          allowDecimals={false}
                          axisLine={false}
                          tickLine={false}
                          domain={[
                            0,
                            (dataMax: number) =>
                              Math.max(1, Math.ceil(dataMax)),
                          ]}
                          tickCount={Math.min(5, Math.max(2, enrollments + 1))}
                          tick={{ fontSize: 10, fill: "#7898aa" }}
                        />
                        <Tooltip
                          cursor={{ fill: "#003e5e05", radius: 8 }}
                          contentStyle={{
                            borderRadius: 14,
                            border: "1px solid #e2edf2",
                            boxShadow: "0 8px 32px #003e5e12",
                            fontSize: 11,
                          }}
                          labelStyle={{
                            color: "#003e5e",
                            fontWeight: 600,
                            marginBottom: 8,
                          }}
                        />
                        {RISK_SERIES.map((series) => (
                          <Bar
                            key={series.key}
                            name={series.label}
                            dataKey={series.key}
                            stackId="risk"
                            fill={`url(#${series.gradient})`}
                            radius={[5, 5, 5, 5]}
                            animationDuration={650}
                            isAnimationActive={!reduceMotion}
                          />
                        ))}
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
                <div className="mt-4 grid grid-cols-2 gap-3 border-t border-slate-100 pt-4 sm:grid-cols-4">
                  {totals.map((series) => (
                    <div key={series.key}>
                      <p className="text-lg font-semibold tabular-nums">
                        {loading ? "…" : series.total}
                      </p>
                      <p className="mt-0.5 text-[10px] text-slate-500">
                        {series.label}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card className="dashboard-panel flex flex-col">
              <CardHeader>
                <CardTitle>Needs your attention</CardTitle>
                <CardDescription>Next steps for your care team</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col">
                <div className="space-y-2">
                  {attentionItems.map((item) => (
                    <Link
                      key={item.label}
                      href={item.href}
                      className="attention-row group"
                    >
                      <span
                        className={cn(
                          "stat-symbol h-10 w-10 shrink-0",
                          `stat-symbol-${item.tone}`,
                        )}
                      >
                        <item.icon className="h-4 w-4" strokeWidth={1.7} />
                      </span>
                      <span className="min-w-0 flex-1 text-xs font-medium">
                        {item.label}
                      </span>
                      <span className="text-lg font-semibold tabular-nums">
                        {loading ? "…" : item.value}
                      </span>
                      <ArrowRight className="h-3.5 w-3.5 text-slate-400 transition-transform group-hover:translate-x-0.5" />
                    </Link>
                  ))}
                  {attentionItems.length === 0 && (
                    <p className="py-6 text-xs text-slate-500">
                      Your role has no pending action queues.
                    </p>
                  )}
                </div>
                <div className="mt-auto pt-5">
                  <div className="rounded-xl bg-[#eef7f0] p-4">
                    <span className="mb-2 flex items-center gap-2 text-xs font-semibold text-[#32634f]">
                      <CheckCircle2 className="h-4 w-4" /> Closed-loop care
                    </span>
                    <p className="text-[11px] leading-relaxed text-[#4e7060]">
                      {overview?.verified_outcomes ?? 0} verified outcomes
                      recorded. Follow each referral through to a confirmed
                      result.
                    </p>
                    {hasPermission("referrals:read") && (
                      <Link
                        href="/referrals"
                        className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-semibold text-teal-700"
                      >
                        View care pathways <ArrowRight className="h-3 w-3" />
                      </Link>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <section aria-labelledby="pathways-title">
            <div className="mb-3 flex items-center justify-between">
              <h2 id="pathways-title" className="text-sm font-semibold">
                {isPlatformAdmin ? "Recova Sub-Engines" : "Your Registered Programme"}
              </h2>
              <span className="text-[10px] text-slate-500">
                {tracks.length} active
              </span>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {tracks.map((track) => (
                <Link
                  key={track.key}
                  href={track.href}
                  className="pathway-link group"
                >
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#eaf2f5] text-teal-700">
                    <track.icon
                      className="h-[18px] w-[18px]"
                      strokeWidth={1.6}
                    />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs font-semibold">
                      {track.title}
                    </span>
                    <span className="mt-1 block text-[10px] leading-relaxed text-slate-500">
                      {track.description}
                    </span>
                  </span>
                  <ArrowRight className="h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform group-hover:translate-x-1" />
                </Link>
              ))}
              {!isPlatformAdmin && hasPermission("org:manage") && (
                <Link
                  href="/settings"
                  className="pathway-link group border-dashed border-[#c4d7e2] bg-[#f8fbfc]"
                >
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#d7e6ed] text-[#004263]">
                    <Workflow className="h-[18px] w-[18px]" strokeWidth={1.6} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs font-semibold text-[#004263]">
                      Request another engine
                    </span>
                    <span className="mt-1 block text-[10px] leading-relaxed text-slate-500">
                      Submit an audited request to expand your center&apos;s programmes
                    </span>
                  </span>
                  <ArrowRight className="h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform group-hover:translate-x-1" />
                </Link>
              )}
            </div>
          </section>

          {isPlatformAdmin && platformOverview && (
            <section aria-labelledby="engine-command-title" className="space-y-4">
              <Card className="dashboard-panel">
                <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
                  <div>
                    <CardTitle id="engine-command-title">
                      Recova Overall Engine — 4 Sub-Dashboards &amp; Customer Centers
                    </CardTitle>
                    <CardDescription className="mt-1">
                      {platformOverview.total_centers} active centers ·{" "}
                      {platformOverview.total_active_patients} participants ·{" "}
                      {platformOverview.total_staff_members} staff users ·{" "}
                      {platformOverview.total_pipeline_runs} total runs
                    </CardDescription>
                  </div>
                  <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Sub-engine dashboards">
                    {TRACKS.map((trk) => {
                      const active = selectedSubEngine === trk.key;
                      return (
                        <button
                          key={trk.key}
                          type="button"
                          role="tab"
                          aria-selected={active}
                          onClick={() => setSelectedSubEngine(trk.key as Track)}
                          className={cn(
                            "rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors",
                            active
                              ? "bg-[#003e5e] text-[#aeff9a]"
                              : "bg-[#f0f6f9] text-[#2a4558] hover:bg-[#d7e6ed]"
                          )}
                        >
                          {trk.name} ({platformOverview.sub_engines[trk.key as Track]?.total_centers ?? 0})
                        </button>
                      );
                    })}
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {(() => {
                    const sub = platformOverview.sub_engines[selectedSubEngine];
                    const meta = TRACKS.find((t) => t.key === selectedSubEngine);
                    if (!sub) return null;
                    return (
                      <>
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                          <div className="rounded-xl border border-[#e2edf2] bg-[#f8fbfc] p-3">
                            <p className="text-[10px] font-medium text-[#5a7d93]">Centers</p>
                            <p className="mt-1 text-xl font-semibold tabular-nums text-[#011621]">{sub.total_centers}</p>
                          </div>
                          <div className="rounded-xl border border-[#e2edf2] bg-[#f8fbfc] p-3">
                            <p className="text-[10px] font-medium text-[#5a7d93]">Participants</p>
                            <p className="mt-1 text-xl font-semibold tabular-nums text-[#011621]">{sub.total_patients}</p>
                          </div>
                          <div className="rounded-xl border border-[#e2edf2] bg-[#f8fbfc] p-3">
                            <p className="text-[10px] font-medium text-[#5a7d93]">Staff Users</p>
                            <p className="mt-1 text-xl font-semibold tabular-nums text-[#011621]">{sub.total_staff}</p>
                          </div>
                          <div className="rounded-xl border border-[#e2edf2] bg-[#f8fbfc] p-3">
                            <p className="text-[10px] font-medium text-[#5a7d93]">Engine Runs</p>
                            <p className="mt-1 text-xl font-semibold tabular-nums text-[#011621]">{sub.total_runs}</p>
                          </div>
                          <div className="rounded-xl border border-[#e2edf2] bg-[#f8fbfc] p-3">
                            <p className="text-[10px] font-medium text-[#5a7d93]">Open Emergencies</p>
                            <p className="mt-1 text-xl font-semibold tabular-nums text-[#ef4444]">{sub.open_emergencies}</p>
                          </div>
                        </div>

                        {sub.centers.length === 0 ? (
                          <EmptyState
                            title={`No centers registered for ${meta?.title || selectedSubEngine}`}
                            description="Centers selecting this primary programme during onboarding will appear here with their live metrics."
                          />
                        ) : (
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead>Customer Center</TableHead>
                                <TableHead>Type / Emirate</TableHead>
                                <TableHead>Participants</TableHead>
                                <TableHead>Staff</TableHead>
                                <TableHead>Runs</TableHead>
                                <TableHead>Emergencies</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {sub.centers.map((center) => (
                                <TableRow key={center.id}>
                                  <TableCell className="text-xs font-semibold text-[#011621]">
                                    {center.name}
                                  </TableCell>
                                  <TableCell className="text-xs text-[#5a7d93]">
                                    {center.org_type} · {center.emirate || "UAE"}
                                  </TableCell>
                                  <TableCell className="text-xs font-medium tabular-nums">{center.active_patients}</TableCell>
                                  <TableCell className="text-xs tabular-nums">{center.staff_members}</TableCell>
                                  <TableCell className="text-xs tabular-nums">{center.total_runs}</TableCell>
                                  <TableCell className="text-xs font-semibold tabular-nums text-[#ef4444]">
                                    {center.open_emergencies}
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        )}
                      </>
                    );
                  })()}

                  <div className="border-t border-[#e2edf2] pt-4">
                    <div className="mb-2 flex items-center justify-between">
                      <h3 className="text-xs font-semibold text-[#011621]">
                        6-Agent Engine Telemetry (All Sub-Engines)
                      </h3>
                      <Link href="/agents" className="text-[11px] font-semibold text-[#003e5e] hover:underline">
                        Open Agent Monitor →
                      </Link>
                    </div>
                    <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
                      {Object.entries(platformOverview.agent_telemetry).map(([agentKey, counts]) => (
                        <div key={agentKey} className="rounded-xl border border-[#e2edf2] bg-white p-3">
                          <p className="truncate text-[10px] font-bold uppercase tracking-wider text-[#003e5e]">
                            {agentKey.replace(/_/g, " ")}
                          </p>
                          <div className="mt-1.5 space-y-0.5 text-[11px] tabular-nums text-[#5a7d93]">
                            {Object.entries(counts).map(([st, cnt]) => (
                              <p key={st} className="flex justify-between">
                                <span>{st}</span>
                                <strong className="text-[#011621]">{cnt}</strong>
                              </p>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </section>
          )}

          {hasPermission("pipeline:read") && (
            <Card className="dashboard-panel">
              <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>Recent activity</CardTitle>
                  <CardDescription className="mt-1">
                    Latest assessments across your care pathways
                  </CardDescription>
                </div>
                <Link
                  href="/agents"
                  className="inline-flex items-center gap-2 text-[11px] font-semibold text-teal-700"
                >
                  View all activity <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="h-24 animate-pulse rounded-xl bg-slate-100" />
                ) : runs.length === 0 ? (
                  <EmptyState
                    title="Ready for your first assessment"
                    description="Add a check-in, screening or wearable observation to start a care assessment."
                  />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Pathway</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Risk tier</TableHead>
                        <TableHead>Recorded</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {runs.map((run) => (
                        <TableRow key={run.id}>
                          <TableCell>
                            <span className="inline-flex items-center gap-2 text-xs font-semibold">
                              <span className="rounded-lg bg-slate-100 p-2 text-teal-700">
                                <Activity className="h-3.5 w-3.5" />
                              </span>
                              {TRACKS.find((track) => track.key === run.track)
                                ?.title || run.track}
                            </span>
                          </TableCell>
                          <TableCell>
                            <StatusBadge status={run.status} />
                          </TableCell>
                          <TableCell>
                            {run.risk_tier ? (
                              <RiskBadge tier={run.risk_tier} />
                            ) : (
                              "Awaiting score"
                            )}
                          </TableCell>
                          <TableCell className="whitespace-nowrap text-xs text-slate-500">
                            {formatDateTime(run.created_at)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </AppShell>
    </AuthGuard>
  );
}
