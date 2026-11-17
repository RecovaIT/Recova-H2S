"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Building2, Droplets, HardHat, Mic, MicOff, ShieldCheck, ThermometerSun } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { careService } from "@/services/care";
import { engineService } from "@/services/engine";
import { patientsService } from "@/services/patients";
import { signalsService } from "@/services/signals";
import type {
  Department,
  HeatmapRow,
  Intervention,
  PatientSummary,
  PipelineRunDetail,
  Workplace,
  WorkplaceAssessment,
} from "@/types/recova";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { AgentExecutionGraph } from "@/components/AgentExecutionGraph";
import { StatusBadge } from "@/components/RiskBadge";
import { formatDateTime, formatLabel } from "@/lib/utils";

interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  onresult: ((ev: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

export function WorkSafeWorkspace() {
  const { hasPermission } = useAuth();
  const { pushToast } = useToast();

  const [tab, setTab] = useState(
    hasPermission("observations:write") ? "readiness" : "supervisor"
  );
  const [workers, setWorkers] = useState<PatientSummary[]>([]);
  const [workplaces, setWorkplaces] = useState<Workplace[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [heatmap, setHeatmap] = useState<HeatmapRow[]>([]);
  const [envHistory, setEnvHistory] = useState<WorkplaceAssessment[]>([]);
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [latestRun, setLatestRun] = useState<PipelineRunDetail | null>(null);

  // Worker ~10s readiness check state
  const [workerId, setWorkerId] = useState("");
  const [readinessScore, setReadinessScore] = useState(8);
  const [fatigueFeeling, setFatigueFeeling] = useState<
    "fresh" | "mild_fatigue" | "exhausted" | "dizzy_heat_illness"
  >("fresh");
  const [hydrated, setHydrated] = useState(true);
  const [shiftHours, setShiftHours] = useState("6");
  const [coreTemp, setCoreTemp] = useState("37.0");
  const [voiceNote, setVoiceNote] = useState("");
  const [dictating, setDictating] = useState(false);

  // Workplace & Department creation
  const [wpName, setWpName] = useState("");
  const [wpLoc, setWpLoc] = useState("");
  const [deptName, setDeptName] = useState("");
  const [deptWpId, setDeptWpId] = useState("");
  const [minK, setMinK] = useState("5");

  // Environment assessment
  const [envDeptId, setEnvDeptId] = useState("");
  const [ambientTemp, setAmbientTemp] = useState("41");
  const [humidity, setHumidity] = useState("58");
  const [wbgt, setWbgt] = useState("31.5");

  // Intervention form
  const [ivDeptId, setIvDeptId] = useState("");
  const [ivType, setIvType] = useState<"rest_break" | "hydration" | "shift_rotation">("hydration");
  const [ivTitle, setIvTitle] = useState("");
  const [ivDetails, setIvDetails] = useState("");
  const [busy, setBusy] = useState(false);

  const loadWorksafe = useCallback(async () => {
    try {
      const [wpList, deptList, hm, envList, ivList] = await Promise.all([
        signalsService.listWorkplaces(),
        signalsService.listDepartments(),
        signalsService.getWorkforceHeatmap(),
        signalsService.listWorkplaceAssessments(),
        hasPermission("interventions:read")
          ? careService.listInterventions({ track: "worksafe" })
          : Promise.resolve([] as Intervention[]),
      ]);
      setWorkplaces(wpList);
      setDepartments(deptList);
      setHeatmap(hm);
      setEnvHistory(envList);
      setInterventions(ivList);
      if (deptList.length > 0 && !envDeptId) {
        setEnvDeptId(deptList[0].id);
        setIvDeptId(deptList[0].id);
      }
      if (wpList.length > 0 && !deptWpId) setDeptWpId(wpList[0].id);

      if (hasPermission("patients:read")) {
        const wPage = await patientsService.list({ track: "worksafe", page_size: 100 });
        setWorkers(wPage.items);
        if (wPage.items.length > 0 && !workerId) setWorkerId(wPage.items[0].id);
      }
    } catch (err) {
      pushToast("Failed to load WorkSafe data", "error", err instanceof Error ? err.message : undefined);
    }
  }, [hasPermission, pushToast, envDeptId, deptWpId, workerId]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadWorksafe();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadWorksafe]);

  const handleReadinessSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workerId) return;
    setBusy(true);
    try {
      const res = await signalsService.submitWorkerReadiness({
        patient_id: workerId,
        readiness_score: readinessScore,
        fatigue_feeling: fatigueFeeling,
        hydrated,
        shift_duration_hours: Number(shiftHours),
        core_temp_est_c: Number(coreTemp),
        voice_note: voiceNote.trim() || undefined,
        trigger_pipeline: true,
      });
      pushToast("10-second worker readiness logged", "success");
      setVoiceNote("");
      if (res.run_id) {
        setLatestRun(await engineService.getRun(res.run_id));
      }
      await loadWorksafe();
    } catch (err) {
      pushToast("Readiness check failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const startSpeechDictation = () => {
    const win = window as unknown as {
      SpeechRecognition?: new () => SpeechRecognitionLike;
      webkitSpeechRecognition?: new () => SpeechRecognitionLike;
    };
    const Ctor = win.SpeechRecognition || win.webkitSpeechRecognition;
    if (!Ctor) {
      pushToast("Speech recognition unavailable in this browser; please type shift note.", "info");
      return;
    }
    const rec = new Ctor();
    const currentWorker = workers.find((w) => w.id === workerId);
    rec.lang = currentWorker?.preferred_language === "ar" ? "ar-AE" : "en-US";
    rec.interimResults = false;
    setDictating(true);
    rec.onresult = (ev) => {
      const spoken = ev.results[0]?.[0]?.transcript || "";
      setVoiceNote((prev) => (prev ? `${prev} ${spoken}` : spoken));
    };
    rec.onend = () => setDictating(false);
    rec.start();
  };

  const handleCreateWorkplace = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await signalsService.createWorkplace({ name: wpName.trim(), location: wpLoc.trim() || undefined });
      setWpName("");
      setWpLoc("");
      pushToast("Workplace site created", "success");
      await loadWorksafe();
    } catch (err) {
      pushToast("Create workplace failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleCreateDepartment = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await signalsService.createDepartment({
        name: deptName.trim(),
        workplace_id: deptWpId || undefined,
        min_group_size_for_reporting: Number(minK),
      });
      setDeptName("");
      pushToast("Department added with k-anonymity floor", "success");
      await loadWorksafe();
    } catch (err) {
      pushToast("Create department failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleRecordEnv = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const created = await signalsService.createWorkplaceAssessment({
        department_id: envDeptId || undefined,
        ambient_temp_c: Number(ambientTemp),
        relative_humidity_pct: Number(humidity),
        wbgt_c: Number(wbgt),
      });
      pushToast("Environment reading saved", "success", `Computed Rothfusz Heat Index: ${created.heat_index_c ?? "—"} °C`);
      await loadWorksafe();
    } catch (err) {
      pushToast("Environment capture failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleCreateIntervention = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await careService.createIntervention({
        track: "worksafe",
        department_id: ivDeptId || undefined,
        intervention_type: ivType,
        title: ivTitle.trim() || `${formatLabel(ivType)} protocol`,
        details: ivDetails.trim() || undefined,
      });
      setIvTitle("");
      setIvDetails("");
      pushToast("WorkSafe intervention scheduled", "success");
      await loadWorksafe();
    } catch (err) {
      pushToast("Intervention creation failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const completeIntervention = async (id: string) => {
    try {
      await careService.updateIntervention(id, { status: "completed" });
      pushToast("Intervention marked completed", "success");
      await loadWorksafe();
    } catch (err) {
      pushToast("Update failed", "error", err instanceof Error ? err.message : undefined);
    }
  };

  return (
    <Tabs value={tab} onValueChange={setTab}>
      <TabsList>
        {hasPermission("observations:write") && (
          <TabsTrigger value="readiness">10s Worker Readiness</TabsTrigger>
        )}
        <TabsTrigger value="supervisor">Supervisor Heatmap &amp; Heat Stress</TabsTrigger>
        {hasPermission("workforce:manage") && (
          <TabsTrigger value="setup">Sites &amp; k-Anonymity Departments</TabsTrigger>
        )}
      </TabsList>

      {/* Mobile-First ~10s Worker Readiness */}
      <TabsContent value="readiness" className="space-y-4">
        <Card className="mx-auto max-w-2xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <HardHat className="h-5 w-5 text-amber-600" />
              10-Second Shift Readiness &amp; Heat-Stress Check
            </CardTitle>
            <CardDescription>
              High-contrast touch capture. Reporting dizzy / confused / heat illness immediately triggers Gate 2 Emergency Bypass.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {workers.length === 0 ? (
              <Alert variant="warning">
                No employees enrolled in WorkSafe yet. Register an employee on the Participants page first.
              </Alert>
            ) : (
              <form onSubmit={handleReadinessSubmit} className="space-y-4">
                <div className="space-y-1">
                  <Label>Worker / Employee</Label>
                  <Select value={workerId} onChange={(e) => setWorkerId(e.target.value)}>
                    {workers.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.given_name} {w.family_name} ({w.mrn})
                      </option>
                    ))}
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label>How do you feel right now?</Label>
                  <div className="grid grid-cols-2 gap-2.5">
                    {[
                      { val: "fresh", label: "Fresh & Ready", cls: "border-emerald-300 bg-emerald-50 text-emerald-900" },
                      { val: "mild_fatigue", label: "Mild Fatigue", cls: "border-amber-300 bg-amber-50 text-amber-900" },
                      { val: "exhausted", label: "Exhausted / Cramping", cls: "border-orange-400 bg-orange-50 text-orange-950" },
                      { val: "dizzy_heat_illness", label: "Dizzy / Heat Illness", cls: "border-red-500 bg-red-50 text-red-950" },
                    ].map((opt) => (
                      <button
                        key={opt.val}
                        type="button"
                        onClick={() => setFatigueFeeling(opt.val as typeof fatigueFeeling)}
                        className={`rounded-xl border-2 p-3 text-left text-xs font-semibold cursor-pointer ${
                          fatigueFeeling === opt.val
                            ? `${opt.cls} ring-2 ring-slate-900`
                            : "border-slate-200 bg-white text-slate-600"
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div className="space-y-1">
                    <Label>Readiness (0-10)</Label>
                    <Input type="number" min={0} max={10} value={readinessScore} onChange={(e) => setReadinessScore(Number(e.target.value))} />
                  </div>
                  <div className="space-y-1">
                    <Label>Shift Hours</Label>
                    <Input type="number" step="0.5" value={shiftHours} onChange={(e) => setShiftHours(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>Est. Core Temp (°C)</Label>
                    <Input type="number" step="0.1" value={coreTemp} onChange={(e) => setCoreTemp(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>Hydrated?</Label>
                    <button
                      type="button"
                      onClick={() => setHydrated((h) => !h)}
                      className={`flex h-9 w-full items-center justify-center gap-1.5 rounded-lg border text-xs font-semibold cursor-pointer ${
                        hydrated
                          ? "border-sky-300 bg-sky-50 text-sky-900"
                          : "border-amber-300 bg-amber-50 text-amber-900"
                      }`}
                    >
                      <Droplets className="h-3.5 w-3.5" />
                      {hydrated ? "Hydrated" : "Needs Water"}
                    </button>
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <Label className="flex items-center gap-1.5">
                      <Mic className="h-3.5 w-3.5 text-slate-500" /> Optional Voice / Shift Note
                    </Label>
                    <Button
                      type="button"
                      size="sm"
                      variant={dictating ? "destructive" : "outline"}
                      onClick={startSpeechDictation}
                      className="h-7 text-xs flex items-center gap-1.5"
                    >
                      {dictating ? <MicOff className="h-3 w-3" /> : <Mic className="h-3 w-3" />}
                      {dictating ? "Listening..." : "Voice Dictate"}
                    </Button>
                  </div>
                  <Textarea value={voiceNote} onChange={(e) => setVoiceNote(e.target.value)} placeholder="Quick note (heat stress, PPE discomfort, chest tightness)..." />
                </div>

                <Button type="submit" size="lg" disabled={busy} className="w-full">
                  {busy ? "Recording..." : "Submit Readiness Check"}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>

        {latestRun && (
          <AgentExecutionGraph run={latestRun} canInspect={hasPermission("agents:inspect")} />
        )}
      </TabsContent>

      {/* Supervisor Anonymized Command View */}
      <TabsContent value="supervisor" className="space-y-6">
        <Alert variant="info" title="Worker Privacy & k-Anonymity Governance">
          Supervisors strictly receive anonymized department cluster distributions. Departments below their minimum k-anonymity threshold automatically suppress tier counts to prevent re-identification.
        </Alert>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {heatmap.length === 0 ? (
            <Card className="col-span-full">
              <CardContent className="py-8 text-center text-xs text-slate-500">
                No departments configured yet.
              </CardContent>
            </Card>
          ) : (
            heatmap.map((row) => (
              <Card key={row.department_id}>
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle>{row.department_name}</CardTitle>
                    <Badge variant="outline">{row.worker_count} workers</Badge>
                  </div>
                  <CardDescription>
                    Heat Index: {row.latest_heat_index_c !== null && row.latest_heat_index_c !== undefined ? `${row.latest_heat_index_c.toFixed(1)} °C` : "No recent sensor"} · Open Interventions: {row.open_interventions}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {row.suppressed_k_anonymity || !row.risk_counts ? (
                    <Alert variant="warning" title={`Suppressed (k < ${row.k_anonymity_threshold})`}>
                      Only {row.worker_count} enrolled worker(s); individualized risk breakdown hidden by privacy policy.
                    </Alert>
                  ) : (
                    <div className="grid grid-cols-4 gap-1.5 text-center text-xs">
                      <div className="rounded bg-emerald-50 p-2 text-emerald-900">
                        <div className="font-bold text-base">{row.risk_counts.GREEN || 0}</div>
                        <div className="text-[10px]">GREEN</div>
                      </div>
                      <div className="rounded bg-amber-50 p-2 text-amber-900">
                        <div className="font-bold text-base">{row.risk_counts.AMBER || 0}</div>
                        <div className="text-[10px]">AMBER</div>
                      </div>
                      <div className="rounded bg-red-50 p-2 text-red-900">
                        <div className="font-bold text-base">
                          {(row.risk_counts.RED || 0) + (row.risk_counts.EMERGENCY_BYPASS || 0)}
                        </div>
                        <div className="text-[10px]">RED/EMERG</div>
                      </div>
                      <div className="rounded bg-slate-100 p-2 text-slate-700">
                        <div className="font-bold text-base">{row.risk_counts.INDETERMINATE || 0}</div>
                        <div className="text-[10px]">BASELINE</div>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {hasPermission("workforce:write") && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ThermometerSun className="h-4 w-4 text-amber-600" />
                  Record Environmental Heat-Index Reading
                </CardTitle>
                <CardDescription>
                  Automatically computes Rothfusz Heat Index in Python from Ambient °C and Humidity %.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleRecordEnv} className="space-y-3">
                  <div className="space-y-1">
                    <Label>Department</Label>
                    <Select value={envDeptId} onChange={(e) => setEnvDeptId(e.target.value)}>
                      <option value="">All site areas</option>
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))}
                    </Select>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="space-y-1">
                      <Label>Ambient (°C)</Label>
                      <Input type="number" step="0.1" value={ambientTemp} onChange={(e) => setAmbientTemp(e.target.value)} />
                    </div>
                    <div className="space-y-1">
                      <Label>Humidity (%)</Label>
                      <Input type="number" step="1" value={humidity} onChange={(e) => setHumidity(e.target.value)} />
                    </div>
                    <div className="space-y-1">
                      <Label>WBGT (°C)</Label>
                      <Input type="number" step="0.1" value={wbgt} onChange={(e) => setWbgt(e.target.value)} />
                    </div>
                  </div>
                  <Button type="submit" disabled={busy}>Log Environmental Sensor Reading</Button>
                </form>

                {envHistory.length > 0 && (
                  <div className="mt-4 space-y-1.5 text-xs">
                    {envHistory.slice(0, 4).map((e) => (
                      <div key={e.id} className="flex items-center justify-between rounded border border-slate-100 bg-slate-50 px-2.5 py-1.5">
                        <span>
                          {e.ambient_temp_c}°C / {e.relative_humidity_pct}% RH → <strong>HI {e.heat_index_c}°C</strong>
                        </span>
                        <span className="text-slate-400">{formatDateTime(e.measured_at)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {hasPermission("interventions:write") && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-teal-700" />
                  Preventive Heat &amp; Fatigue Interventions
                </CardTitle>
                <CardDescription>
                  Schedule mandatory cooling rest breaks, electrolyte hydration, or shift rotations.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <form onSubmit={handleCreateIntervention} className="space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <Label>Department</Label>
                      <Select value={ivDeptId} onChange={(e) => setIvDeptId(e.target.value)}>
                        <option value="">General</option>
                        {departments.map((d) => (
                          <option key={d.id} value={d.id}>{d.name}</option>
                        ))}
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label>Intervention Type</Label>
                      <Select value={ivType} onChange={(e) => setIvType(e.target.value as typeof ivType)}>
                        <option value="hydration">Hydration Pause</option>
                        <option value="rest_break">Shaded Cooling Rest Break</option>
                        <option value="shift_rotation">Crew Shift Rotation</option>
                      </Select>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <Label>Protocol Title</Label>
                    <Input value={ivTitle} onChange={(e) => setIvTitle(e.target.value)} placeholder="15-min cooling break + electrolyte station" />
                  </div>
                  <Button type="submit" disabled={busy}>Dispatch Department Intervention</Button>
                </form>

                {interventions.length > 0 && (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Intervention</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {interventions.slice(0, 5).map((iv) => (
                        <TableRow key={iv.id}>
                          <TableCell className="text-xs font-medium">{iv.title}</TableCell>
                          <TableCell><StatusBadge status={iv.status} /></TableCell>
                          <TableCell className="text-right">
                            {iv.status !== "completed" && (
                              <Button size="sm" variant="outline" onClick={() => void completeIntervention(iv.id)}>
                                Complete
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
          )}
        </div>
      </TabsContent>

      {/* Workplaces & Departments Config */}
      {hasPermission("workforce:manage") && (
        <TabsContent value="setup" className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-slate-700" />
                Workplaces ({workplaces.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <form onSubmit={handleCreateWorkplace} className="space-y-2">
                <Input required value={wpName} onChange={(e) => setWpName(e.target.value)} placeholder="Site Name (e.g. Mussafah Solar Yard)" />
                <Input value={wpLoc} onChange={(e) => setWpLoc(e.target.value)} placeholder="Emirate / Zone" />
                <Button type="submit" disabled={busy}>Add Workplace</Button>
              </form>
              <div className="space-y-1 text-xs">
                {workplaces.map((w) => (
                  <div key={w.id} className="rounded border border-slate-100 bg-slate-50 px-2.5 py-1.5">
                    <strong>{w.name}</strong> {w.location ? `· ${w.location}` : ""}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Departments &amp; k-Anonymity Floor ({departments.length})</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <form onSubmit={handleCreateDepartment} className="space-y-2">
                <Input required value={deptName} onChange={(e) => setDeptName(e.target.value)} placeholder="Department Name (e.g. Electrical Crew A)" />
                <div className="grid grid-cols-2 gap-2">
                  <Select value={deptWpId} onChange={(e) => setDeptWpId(e.target.value)}>
                    <option value="">No specific site</option>
                    {workplaces.map((w) => (
                      <option key={w.id} value={w.id}>{w.name}</option>
                    ))}
                  </Select>
                  <Input type="number" min={3} max={50} value={minK} onChange={(e) => setMinK(e.target.value)} placeholder="Min k (5)" />
                </div>
                <Button type="submit" disabled={busy}>Add Department</Button>
              </form>
              <div className="space-y-1 text-xs">
                {departments.map((d) => (
                  <div key={d.id} className="flex justify-between rounded border border-slate-100 bg-slate-50 px-2.5 py-1.5">
                    <strong>{d.name}</strong>
                    <span className="text-slate-500">k ≥ {d.min_group_size_for_reporting}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      )}
    </Tabs>
  );
}
