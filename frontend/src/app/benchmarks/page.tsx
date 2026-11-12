"use client";

import React, { useCallback, useEffect, useState } from "react";
import { BarChart3, CheckCircle2, Play, XCircle } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { opsService } from "@/services/ops";
import type { BenchmarkRun, BenchmarkRunDetail, Track } from "@/types/recova";
import { formatDateTime, formatLabel } from "@/lib/utils";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { StatusBadge } from "@/components/RiskBadge";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";

const ALL_TRACKS: Track[] = ["core", "loop", "neuro", "worksafe"];

export default function BenchmarksPage() {
  const { hasPermission } = useAuth();
  const { pushToast } = useToast();

  const [selectedTracks, setSelectedTracks] = useState<Track[]>(ALL_TRACKS);
  const [runs, setRuns] = useState<BenchmarkRun[]>([]);
  const [detail, setDetail] = useState<BenchmarkRunDetail | null>(null);
  const [running, setRunning] = useState(false);

  const loadRuns = useCallback(async () => {
    const list = await opsService.listBenchmarkRuns();
    setRuns(list);
    if (list.length > 0) {
      setDetail(await opsService.getBenchmarkRun(list[0].id));
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadRuns();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadRuns]);

  const toggleTrack = (t: Track) => {
    setSelectedTracks((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    );
  };

  const handleRunBenchmarks = async () => {
    if (selectedTracks.length === 0) return;
    setRunning(true);
    try {
      const res = await opsService.runBenchmarks(selectedTracks, false);
      setDetail(res);
      pushToast(
        "Benchmark suite completed",
        res.passed_cases === res.total_cases ? "success" : "info",
        `${res.passed_cases} / ${res.total_cases} cases passed`
      );
      await loadRuns();
    } catch (err) {
      pushToast("Benchmark run failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setRunning(false);
    }
  };

  const m = (detail?.metrics || {}) as Record<string, number | string | null>;

  return (
    <AuthGuard requiredPermission="benchmarks:read">
      <AppShell
        title="Validation &amp; Benchmark Engine"
        subtitle="Executes isolated synthetic clinical & governance scenarios through the real six-agent backend pipeline. Zero fabricated percentages."
        actions={
          hasPermission("benchmarks:run") ? (
            <Button size="sm" onClick={() => void handleRunBenchmarks()} disabled={running || selectedTracks.length === 0}>
              <Play className="h-4 w-4" />
              {running ? "Running Validation Suite..." : "Execute Real Benchmark Run"}
            </Button>
          ) : undefined
        }
      >
        <div className="space-y-6">
          <Card>
            <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Tracks to Evaluate:
                </span>
                {ALL_TRACKS.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => toggleTrack(t)}
                    className={`rounded-lg border px-3 py-1 text-xs font-medium uppercase cursor-pointer ${
                      selectedTracks.includes(t)
                        ? "border-teal-600 bg-teal-50 text-teal-900"
                        : "border-slate-200 bg-white text-slate-500"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <span className="text-xs text-slate-500">
                Synthetic benchmark rows execute inside isolated fixtures and are cleaned from the patient registry afterwards.
              </span>
            </CardContent>
          </Card>

          {!detail ? (
            <EmptyState
              icon={<BarChart3 className="h-5 w-5" />}
              title="No benchmark validation runs recorded yet"
              description="Click 'Execute Real Benchmark Run' to evaluate sensitivity, specificity, emergency detection, missing-data handling, and mathematical consistency across all 4 tracks."
            />
          ) : (
            <>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
                <Card>
                  <CardHeader className="pb-1">
                    <CardDescription>Cases Passed</CardDescription>
                    <CardTitle className="text-xl tabular-nums">
                      {detail.passed_cases} / {detail.total_cases}
                    </CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-1">
                    <CardDescription>Drift Sensitivity</CardDescription>
                    <CardTitle className="text-xl tabular-nums">
                      {m.sensitivity_pct !== null && m.sensitivity_pct !== undefined ? `${m.sensitivity_pct}%` : "—"}
                    </CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-1">
                    <CardDescription>Drift Specificity</CardDescription>
                    <CardTitle className="text-xl tabular-nums">
                      {m.specificity_pct !== null && m.specificity_pct !== undefined ? `${m.specificity_pct}%` : "—"}
                    </CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-1">
                    <CardDescription>Emergency Accuracy</CardDescription>
                    <CardTitle className="text-xl tabular-nums">
                      {m.emergency_detection_accuracy_pct !== null && m.emergency_detection_accuracy_pct !== undefined
                        ? `${m.emergency_detection_accuracy_pct}%`
                        : "—"}
                    </CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-1">
                    <CardDescription>Math Consistency</CardDescription>
                    <CardTitle className="text-xl tabular-nums">
                      {m.scoring_consistency_pct !== null && m.scoring_consistency_pct !== undefined
                        ? `${m.scoring_consistency_pct}%`
                        : "—"}
                    </CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-1">
                    <CardDescription>Mean Latency</CardDescription>
                    <CardTitle className="text-xl tabular-nums">
                      {m.mean_duration_ms !== null && m.mean_duration_ms !== undefined
                        ? `${m.mean_duration_ms} ms`
                        : "—"}
                    </CardTitle>
                  </CardHeader>
                </Card>
              </div>

              {typeof m.note === "string" && <Alert variant="info">{m.note}</Alert>}

              <Card>
                <CardHeader>
                  <CardTitle>
                    Case-by-Case Execution Results — {detail.suite_name} v{detail.suite_version}
                  </CardTitle>
                  <CardDescription>
                    Algorithm v{detail.algorithm_version} · Executed {formatDateTime(detail.finished_at || detail.created_at)}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Case</TableHead>
                        <TableHead>Track</TableHead>
                        <TableHead>Category</TableHead>
                        <TableHead>Scenario</TableHead>
                        <TableHead>Result</TableHead>
                        <TableHead>Latency</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {detail.cases.map((c) => (
                        <TableRow key={c.id}>
                          <TableCell className="font-mono text-xs font-semibold">{c.case_id}</TableCell>
                          <TableCell className="text-xs uppercase">{c.track}</TableCell>
                          <TableCell className="text-xs">{formatLabel(c.category)}</TableCell>
                          <TableCell className="text-xs text-slate-700">{c.scenario}</TableCell>
                          <TableCell>
                            {c.passed ? (
                              <Badge variant="success">
                                <CheckCircle2 className="h-3 w-3" /> Passed
                              </Badge>
                            ) : (
                              <Badge variant="danger">
                                <XCircle className="h-3 w-3" /> {c.failure_details || "Failed"}
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-xs tabular-nums text-slate-500">
                            {c.duration_ms ? `${c.duration_ms.toFixed(1)} ms` : "—"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Historical Validation Runs ({runs.length})</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Suite</TableHead>
                        <TableHead>Tracks</TableHead>
                        <TableHead>Score</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {runs.map((r) => (
                        <TableRow key={r.id}>
                          <TableCell className="text-xs font-medium">{r.suite_name}</TableCell>
                          <TableCell className="text-xs uppercase">{r.tracks.join(", ")}</TableCell>
                          <TableCell className="text-xs font-semibold tabular-nums">
                            {r.passed_cases} / {r.total_cases}
                          </TableCell>
                          <TableCell><StatusBadge status={r.status} /></TableCell>
                          <TableCell className="text-xs text-slate-500">{formatDateTime(r.created_at)}</TableCell>
                          <TableCell className="text-right">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={async () => setDetail(await opsService.getBenchmarkRun(r.id))}
                            >
                              View Cases
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </AppShell>
    </AuthGuard>
  );
}
