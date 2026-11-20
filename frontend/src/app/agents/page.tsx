"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { AlertOctagon, Radio, RefreshCw } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useRealtimeEvents } from "@/hooks/useRealtimeEvents";
import { engineService } from "@/services/engine";
import type {
  EmergencyEvent,
  PipelineRun,
  PipelineRunDetail,
} from "@/types/recova";
import { formatDateTime, formatLabel } from "@/lib/utils";
import { AgentExecutionGraph } from "@/components/AgentExecutionGraph";
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
import { useToast } from "@/components/ui/toast";

function AgentsMonitoringPageWorkspace() {
  const { hasPermission } = useAuth();
  const { pushToast } = useToast();
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<PipelineRunDetail | null>(
    null,
  );
  const [emergencies, setEmergencies] = useState<EmergencyEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const selectedId = useRef<string | null>(null);
  const refreshing = useRef(false);
  useEffect(() => {
    selectedId.current = selectedRun?.id || null;
  }, [selectedRun?.id]);

  const loadData = useCallback(async () => {
    if (refreshing.current) return;
    refreshing.current = true;
    try {
      const [runsPage, emList] = await Promise.all([
        engineService.listRuns({ page: 1, page_size: 25 }),
        engineService.listEmergencies(),
      ]);
      setRuns(runsPage.items);
      setEmergencies(emList);
      const target = selectedId.current || runsPage.items[0]?.id;
      if (target) {
        selectedId.current = target;
        const detail = await engineService.getRun(target);
        if (selectedId.current === target) setSelectedRun(detail);
      }
    } catch (e) {
      pushToast(
        "Could not refresh pipeline state",
        "error",
        e instanceof Error ? e.message : undefined,
      );
    } finally {
      refreshing.current = false;
    }
  }, [pushToast]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadData();
    }, 0);
    const fallback = setInterval(() => void loadData(), 15000);
    return () => {
      clearTimeout(timer);
      clearInterval(fallback);
    };
  }, [loadData]);

  const { connected, events } = useRealtimeEvents(true, () => {
    void loadData();
  });

  const handleEmergencyAction = async (
    id: string,
    action: "acknowledge" | "resolve",
  ) => {
    setBusy(true);
    try {
      await engineService.resolveEmergency(
        id,
        action,
        action === "resolve"
          ? "Clinician verified acute triage resolution"
          : "Clinician acknowledged alert",
      );
      pushToast(`Emergency ${action}d`, "success");
      await loadData();
    } catch (err) {
      pushToast(
        "Emergency action failed",
        "error",
        err instanceof Error ? err.message : undefined,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell
      title="Six-Agent Pipeline Monitor & Emergency Console"
      subtitle="Live execution traces, SSE telemetry stream, and Gate 2 red-flag triage queue."
      actions={
        <Button size="sm" variant="outline" onClick={() => void loadData()}>
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </Button>
      }
    >
      <div className="space-y-6">
        {/* Gate 2 Emergency Queue */}
        <Card
          className={
            emergencies.some((e) => e.status === "open") ? "border-red-300" : ""
          }
        >
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertOctagon className="h-4 w-4 text-red-600" />
              Gate 2 Emergency Red-Flag Escalations ({emergencies.length})
            </CardTitle>
            <CardDescription>
              Deterministic acute crises bypass routine Agents 3–5 and escalate
              directly to STAT emergency triage.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {emergencies.length === 0 ? (
              <p className="text-xs text-slate-500">
                No emergency bypass events recorded.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Track</TableHead>
                    <TableHead>Rule Codes</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Detected At</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {emergencies.map((em) => (
                    <TableRow key={em.id}>
                      <TableCell className="text-xs uppercase font-semibold">
                        {em.track}
                      </TableCell>
                      <TableCell className="text-xs font-mono">
                        {em.rule_codes.join(", ")}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={em.status} />
                      </TableCell>
                      <TableCell className="text-xs text-slate-500">
                        {formatDateTime(em.created_at)}
                      </TableCell>
                      <TableCell className="text-right space-x-1.5">
                        {hasPermission("reviews:sign") &&
                          em.status === "open" && (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={busy}
                              onClick={() =>
                                void handleEmergencyAction(em.id, "acknowledge")
                              }
                            >
                              Acknowledge
                            </Button>
                          )}
                        {hasPermission("reviews:sign") &&
                          em.status !== "resolved" && (
                            <Button
                              size="sm"
                              disabled={busy}
                              onClick={() =>
                                void handleEmergencyAction(em.id, "resolve")
                              }
                            >
                              Resolve
                            </Button>
                          )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {selectedRun && (
          <AgentExecutionGraph
            run={selectedRun}
            canInspect={hasPermission("agents:inspect")}
          />
        )}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <Card className="lg:col-span-8">
            <CardHeader>
              <CardTitle>Pipeline Execution Log ({runs.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {runs.length === 0 ? (
                <EmptyState
                  icon={<Radio className="h-5 w-5" />}
                  title="No pipeline executions yet"
                  description="Trigger a check-in, screening, wearable batch, or cognitive assessment to inspect step-by-step agent graphs."
                />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Run ID</TableHead>
                      <TableHead>Track</TableHead>
                      <TableHead>Trigger</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Tier</TableHead>
                      <TableHead>Time</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {runs.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell className="font-mono text-xs">
                          {r.id.slice(0, 8)}
                        </TableCell>
                        <TableCell className="text-xs uppercase font-medium">
                          {r.track}
                        </TableCell>
                        <TableCell className="text-xs">
                          {formatLabel(r.trigger)}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={r.status} />
                        </TableCell>
                        <TableCell>
                          {r.risk_tier ? <RiskBadge tier={r.risk_tier} /> : "—"}
                        </TableCell>
                        <TableCell className="text-xs text-slate-500">
                          {formatDateTime(r.created_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={async () =>
                              setSelectedRun(await engineService.getRun(r.id))
                            }
                          >
                            Inspect Graph
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <Card className="lg:col-span-4">
            <CardHeader>
              <CardTitle>
                Live SSE Telemetry ({connected ? "Connected" : "Idle"})
              </CardTitle>
              <CardDescription>
                Real-time organisation event stream
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="max-h-72 space-y-2 overflow-y-auto text-xs">
                {events.length === 0 ? (
                  <p className="text-slate-500">
                    Listening for pipeline &amp; referral updates...
                  </p>
                ) : (
                  events.map((ev, i) => (
                    <div
                      key={`${ev.timestamp}-${i}`}
                      className="rounded border border-slate-100 bg-slate-50 p-2"
                    >
                      <div className="font-semibold text-teal-800">
                        {ev.type}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        {formatDateTime(ev.timestamp)}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

export default function AgentsMonitoringPage() {
  return (
    <AuthGuard requiredPermission="pipeline:read">
      <AgentsMonitoringPageWorkspace />
    </AuthGuard>
  );
}
