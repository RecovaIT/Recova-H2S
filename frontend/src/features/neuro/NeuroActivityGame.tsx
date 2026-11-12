"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Brain, CheckCircle2, Play, RotateCcw, Volume2 } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { engineService } from "@/services/engine";
import { patientsService } from "@/services/patients";
import { signalsService } from "@/services/signals";
import { nowTimestampMs } from "@/lib/utils";
import type {
  CognitiveAssessment,
  CognitiveTrialInput,
  Observation,
  PatientDetail,
  PatientSummary,
  PersonalBaseline,
  PipelineRunDetail,
} from "@/types/recova";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Label, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { AgentExecutionGraph } from "@/components/AgentExecutionGraph";
import { DecideAiReviewWorkspace } from "@/components/DecideAiReviewWorkspace";
import { LongitudinalTrendChart } from "@/components/LongitudinalTrendChart";
import { RiskBadge } from "@/components/RiskBadge";

interface KeyPadSpec {
  id: number;
  label: string;
  freq: number;
  bgClass: string;
  activeClass: string;
}

const KEY_SPECS: KeyPadSpec[] = [
  { id: 1, label: "1 · Teal", freq: 261.63, bgClass: "bg-teal-100 text-teal-900 border-teal-300", activeClass: "bg-teal-600 text-white scale-105 ring-4 ring-teal-300" },
  { id: 2, label: "2 · Indigo", freq: 329.63, bgClass: "bg-indigo-100 text-indigo-900 border-indigo-300", activeClass: "bg-indigo-600 text-white scale-105 ring-4 ring-indigo-300" },
  { id: 3, label: "3 · Amber", freq: 392.0, bgClass: "bg-amber-100 text-amber-900 border-amber-300", activeClass: "bg-amber-500 text-white scale-105 ring-4 ring-amber-300" },
  { id: 4, label: "4 · Rose", freq: 523.25, bgClass: "bg-rose-100 text-rose-900 border-rose-300", activeClass: "bg-rose-600 text-white scale-105 ring-4 ring-rose-300" },
  { id: 5, label: "5 · Sky", freq: 659.25, bgClass: "bg-sky-100 text-sky-900 border-sky-300", activeClass: "bg-sky-600 text-white scale-105 ring-4 ring-sky-300" },
  { id: 6, label: "6 · Violet", freq: 783.99, bgClass: "bg-violet-100 text-violet-900 border-violet-300", activeClass: "bg-violet-600 text-white scale-105 ring-4 ring-violet-300" },
];

type Phase = "idle" | "seq4_show" | "seq4_input" | "seq6_show" | "seq6_input" | "rule_switch" | "delayed_recall" | "complete";

const RULE_PROMPTS = [
  { cue: "Tap EVEN number (2 or 4)", rule: "even", valid: [2, 4] },
  { cue: "Tap ODD number (1 or 3)", rule: "odd", valid: [1, 3] },
];

function playFrequency(freq: number, ms = 280): void {
  if (typeof window === "undefined") return;
  const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioCtx) return;
  try {
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + ms / 1000);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + ms / 1000);
    setTimeout(() => void ctx.close().catch(() => undefined), ms + 120);
  } catch {
    // Audio playback blocked or unavailable in headless tests
  }
}

function randomSequence(maxKey: number, len: number): number[] {
  const arr: number[] = [];
  for (let i = 0; i < len; i += 1) {
    arr.push(Math.floor(Math.random() * maxKey) + 1);
  }
  return arr;
}

