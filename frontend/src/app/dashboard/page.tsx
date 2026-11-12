"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertOctagon,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  GitBranch,
  Users,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useAuth } from "@/hooks/useAuth";
import { engineService } from "@/services/engine";
import { opsService } from "@/services/ops";
import type { EmergencyEvent, OverviewReport, PipelineRun } from "@/types/recova";
import { formatDateTime } from "@/lib/utils";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { RiskBadge, StatusBadge } from "@/components/RiskBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function DashboardPage() {
  const { hasPermission, hasTrack } = useAuth();
  const [overview, setOverview] = useState<OverviewReport | null>(null);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [emergencies, setEmergencies] = useState<EmergencyEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      opsService.getOverview().catch(() => null),
      hasPermission("pipeline:read")
        ? engineService.listRuns({ page: 1, page_size: 8 }).then((r) => r.items).catch(() => [])
        : Promise.resolve([]),
      hasPermission("pipeline:read")
        ? engineService.listEmergencies("open").catch(() => [])
        : Promise.resolve([]),
    ])
      .then(([ov, rList, emList]) => {
        setOverview(ov);
        setRuns(rList);
        setEmergencies(emList);
      })
      .finally(() => setLoading(false));
  }, [hasPermission]);

  const riskChartData = overview
    ? Object.entries(overview.track_risk_distribution).map(([track, counts]) => ({
        track: track.toUpperCase(),
        GREEN: counts.GREEN || 0,
        AMBER: counts.AMBER || 0,
        RED: (counts.RED || 0) + (counts.EMERGENCY_BYPASS || 0),
        UNSCORED: (counts.UNSCORED || 0) + (counts.INDETERMINATE || 0),
      }))
    : [];

  return (
    <AuthGuard requiredPermission="org:read">
      <AppShell
        title="Clinical Operations Dashboard"
        subtitle="Real-time PostgreSQL aggregates across all active tracks, closed-loop referrals, and Gate 2 safety escalations."
        actions={
          <div className="flex gap-2">
            {hasPermission("patients:read") && (
              <Link href="/patients">
                <Button size="sm" variant="outline">
                  Manage Participants
                </Button>
              </Link>
            )}
            {hasPermission("benchmarks:read") && (
              <Link href="/benchmarks">
                <Button size="sm">Run Validation Suite</Button>
              </Link>
            )}
          </div>
        }
      >
        <div className="space-y-6">
          {/* KPI Row */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <Card>
              <CardHeader className="pb-1">
                <CardDescription className="flex items-center gap-1.5">
                  <Users className="h-3.5 w-3.5 text-teal-700" /> Active Participants
                </CardDescription>
                <CardTitle className="text-2xl tabular-nums">
                  {overview?.active_patients ?? (loading ? "…" : 0)}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card className={emergencies.length > 0 ? "border-red-300 bg-red-50/40" : ""}>
              <CardHeader className="pb-1">
                <CardDescription className="flex items-center gap-1.5 text-red-700">
                  <AlertOctagon className="h-3.5 w-3.5" /> Open Emergencies
                </CardDescription>
                <CardTitle className="text-2xl tabular-nums text-red-700">
                  {overview?.open_emergencies ?? (loading ? "…" : 0)}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardDescription className="flex items-center gap-1.5">
                  <ClipboardCheck className="h-3.5 w-3.5 text-amber-600" /> Pending Reviews
                </CardDescription>
                <CardTitle className="text-2xl tabular-nums">
                  {overview?.pending_clinician_reviews ?? (loading ? "…" : 0)}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardDescription className="flex items-center gap-1.5">
                  <GitBranch className="h-3.5 w-3.5 text-indigo-600" /> Open Referrals ({overview?.sla_breaches ?? 0} SLA breach)
                </CardDescription>
                <CardTitle className="text-2xl tabular-nums">
                  {overview?.open_referrals ?? (loading ? "…" : 0)}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardDescription className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" /> Verified Outcomes
                </CardDescription>
                <CardTitle className="text-2xl tabular-nums">
                  {overview?.verified_outcomes ?? (loading ? "…" : 0)}
                </CardTitle>
              </CardHeader>
            </Card>
          </div>

          {/* Four Track Launchers */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { key: "core", title: "Recova Core", desc: "Relapse prevention, HRV/sleep drift & daily check-ins", href: "/core" },
              { key: "loop", title: "Recova Loop", desc: "IFHAS screening, insurance routing & SLA navigation", href: "/loop" },
              { key: "neuro", title: "Recova Neuro", desc: "Audio-visual sequence activity & cognitive baselines", href: "/neuro" },
              { key: "worksafe", title: "Recova WorkSafe", desc: "10s readiness & k-anonymity heat-stress heatmaps", href: "/worksafe" },
            ]
              .filter((t) => hasTrack(t.key))
              .map((t) => (
                <Link key={t.key} href={t.href}>
                  <Card className="h-full transition-colors hover:border-teal-400">
                    <CardHeader>
                      <CardTitle className="flex items-center justify-between text-sm">
                        {t.title}
                        <ArrowRight className="h-4 w-4 text-teal-700" />
                      </CardTitle>
                      <CardDescription>{t.desc}</CardDescription>
                    </CardHeader>
                  </Card>
                </Link>
              ))}
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            {/* Risk Distribution Chart */}
            <Card className="lg:col-span-6">
              <CardHeader>
                <CardTitle>Enrolled Risk Tier Distribution by Track</CardTitle>
                <CardDescription>Computed directly from PostgreSQL track enrollments.</CardDescription>
              </CardHeader>
              <CardContent>
                {riskChartData.length === 0 ? (
                  <EmptyState
                    title="No active track enrollments yet"
                    description="Register patients or participants to see real risk distributions across Recova tracks."
                  />
                ) : (
                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={riskChartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis dataKey="track" tick={{ fontSize: 11 }} />
                        <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Legend wrapperStyle={{ fontSize: "11px" }} />
                        <Bar dataKey="GREEN" stackId="a" fill="#10b981" />
                        <Bar dataKey="AMBER" stackId="a" fill="#f59e0b" />
                        <Bar dataKey="RED" stackId="a" fill="#ef4444" />
                        <Bar dataKey="UNSCORED" stackId="a" fill="#94a3b8" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Recent Pipeline Runs */}
            <Card className="lg:col-span-6">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Activity className="h-4 w-4 text-teal-700" />
                    Recent Six-Agent Runs
                  </CardTitle>
                  <CardDescription>Total production runs: {overview?.total_pipeline_runs ?? 0}</CardDescription>
                </div>
                <Link href="/agents">
                  <Button variant="ghost" size="sm">Monitor All →</Button>
                </Link>
              </CardHeader>
              <CardContent>
                {runs.length === 0 ? (
                  <EmptyState
                    title="No pipeline executions recorded"
                    description="Submit check-ins, wearables, screenings, or cognitive sessions to execute the shared six-agent engine."
                  />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Track</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Tier</TableHead>
                        <TableHead>Time</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {runs.map((r) => (
                        <TableRow key={r.id}>
                          <TableCell className="text-xs font-medium uppercase">{r.track}</TableCell>
                          <TableCell><StatusBadge status={r.status} /></TableCell>
                          <TableCell>{r.risk_tier ? <RiskBadge tier={r.risk_tier} /> : "—"}</TableCell>
                          <TableCell className="text-xs text-slate-500">{formatDateTime(r.created_at)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </AppShell>
    </AuthGuard>
  );
}
