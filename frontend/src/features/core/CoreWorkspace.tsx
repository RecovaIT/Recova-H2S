"use client";

import React, { useCallback, useEffect, useState } from "react";
import { HeartPulse, Mic, MicOff, Play, Upload } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { careService } from "@/services/care";
import { engineService } from "@/services/engine";
import { patientsService } from "@/services/patients";
import { signalsService } from "@/services/signals";
import type {
  ClinicalReview,
  Observation,
  PatientDetail,
  PatientSummary,
  PersonalBaseline,
  PipelineRunDetail,
  Referral,
  ReferralDetail,
} from "@/types/recova";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Label, Select, Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { AgentExecutionGraph } from "@/components/AgentExecutionGraph";
import { ClosedLoopReferralTracker } from "@/components/ClosedLoopReferralTracker";
import { DecideAiReviewWorkspace } from "@/components/DecideAiReviewWorkspace";
import { LongitudinalTrendChart } from "@/components/LongitudinalTrendChart";
import { RiskBadge } from "@/components/RiskBadge";
import { SubEngineSummaryBanner } from "@/components/SubEngineSummaryBanner";

const CORE_SYMPTOMS = [
  "craving_spike",
  "insomnia",
  "agitation",
  "sweating_tremors",
  "chest_pain",
  "severe_withdrawal",
];

interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  onresult: ((ev: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

export function CoreWorkspace() {
  const { hasPermission } = useAuth();
  const { pushToast } = useToast();

  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [baselines, setBaselines] = useState<PersonalBaseline[]>([]);
  const [latestRun, setLatestRun] = useState<PipelineRunDetail | null>(null);
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [selectedRefDetail, setSelectedRefDetail] = useState<ReferralDetail | null>(null);
  const [reviews, setReviews] = useState<ClinicalReview[]>([]);
  const [loading, setLoading] = useState(true);

  // Check-in form
  const [kind, setKind] = useState<"text" | "voice">("text");
  const [moodScore, setMoodScore] = useState(6);
  const [cravingScore, setCravingScore] = useState(3);
  const [stressScore, setStressScore] = useState(4);
  const [sleepHours, setSleepHours] = useState(6.8);
  const [textNote, setTextNote] = useState("");
  const [symptoms, setSymptoms] = useState<string[]>([]);
  const [selfCrisis, setSelfCrisis] = useState(false);
  const [dictating, setDictating] = useState(false);
  const [transcriptSource, setTranscriptSource] = useState<"typed" | "browser_speech">("typed");
  const [submitting, setSubmitting] = useState(false);

  // Quick wearable batch
  const [hrvInput, setHrvInput] = useState("44");
  const [rhrInput, setRhrInput] = useState("68");
  const [sleepWearable, setSleepWearable] = useState("7.0");
  const [stepsWearable, setStepsWearable] = useState("6200");

  useEffect(() => {
    patientsService
      .list({ track: "core", page_size: 100 })
      .then((res) => {
        setPatients(res.items);
        if (res.items.length > 0) {
          setSelectedId(res.items[0].id);
        }
      })
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, []);

  const loadPatientContext = useCallback(async (pid: string) => {
    if (!pid) return;
    try {
      const [pat, obsPage, baseList, runsPage, refsPage, revPage] = await Promise.all([
        patientsService.get(pid),
        signalsService.listObservations(pid, { track: "core", page_size: 100 }),
        engineService.listBaselines(pid),
        engineService.listRuns({ patient_id: pid, track: "core", page_size: 1 }),
        careService.listReferrals({ patient_id: pid, track: "core", page_size: 10 }),
        careService.listReviews({ patient_id: pid, page_size: 10 }),
      ]);
      setPatient(pat);
      setObservations(obsPage.items);
      setBaselines(baseList);
      setReferrals(refsPage.items);
      setReviews(revPage.items);
      if (runsPage.items.length > 0) {
        const detail = await engineService.getRun(runsPage.items[0].id);
        setLatestRun(detail);
      } else {
        setLatestRun(null);
      }
      if (refsPage.items.length > 0) {
        const rd = await careService.getReferral(refsPage.items[0].id);
        setSelectedRefDetail(rd);
      } else {
        setSelectedRefDetail(null);
      }
    } catch (err) {
      pushToast("Failed to load patient workspace", "error", err instanceof Error ? err.message : undefined);
    }
  }, [pushToast]);

  useEffect(() => {
    if (!selectedId) return;
    const timer = setTimeout(() => {
      void loadPatientContext(selectedId);
    }, 0);
    return () => clearTimeout(timer);
  }, [selectedId, loadPatientContext]);

  const startSpeechDictation = () => {
    const win = window as unknown as {
      SpeechRecognition?: new () => SpeechRecognitionLike;
      webkitSpeechRecognition?: new () => SpeechRecognitionLike;
    };
    const Ctor = win.SpeechRecognition || win.webkitSpeechRecognition;
    if (!Ctor) {
      pushToast("Speech recognition unavailable in this browser; please type check-in text.", "info");
      return;
    }
    const rec = new Ctor();
    rec.lang = patient?.preferred_language === "ar" ? "ar-AE" : "en-US";
    rec.interimResults = false;
    setKind("voice");
    setDictating(true);
    rec.onresult = (ev) => {
      const spoken = ev.results[0]?.[0]?.transcript || "";
      setTextNote((prev) => (prev ? `${prev} ${spoken}` : spoken));
      setTranscriptSource("browser_speech");
    };
    rec.onend = () => setDictating(false);
    rec.start();
  };

  const toggleSymptom = (sym: string) => {
    setSymptoms((prev) => (prev.includes(sym) ? prev.filter((s) => s !== sym) : [...prev, sym]));
  };

  const handleSubmitCheckIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedId) return;
    setSubmitting(true);
    try {
      const res = await signalsService.createCheckIn({
        patient_id: selectedId,
        track: "core",
        kind,
        mood_score: moodScore,
        craving_score: cravingScore,
        stress_score: stressScore,
        sleep_hours_reported: sleepHours,
        text: textNote.trim() || undefined,
        transcript_source: transcriptSource,
        symptoms,
        self_reported_crisis: selfCrisis,
        trigger_pipeline: true,
      });
      pushToast("Check-in saved & 6-agent pipeline executed", "success");
      setTextNote("");
      setSymptoms([]);
      setSelfCrisis(false);
      await loadPatientContext(selectedId);
      if (res.run_id) {
        const rd = await engineService.getRun(res.run_id);
        setLatestRun(rd);
      }
    } catch (err) {
      pushToast("Check-in submission failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setSubmitting(false);
    }
  };

  const handleIngestWearable = async () => {
    if (!selectedId) return;
    setSubmitting(true);
    try {
      const nowIso = new Date().toISOString();
      await signalsService.ingestWearables({
        patient_id: selectedId,
        track: "core",
        source_system: "sahatna",
        observations: [
          { metric_code: "hrv_rmssd", value_num: Number(hrvInput), unit: "ms", effective_at: nowIso },
          { metric_code: "resting_hr", value_num: Number(rhrInput), unit: "bpm", effective_at: nowIso },
          { metric_code: "sleep_duration_hours", value_num: Number(sleepWearable), unit: "h", effective_at: nowIso },
          { metric_code: "steps_daily", value_num: Number(stepsWearable), unit: "steps", effective_at: nowIso },
        ],
        trigger_pipeline: true,
      });
      pushToast("Wearable stream ingested & pipeline run", "success");
      await loadPatientContext(selectedId);
    } catch (err) {
      pushToast("Wearable ingest failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRunManualPipeline = async () => {
    if (!selectedId) return;
    setSubmitting(true);
    try {
      const run = await engineService.triggerRun({ patient_id: selectedId, track: "core", trigger: "manual" });
      setLatestRun(run);
      pushToast("Manual Core pipeline completed", "success", `Risk Tier: ${run.risk_tier || run.status}`);
      await loadPatientContext(selectedId);
    } catch (err) {
      pushToast("Pipeline execution failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setSubmitting(false);
    }
  };

  if (!loading && patients.length === 0) {
    return (
      <EmptyState
        icon={<HeartPulse className="h-5 w-5" />}
        title="No patients enrolled in Recova Core"
        description="Register a patient on the Participants page with the Core track selected to begin relapse-prevention monitoring."
      />
    );
  }

  return (
    <div className="space-y-6">
      <SubEngineSummaryBanner track="core" />
      {/* Patient Selector Bar */}
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-5">
          <div className="flex flex-wrap items-center gap-3">
            <Label className="text-xs uppercase tracking-wide text-slate-500">Active Core Patient</Label>
            <div className="w-72">
              <Select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.given_name} {p.family_name} ({p.mrn})
                  </option>
                ))}
              </Select>
            </div>
            {patient && (
              <RiskBadge
                tier={
                  patient.enrollments.find((e) => e.track === "core")?.latest_risk_tier || "INDETERMINATE"
                }
              />
            )}
          </div>
          {hasPermission("pipeline:run") && selectedId && (
            <Button onClick={() => void handleRunManualPipeline()} disabled={submitting}>
              <Play className="h-4 w-4" /> Re-Run 6-Agent Core Pipeline
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Signal Ingestion Row */}
      {hasPermission("observations:write") && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <Card className="lg:col-span-7">
            <CardHeader>
              <CardTitle>Daily Voice &amp; Text Check-In</CardTitle>
              <CardDescription>
                Supports Web Speech dictation or structured text intake; feeds Gate 2 red-flag safety and Agent 4 scoring.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmitCheckIn} className="space-y-4">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div className="space-y-1">
                    <Label>Mood (0-10)</Label>
                    <input
                      type="number"
                      min={0}
                      max={10}
                      value={moodScore}
                      onChange={(e) => setMoodScore(Number(e.target.value))}
                      className="h-9 w-full rounded-lg border border-slate-300 px-3 text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label>Craving (0-10)</Label>
                    <input
                      type="number"
                      min={0}
                      max={10}
                      value={cravingScore}
                      onChange={(e) => setCravingScore(Number(e.target.value))}
                      className="h-9 w-full rounded-lg border border-slate-300 px-3 text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label>Stress (0-10)</Label>
                    <input
                      type="number"
                      min={0}
                      max={10}
                      value={stressScore}
                      onChange={(e) => setStressScore(Number(e.target.value))}
                      className="h-9 w-full rounded-lg border border-slate-300 px-3 text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label>Sleep Hours</Label>
                    <input
                      type="number"
                      step="0.5"
                      min={0}
                      max={20}
                      value={sleepHours}
                      onChange={(e) => setSleepHours(Number(e.target.value))}
                      className="h-9 w-full rounded-lg border border-slate-300 px-3 text-sm"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Label>Check-In Journal / Voice Transcript</Label>
                    <Button
                      type="button"
                      size="sm"
                      variant={dictating ? "destructive" : "outline"}
                      onClick={startSpeechDictation}
                    >
                      {dictating ? <MicOff className="h-3.5 w-3.5" /> : <Mic className="h-3.5 w-3.5" />}
                      {dictating ? "Listening..." : "Voice Dictate"}
                    </Button>
                  </div>
                  <Textarea
                    value={textNote}
                    onChange={(e) => {
                      setTextNote(e.target.value);
                      setTranscriptSource("typed");
                    }}
                    placeholder="Record patient reflection, triggers, cravings, or recovery check-in..."
                  />
                </div>

                <div className="space-y-1.5">
                  <Label>Reported Symptoms</Label>
                  <div className="flex flex-wrap gap-2">
                    {CORE_SYMPTOMS.map((sym) => (
                      <button
                        key={sym}
                        type="button"
                        onClick={() => toggleSymptom(sym)}
                        className={`rounded-md border px-2.5 py-1 text-xs cursor-pointer ${
                          symptoms.includes(sym)
                            ? "border-red-400 bg-red-50 text-red-800 font-medium"
                            : "border-slate-200 bg-white text-slate-600"
                        }`}
                      >
                        {sym.replace(/_/g, " ")}
                      </button>
                    ))}
                  </div>
                </div>

                <label className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50/50 p-2.5 text-xs text-red-900 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selfCrisis}
                    onChange={(e) => setSelfCrisis(e.target.checked)}
                  />
                  Patient reports acute crisis / urgent distress (triggers immediate Gate 2 Emergency Bypass)
                </label>

                <Button type="submit" disabled={submitting}>
                  {submitting ? "Processing..." : "Submit Check-In & Run Pipeline"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card className="lg:col-span-5">
            <CardHeader>
              <CardTitle>Wearable Stream Sync (HRV / Sleep / RHR / Steps)</CardTitle>
              <CardDescription>
                Simulates structured wearable device telemetry ingestion from Sahatna / Garmin / Apple Health.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>HRV RMSSD (ms)</Label>
                  <input
                    type="number"
                    value={hrvInput}
                    onChange={(e) => setHrvInput(e.target.value)}
                    className="h-9 w-full rounded-lg border border-slate-300 px-3 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Resting HR (bpm)</Label>
                  <input
                    type="number"
                    value={rhrInput}
                    onChange={(e) => setRhrInput(e.target.value)}
                    className="h-9 w-full rounded-lg border border-slate-300 px-3 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Sleep Duration (hrs)</Label>
                  <input
                    type="number"
                    step="0.1"
                    value={sleepWearable}
                    onChange={(e) => setSleepWearable(e.target.value)}
                    className="h-9 w-full rounded-lg border border-slate-300 px-3 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Daily Steps</Label>
                  <input
                    type="number"
                    value={stepsWearable}
                    onChange={(e) => setStepsWearable(e.target.value)}
                    className="h-9 w-full rounded-lg border border-slate-300 px-3 text-sm"
                  />
                </div>
              </div>
              <Alert variant="info">
                Ensure at least 3 baseline wearable windows exist (initial stable days) to compute deterministic longitudinal Z-score drift.
              </Alert>
              <Button variant="outline" onClick={() => void handleIngestWearable()} disabled={submitting} className="w-full">
                <Upload className="h-4 w-4" /> Ingest Wearable Batch &amp; Score
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {/* 6-Agent Graph */}
      {latestRun && (
        <AgentExecutionGraph
          run={latestRun}
          canInspect={hasPermission("agents:inspect")}
        />
      )}

      {/* Trend Chart */}
      <LongitudinalTrendChart
        observations={observations}
        baselines={baselines}
        initialMetric="hrv_rmssd"
      />

      {/* DECIDE-AI Clinical Review */}
      {latestRun && (
        <DecideAiReviewWorkspace
          run={latestRun}
          referrals={referrals}
          existingReviews={reviews}
          canSign={hasPermission("reviews:sign")}
          onSigned={() => void loadPatientContext(selectedId)}
        />
      )}

      {/* Closed-Loop Referrals */}
      {referrals.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-slate-900">Closed-Loop Care Coordination</h3>
          {referrals.map((r) => (
            <ClosedLoopReferralTracker
              key={r.id}
              referral={r}
              detail={selectedRefDetail?.id === r.id ? selectedRefDetail : null}
              canWrite={hasPermission("referrals:write")}
              canVerifyOutcome={hasPermission("outcomes:verify")}
              onUpdated={() => void loadPatientContext(selectedId)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