export function NeuroActivityGame() {
  const { hasPermission } = useAuth();
  const { pushToast } = useToast();

  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [assessments, setAssessments] = useState<CognitiveAssessment[]>([]);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [baselines, setBaselines] = useState<PersonalBaseline[]>([]);
  const [latestRun, setLatestRun] = useState<PipelineRunDetail | null>(null);
  const [loading, setLoading] = useState(true);

  // Interactive Game State
  const [phase, setPhase] = useState<Phase>("idle");
  const [lang, setLang] = useState<"en" | "ar">("en");
  const [activeKey, setActiveKey] = useState<number | null>(null);
  const [targetSeq, setTargetSeq] = useState<number[]>([]);
  const [recallAnchorSeq, setRecallAnchorSeq] = useState<number[]>([]);
  const [userSeq, setUserSeq] = useState<number[]>([]);
  const [ruleRound, setRuleRound] = useState(0);
  const [ruleTargets] = useState(() => [RULE_PROMPTS[0], RULE_PROMPTS[1], RULE_PROMPTS[0], RULE_PROMPTS[1]]);
  const [trials, setTrials] = useState<CognitiveTrialInput[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const phaseStartRef = useRef<number>(0);
  const sessionStartRef = useRef<string>("");

  useEffect(() => {
    patientsService
      .list({ track: "neuro", page_size: 100 })
      .then((res) => {
        setPatients(res.items);
        if (res.items.length > 0) setSelectedId(res.items[0].id);
      })
      .finally(() => setLoading(false));
  }, []);

  const loadContext = useCallback(async (pid: string) => {
    if (!pid) return;
    try {
      const [pat, cogList, obsPage, baseList, runsPage] = await Promise.all([
        patientsService.get(pid),
        signalsService.listCognitiveAssessments(pid),
        signalsService.listObservations(pid, { page_size: 100 }),
        engineService.listBaselines(pid),
        engineService.listRuns({ patient_id: pid, track: "neuro", page_size: 1 }),
      ]);
      setPatient(pat);
      setAssessments(cogList);
      setObservations(obsPage.items);
      setBaselines(baseList);
      if (runsPage.items.length > 0) {
        setLatestRun(await engineService.getRun(runsPage.items[0].id));
      } else {
        setLatestRun(null);
      }
    } catch (err) {
      pushToast("Failed to load Neuro patient data", "error", err instanceof Error ? err.message : undefined);
    }
  }, [pushToast]);

  useEffect(() => {
    if (!selectedId) return;
    const timer = setTimeout(() => {
      void loadContext(selectedId);
    }, 0);
    return () => clearTimeout(timer);
  }, [selectedId, loadContext]);

  const playSequence = async (seq: number[], nextPhase: Phase) => {
    setUserSeq([]);
    for (const keyId of seq) {
      const spec = KEY_SPECS.find((k) => k.id === keyId);
      setActiveKey(keyId);
      if (spec) playFrequency(spec.freq);
      await new Promise((r) => setTimeout(r, 420));
      setActiveKey(null);
      await new Promise((r) => setTimeout(r, 180));
    }
    phaseStartRef.current = nowTimestampMs();
    setPhase(nextPhase);
  };

  const startSession = () => {
    const seq4 = randomSequence(4, 3);
    setTrials([]);
    setTargetSeq(seq4);
    setRecallAnchorSeq(seq4);
    setRuleRound(0);
    sessionStartRef.current = new Date().toISOString();
    setPhase("seq4_show");
    void playSequence(seq4, "seq4_input");
  };

  const handleKeyTap = (keyId: number) => {
    const spec = KEY_SPECS.find((k) => k.id === keyId);
    if (spec) playFrequency(spec.freq, 180);
    setActiveKey(keyId);
    setTimeout(() => setActiveKey(null), 160);

    if (phase === "seq4_input" || phase === "seq6_input") {
      const next = [...userSeq, keyId];
      setUserSeq(next);
      if (next.length >= targetSeq.length) {
        const rt = Math.max(50, nowTimestampMs() - phaseStartRef.current);
        const correct = next.every((val, i) => val === targetSeq[i]);
        const recorded: CognitiveTrialInput = {
          task_type: phase === "seq4_input" ? "sequence_4key" : "sequence_6key",
          modality: "audiovisual",
          expected: targetSeq,
          response: next,
          reaction_time_ms: Number(rt.toFixed(1)),
          correct,
        };
        const updatedTrials = [...trials, recorded];
        setTrials(updatedTrials);

        if (phase === "seq4_input") {
          const seq6 = randomSequence(6, 4);
          setTargetSeq(seq6);
          setPhase("seq6_show");
          void playSequence(seq6, "seq6_input");
        } else {
          phaseStartRef.current = nowTimestampMs();
          setUserSeq([]);
          setPhase("rule_switch");
        }
      }
      return;
    }

    if (phase === "rule_switch") {
      const prompt = ruleTargets[ruleRound];
      const rt = Math.max(50, nowTimestampMs() - phaseStartRef.current);
      const correct = prompt.valid.includes(keyId);
      const recorded: CognitiveTrialInput = {
        task_type: "rule_switch",
        modality: "executive",
        expected: prompt.valid,
        response: [keyId],
        reaction_time_ms: Number(rt.toFixed(1)),
        correct,
      };
      setTrials((prev) => [...prev, recorded]);
      if (ruleRound + 1 < ruleTargets.length) {
        setRuleRound((r) => r + 1);
        phaseStartRef.current = nowTimestampMs();
      } else {
        setUserSeq([]);
        phaseStartRef.current = nowTimestampMs();
        setPhase("delayed_recall");
      }
      return;
    }

    if (phase === "delayed_recall") {
      const next = [...userSeq, keyId];
      setUserSeq(next);
      if (next.length >= recallAnchorSeq.length) {
        const rt = Math.max(50, nowTimestampMs() - phaseStartRef.current);
        const correct = next.every((val, i) => val === recallAnchorSeq[i]);
        const recorded: CognitiveTrialInput = {
          task_type: "delayed_recall",
          modality: "recall",
          expected: recallAnchorSeq,
          response: next,
          reaction_time_ms: Number(rt.toFixed(1)),
          correct,
        };
        setTrials((prev) => [...prev, recorded]);
        setPhase("complete");
      }
    }
  };

  const submitAssessment = async () => {
    if (!selectedId || trials.length === 0) return;
    setSubmitting(true);
    try {
      const res = await signalsService.createCognitiveAssessment({
        patient_id: selectedId,
        started_at: sessionStartRef.current || new Date().toISOString(),
        completed_at: new Date().toISOString(),
        assessment_language: lang,
        environment: {
          audio_enabled: true,
          device: "web_browser",
        },
        raw_trials: trials,
        trigger_pipeline: true,
      });
      pushToast("Cognitive session scored by 6-agent engine", "success");
      setPhase("idle");
      setTrials([]);
      if (res.run_id) {
        setLatestRun(await engineService.getRun(res.run_id));
      }
      await loadContext(selectedId);
    } catch (err) {
      pushToast("Failed to save cognitive assessment", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setSubmitting(false);
    }
  };

  if (!loading && patients.length === 0) {
    return (
      <EmptyState
        icon={<Brain className="h-5 w-5" />}
        title="No participants enrolled in Recova Neuro"
        description="Register a participant (ages 50–75) enrolled in the Neuro track to launch longitudinal cognitive monitoring."
      />
    );
  }

  const visibleKeys = phase === "seq6_show" || phase === "seq6_input" ? KEY_SPECS : KEY_SPECS.slice(0, 4);

  return (
    <div className="space-y-6">
      <Alert variant="warning" title="Non-Diagnostic Early Brain Health & Cognitive Wellness Screening">
        Recova Neuro monitors within-person longitudinal cognitive reaction-time &amp; accuracy shifts adjusted for education, language match, hearing/vision, and session practice effects. It is not a standalone diagnostic tool for dementia.
      </Alert>

      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-5">
          <div className="flex flex-wrap items-center gap-3">
            <Label className="text-xs uppercase tracking-wide text-slate-500">Neuro Participant</Label>
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
              <div className="flex flex-wrap gap-1.5 text-xs">
                <RiskBadge
                  tier={patient.enrollments.find((e) => e.track === "neuro")?.latest_risk_tier || "INDETERMINATE"}
                />
                {patient.education_level && (
                  <Badge variant="outline">Edu: {patient.education_level}</Badge>
                )}
                {patient.hearing_status && (
                  <Badge variant="outline">Hearing: {patient.hearing_status}</Badge>
                )}
                {patient.vision_status && (
                  <Badge variant="outline">Vision: {patient.vision_status}</Badge>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Label>Activity Language</Label>
            <Select value={lang} onChange={(e) => setLang(e.target.value as "en" | "ar")} className="w-28">
              <option value="en">English</option>
              <option value="ar">Arabic</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Interactive Cognitive Battery */}
      {hasPermission("cognitive:administer") && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Volume2 className="h-4 w-4 text-violet-700" />
                Interactive Audio-Visual Cognitive Session (Sessions Completed: {assessments.length})
              </span>
              {phase !== "idle" && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setPhase("idle");
                    setTrials([]);
                  }}
                >
                  <RotateCcw className="h-3.5 w-3.5" /> Reset
                </Button>
              )}
            </CardTitle>
            <CardDescription>
              Stages: (1) 4-Key Sequence → (2) 6-Key Sequence → (3) Executive Rule Switching → (4) Delayed Recall of First Sequence.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-5">
            {phase === "idle" && (
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-violet-200 bg-violet-50/40 p-8 text-center">
                <p className="max-w-lg text-sm text-slate-700">
                  Ensure sound is enabled (visual indicators also illuminate if muted). Each trial captures exact millisecond latency and sequence accuracy.
                </p>
                <Button size="lg" className="mt-4 bg-violet-700 hover:bg-violet-800" onClick={startSession}>
                  <Play className="h-4 w-4" /> Start Cognitive Assessment Session
                </Button>
              </div>
            )}

            {phase !== "idle" && phase !== "complete" && (
              <div className="space-y-4">
                <div className="rounded-lg border border-violet-200 bg-violet-50 p-3 text-center text-sm font-semibold text-violet-950">
                  {phase === "seq4_show" && "Watch and listen closely to the 4-key sequence..."}
                  {phase === "seq4_input" && `Tap the ${targetSeq.length} highlighted keys in order (${userSeq.length}/${targetSeq.length})`}
                  {phase === "seq6_show" && "Watch and listen closely to the 6-key sequence..."}
                  {phase === "seq6_input" && `Tap the ${targetSeq.length} keys in order (${userSeq.length}/${targetSeq.length})`}
                  {phase === "rule_switch" && `Rule Switch (${ruleRound + 1}/${ruleTargets.length}): ${ruleTargets[ruleRound].cue}`}
                  {phase === "delayed_recall" && `Delayed Recall: Repeat the VERY FIRST ${recallAnchorSeq.length}-key sequence from Stage 1 (${userSeq.length}/${recallAnchorSeq.length})`}
                </div>

                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {visibleKeys.map((k) => (
                    <button
                      key={k.id}
                      type="button"
                      disabled={phase === "seq4_show" || phase === "seq6_show"}
                      onClick={() => handleKeyTap(k.id)}
                      className={`h-24 rounded-xl border-2 text-lg font-bold transition-all cursor-pointer disabled:cursor-default ${
                        activeKey === k.id ? k.activeClass : k.bgClass
                      }`}
                    >
                      {k.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {phase === "complete" && (
              <div className="space-y-4 rounded-xl border border-emerald-200 bg-emerald-50/60 p-5">
                <div className="flex items-center gap-2 text-sm font-semibold text-emerald-900">
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                  All {trials.length} Cognitive Trials Captured — Ready for Backend Scoring
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 text-xs">
                  <div className="rounded bg-white p-2.5 border border-emerald-100">
                    Accuracy:{" "}
                    <strong>
                      {Math.round((trials.filter((t) => t.correct).length / trials.length) * 100)}%
                    </strong>
                  </div>
                  <div className="rounded bg-white p-2.5 border border-emerald-100">
                    Mean Latency:{" "}
                    <strong>
                      {Math.round(trials.reduce((a, b) => a + b.reaction_time_ms, 0) / trials.length)} ms
                    </strong>
                  </div>
                  <div className="rounded bg-white p-2.5 border border-emerald-100">
                    Confounder Session Index: <strong>#{assessments.length + 1}</strong>
                  </div>
                </div>
                <Button onClick={() => void submitAssessment()} disabled={submitting}>
                  {submitting ? "Submitting to Agent 4..." : "Save Session & Execute Six-Agent Pipeline"}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {latestRun && (
        <AgentExecutionGraph run={latestRun} canInspect={hasPermission("agents:inspect")} />
      )}

      <LongitudinalTrendChart
        observations={observations}
        baselines={baselines}
        initialMetric="cog_auditory_accuracy"
      />

      {latestRun && (
        <DecideAiReviewWorkspace
          run={latestRun}
          canSign={hasPermission("reviews:sign")}
          onSigned={() => void loadContext(selectedId)}
        />
      )}
    </div>
  );
}
