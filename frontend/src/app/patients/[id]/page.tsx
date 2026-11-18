"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { FileCode2, MailPlus, Play, RotateCcw, ShieldCheck } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import { engineService } from "@/services/engine";
import { patientsService } from "@/services/patients";
import { signalsService } from "@/services/signals";
import type {
  Consent,
  ConsentScope,
  MetricCatalogEntry,
  Observation,
  PatientDetail,
  PersonalBaseline,
  PipelineRun,
  PipelineRunDetail,
  Track,
} from "@/types/recova";
import { formatDate, formatDateTime, formatLabel } from "@/lib/utils";
import { AgentExecutionGraph } from "@/components/AgentExecutionGraph";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { FhirBundleModal } from "@/components/FhirBundleModal";
import { LongitudinalTrendChart } from "@/components/LongitudinalTrendChart";
import { RiskBadge, StatusBadge } from "@/components/RiskBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";

const CONSENT_SCOPES: ConsentScope[] = [
  "data_processing",
  "wearable_ingestion",
  "llm_synthesis",
  "family_notification",
  "hie_sharing",
  "supervisor_identifiable",
];

export default function PatientDetailPage() {
  const params = useParams<{ id: string }>();
  const patientId = params?.id || "";
  const { hasPermission } = useAuth();
  const { pushToast } = useToast();

  const [tab, setTab] = useState("overview");
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [consents, setConsents] = useState<Consent[]>([]);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [catalog, setCatalog] = useState<MetricCatalogEntry[]>([]);
  const [baselines, setBaselines] = useState<PersonalBaseline[]>([]);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<PipelineRunDetail | null>(null);
  const [fhirOpen, setFhirOpen] = useState(false);

  // Quick manual observation
  const [metricCode, setMetricCode] = useState("sleep_duration_hours");
  const [metricValue, setMetricValue] = useState("7.2");
  const [obsTrack, setObsTrack] = useState<Track>("core");
  const [newScope, setNewScope] = useState<ConsentScope>("data_processing");
  const [busy, setBusy] = useState(false);

  const loadAll = useCallback(async () => {
    if (!patientId) return;
    try {
      const [pat, cons, obsPage, cat, base, runsPage] = await Promise.all([
        patientsService.get(patientId),
        hasPermission("consents:read") ? patientsService.listConsents(patientId) : Promise.resolve([]),
        hasPermission("observations:read")
          ? signalsService.listObservations(patientId, { page: 1, page_size: 100 })
          : Promise.resolve({ items: [], total: 0, page: 1, page_size: 100, pages: 0 }),
        hasPermission("observations:read") ? signalsService.catalog() : Promise.resolve([]),
        hasPermission("observations:read") ? engineService.listBaselines(patientId) : Promise.resolve([]),
        hasPermission("pipeline:read")
          ? engineService.listRuns({ patient_id: patientId, page_size: 15 }).then((r) => r.items)
          : Promise.resolve([]),
      ]);
      setPatient(pat);
      setConsents(cons);
      setObservations(obsPage.items);
      setCatalog(cat);
      setBaselines(base);
      setRuns(runsPage);
      if (pat.enrollments.length > 0) {
        setObsTrack(pat.enrollments[0].track as Track);
      }
      if (runsPage.length > 0) {
        setSelectedRun(await engineService.getRun(runsPage[0].id));
      }
    } catch (err) {
      pushToast("Failed to load patient chart", "error", err instanceof Error ? err.message : undefined);
    }
  }, [patientId, hasPermission, pushToast]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadAll();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadAll]);

  const handleGrantConsent = async () => {
    setBusy(true);
    try {
      await patientsService.grantConsent({
        patient_id: patientId,
        scope: newScope,
        method: "electronic",
        granted_by_name: patient ? `${patient.given_name} ${patient.family_name}` : undefined,
      });
      pushToast(`Consent granted: ${newScope}`, "success");
      await loadAll();
    } catch (err) {
      pushToast("Failed to grant consent", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleRevokeConsent = async (consentId: string) => {
    setBusy(true);
    try {
      await patientsService.revokeConsent(consentId, "Clinician / participant requested revocation");
      pushToast("Consent revoked", "info");
      await loadAll();
    } catch (err) {
      pushToast("Revocation failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleAddObservation = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await signalsService.recordObservation({
        patient_id: patientId,
        track: obsTrack,
        metric_code: metricCode,
        value_num: Number(metricValue),
        effective_at: new Date().toISOString(),
        source: "manual",
      });
      pushToast("Observation recorded", "success");
      await loadAll();
    } catch (err) {
      pushToast("Observation failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleTriggerPipeline = async () => {
    setBusy(true);
    try {
      const rd = await engineService.triggerRun({ patient_id: patientId, track: obsTrack, trigger: "manual" });
      setSelectedRun(rd);
      pushToast("Pipeline executed", "success", `Risk Tier: ${rd.risk_tier || rd.status}`);
      await loadAll();
    } catch (err) {
      pushToast("Pipeline run failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleResetBaseline = async () => {
    setBusy(true);
    try {
      const res = await engineService.resetBaseline(patientId);
      pushToast("Baseline reset", "info", `${res.reset_count} metric baseline(s) marked reset.`);
      await loadAll();
    } catch (err) {
      pushToast("Reset failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleIssuePortalInvite = async () => {
    const email = window.prompt("Enter participant recipient email for the 72h portal invitation:");
    if (!email || !email.includes("@")) {
      if (email !== null) {
        pushToast("Valid email required", "error", "Enter a valid recipient email to bind the portal invitation.");
      }
      return;
    }
    setBusy(true);
    try {
      const res = await api.post<{ invitation_token: string; expires_at: string }>(
        `/patients/${patientId}/portal-invitations?recipient_email=${encodeURIComponent(email)}`
      );
      pushToast("Portal invitation issued (72h expiry)", "success", `Token: ${res.invitation_token.slice(0, 12)}…`);
    } catch (err) {
      pushToast("Could not issue invitation", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const fullName = patient ? `${patient.given_name} ${patient.family_name}` : "Participant Chart";

  return (
    <AuthGuard requiredPermission="patients:read">
      <AppShell
        title={fullName}
        subtitle={patient ? `MRN ${patient.mrn} · ${formatLabel(patient.participant_type)} · Registered ${formatDate(patient.created_at)}` : "Loading chart..."}
        actions={
          <div className="flex flex-wrap gap-2">
            {hasPermission("patients:write") && patient && (
              <Button size="sm" variant="outline" onClick={() => void handleIssuePortalInvite()} disabled={busy}>
                <MailPlus className="h-4 w-4" /> Issue Portal Invite
              </Button>
            )}
            {hasPermission("fhir:export") && patient && (
              <Button size="sm" variant="outline" onClick={() => setFhirOpen(true)}>
                <FileCode2 className="h-4 w-4" /> FHIR R4 Bundle
              </Button>
            )}
            {hasPermission("pipeline:run") && patient && (
              <Button size="sm" onClick={() => void handleTriggerPipeline()} disabled={busy}>
                <Play className="h-4 w-4" /> Run {obsTrack.toUpperCase()} Pipeline
              </Button>
            )}
          </div>
        }
      >
        {patient && (
          <div className="space-y-6">
            <Card>
              <CardContent className="grid grid-cols-2 gap-4 pt-5 sm:grid-cols-5 text-xs">
                <div>
                  <span className="text-slate-400 block">Masked Phone</span>
                  <strong>{patient.phone_masked || "—"}</strong>
                </div>
                <div>
                  <span className="text-slate-400 block">Masked Email</span>
                  <strong>{patient.email_masked || "—"}</strong>
                </div>
                <div>
                  <span className="text-slate-400 block">Language / Sex</span>
                  <strong>{patient.preferred_language.toUpperCase()} · {formatLabel(patient.sex)}</strong>
                </div>
                <div>
                  <span className="text-slate-400 block">Neuro Profile</span>
                  <strong>{formatLabel(patient.education_level || "unspecified")} / {formatLabel(patient.hearing_status)}</strong>
                </div>
                <div>
                  <span className="text-slate-400 block">Active Tracks</span>
                  <div className="mt-0.5 flex flex-wrap gap-1">
                    {patient.enrollments.map((e) => (
                      <Badge key={e.id} variant="outline" className="uppercase text-[10px]">
                        {e.track}
                      </Badge>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            <Tabs value={tab} onValueChange={setTab}>
              <TabsList>
                <TabsTrigger value="overview">Longitudinal Charts &amp; Engine</TabsTrigger>
                <TabsTrigger value="consents">Consent Governance ({consents.length})</TabsTrigger>
                <TabsTrigger value="observations">Observations ({observations.length})</TabsTrigger>
                <TabsTrigger value="baselines">Personal Baselines ({baselines.length})</TabsTrigger>
              </TabsList>

              <TabsContent value="overview" className="space-y-6">
                <LongitudinalTrendChart observations={observations} baselines={baselines} />
                {selectedRun && (
                  <AgentExecutionGraph run={selectedRun} canInspect={hasPermission("agents:inspect")} />
                )}
                {runs.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle>Run History ({runs.length})</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Track</TableHead>
                            <TableHead>Trigger</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead>Tier</TableHead>
                            <TableHead>Timestamp</TableHead>
                            <TableHead />
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {runs.map((r) => (
                            <TableRow key={r.id}>
                              <TableCell className="text-xs uppercase font-semibold">{r.track}</TableCell>
                              <TableCell className="text-xs">{formatLabel(r.trigger)}</TableCell>
                              <TableCell><StatusBadge status={r.status} /></TableCell>
                              <TableCell>{r.risk_tier ? <RiskBadge tier={r.risk_tier} /> : "—"}</TableCell>
                              <TableCell className="text-xs text-slate-500">{formatDateTime(r.created_at)}</TableCell>
                              <TableCell className="text-right">
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={async () => setSelectedRun(await engineService.getRun(r.id))}
                                >
                                  Inspect
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="consents" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <ShieldCheck className="h-4 w-4 text-teal-700" />
                      Gate 1 Consent Controls
                    </CardTitle>
                    <CardDescription>
                      Revoking <code>data_processing</code> immediately blocks routine pipeline processing at Gate 1.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {hasPermission("consents:write") && (
                      <div className="flex flex-wrap items-end gap-3">
                        <div className="w-64 space-y-1">
                          <Label>Consent Scope</Label>
                          <Select value={newScope} onChange={(e) => setNewScope(e.target.value as ConsentScope)}>
                            {CONSENT_SCOPES.map((s) => (
                              <option key={s} value={s}>{s}</option>
                            ))}
                          </Select>
                        </div>
                        <Button onClick={() => void handleGrantConsent()} disabled={busy}>
                          Grant Electronic Consent
                        </Button>
                      </div>
                    )}

                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Scope</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Method</TableHead>
                          <TableHead>Effective At</TableHead>
                          <TableHead />
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {consents.map((c) => (
                          <TableRow key={c.id}>
                            <TableCell className="font-mono text-xs">{c.scope}</TableCell>
                            <TableCell><StatusBadge status={c.status} /></TableCell>
                            <TableCell className="text-xs">{formatLabel(c.method)}</TableCell>
                            <TableCell className="text-xs text-slate-500">{formatDateTime(c.effective_at)}</TableCell>
                            <TableCell className="text-right">
                              {c.status === "granted" && hasPermission("consents:write") && (
                                <Button size="sm" variant="destructive" onClick={() => void handleRevokeConsent(c.id)}>
                                  Revoke
                                </Button>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="observations" className="space-y-4">
                {hasPermission("observations:write") && (
                  <Card>
                    <CardHeader>
                      <CardTitle>Record Single Metric Observation</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <form onSubmit={handleAddObservation} className="flex flex-wrap items-end gap-3">
                        <div className="w-60 space-y-1">
                          <Label>Biomarker / Signal</Label>
                          <Select value={metricCode} onChange={(e) => setMetricCode(e.target.value)}>
                            {(catalog.length > 0
                              ? catalog
                              : [{ code: "sleep_duration_hours", label: "Sleep Duration", unit: "h" }]
                            ).map((c) => (
                              <option key={c.code} value={c.code}>
                                {c.label} ({c.unit})
                              </option>
                            ))}
                          </Select>
                        </div>
                        <div className="w-32 space-y-1">
                          <Label>Value</Label>
                          <Input type="number" step="0.01" required value={metricValue} onChange={(e) => setMetricValue(e.target.value)} />
                        </div>
                        <div className="w-36 space-y-1">
                          <Label>Track</Label>
                          <Select value={obsTrack} onChange={(e) => setObsTrack(e.target.value as Track)}>
                            <option value="core">Core</option>
                            <option value="loop">Loop</option>
                            <option value="neuro">Neuro</option>
                            <option value="worksafe">WorkSafe</option>
                          </Select>
                        </div>
                        <Button type="submit" disabled={busy}>Record Observation</Button>
                      </form>
                    </CardContent>
                  </Card>
                )}

                <Card>
                  <CardContent className="pt-5">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Metric</TableHead>
                          <TableHead>Value</TableHead>
                          <TableHead>Source</TableHead>
                          <TableHead>Effective At</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {observations.map((o) => (
                          <TableRow key={o.id}>
                            <TableCell className="text-xs font-medium">{formatLabel(o.metric_code)}</TableCell>
                            <TableCell className="text-xs tabular-nums">
                              {o.value_num ?? o.value_text ?? "—"} {o.unit || ""}
                            </TableCell>
                            <TableCell className="text-xs">{formatLabel(o.source)}</TableCell>
                            <TableCell className="text-xs text-slate-500">{formatDateTime(o.effective_at)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="baselines" className="space-y-4">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                      <CardTitle>Personal Longitudinal Baselines (Initial 3–5 Stable Windows)</CardTitle>
                      <CardDescription>Computed deterministically by Agent 4 per metric.</CardDescription>
                    </div>
                    {hasPermission("reviews:sign") && (
                      <Button size="sm" variant="outline" onClick={() => void handleResetBaseline()} disabled={busy}>
                        <RotateCcw className="h-3.5 w-3.5" /> Reset Baselines
                      </Button>
                    )}
                  </CardHeader>
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Metric</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Windows</TableHead>
                          <TableHead>Mean</TableHead>
                          <TableHead>Sample SD</TableHead>
                          <TableHead>Algo</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {baselines.map((b) => (
                          <TableRow key={b.id}>
                            <TableCell className="text-xs font-medium">{formatLabel(b.metric_code)}</TableCell>
                            <TableCell><StatusBadge status={b.status} /></TableCell>
                            <TableCell className="text-xs tabular-nums">{b.n_windows}</TableCell>
                            <TableCell className="text-xs tabular-nums">{b.mean.toFixed(2)}</TableCell>
                            <TableCell className="text-xs tabular-nums">{b.sample_sd.toFixed(2)}</TableCell>
                            <TableCell className="text-xs">v{b.algorithm_version}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        )}

        {patient && (
          <FhirBundleModal
            patientId={patient.id}
            patientLabel={fullName}
            open={fhirOpen}
            onOpenChange={setFhirOpen}
          />
        )}
      </AppShell>
    </AuthGuard>
  );
}
