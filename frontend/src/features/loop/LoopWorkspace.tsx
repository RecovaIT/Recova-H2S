"use client";

import React, { useCallback, useEffect, useState } from "react";
import { FileCheck2, Shield, Workflow } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { careService } from "@/services/care";
import { engineService } from "@/services/engine";
import { opsService } from "@/services/ops";
import { patientsService } from "@/services/patients";
import { signalsService } from "@/services/signals";
import type {
  CareFacility,
  FamilyHealthPassport,
  InsurancePlan,
  PatientSummary,
  PipelineRunDetail,
  Referral,
  ReferralDetail,
} from "@/types/recova";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { AgentExecutionGraph } from "@/components/AgentExecutionGraph";
import { ClosedLoopReferralTracker } from "@/components/ClosedLoopReferralTracker";
import { DecideAiReviewWorkspace } from "@/components/DecideAiReviewWorkspace";
import { RiskBadge, StatusBadge } from "@/components/RiskBadge";
import { formatDateTime, formatLabel, formatRelativeCountdown } from "@/lib/utils";

const PHQ9_QUESTIONS = [
  "Little interest or pleasure in doing things",
  "Feeling down, depressed, or hopeless",
  "Trouble falling or staying asleep, or sleeping too much",
  "Feeling tired or having little energy",
  "Poor appetite or overeating",
  "Feeling bad about yourself — or that you are a failure",
  "Trouble concentrating on things",
  "Moving or speaking slowly, or being fidgety/restless",
  "Thoughts that you would be better off dead or hurting yourself",
];

export function LoopWorkspace() {
  const { hasPermission } = useAuth();
  const { pushToast } = useToast();

  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [passport, setPassport] = useState<FamilyHealthPassport | null>(null);
  const [facilities, setFacilities] = useState<CareFacility[]>([]);
  const [plans, setPlans] = useState<InsurancePlan[]>([]);
  const [latestRun, setLatestRun] = useState<PipelineRunDetail | null>(null);
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [refDetail, setRefDetail] = useState<ReferralDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // IFHAS intake form
  const [site, setSite] = useState("Abu Dhabi IFHAS Community Center");
  const [hba1c, setHba1c] = useState("6.1");
  const [bpSys, setBpSys] = useState("128");
  const [bpDia, setBpDia] = useState("82");
  const [totalChol, setTotalChol] = useState("195");
  const [ldl, setLdl] = useState("118");
  const [hdl, setHdl] = useState("52");
  const [steps, setSteps] = useState("5400");
  const [phqItems, setPhqItems] = useState<number[]>(Array(9).fill(0));
  const [notes, setNotes] = useState("");

  useEffect(() => {
    Promise.all([
      patientsService.list({ track: "loop", page_size: 100 }),
      opsService.listCareFacilities().catch(() => [] as CareFacility[]),
      opsService.listInsurancePlans().catch(() => [] as InsurancePlan[]),
    ])
      .then(([pRes, fRes, planRes]) => {
        setPatients(pRes.items);
        setFacilities(fRes);
        setPlans(planRes);
        if (pRes.items.length > 0) setSelectedId(pRes.items[0].id);
      })
      .finally(() => setLoading(false));
  }, []);

  const loadContext = useCallback(async (pid: string) => {
    if (!pid) return;
    try {
      const [pp, runsPage, refsPage] = await Promise.all([
        patientsService.getPassport(pid),
        engineService.listRuns({ patient_id: pid, track: "loop", page_size: 1 }),
        careService.listReferrals({ patient_id: pid, track: "loop", page_size: 10 }),
      ]);
      setPassport(pp);
      setReferrals(refsPage.items);
      if (runsPage.items.length > 0) {
        const rd = await engineService.getRun(runsPage.items[0].id);
        setLatestRun(rd);
      } else {
        setLatestRun(null);
      }
      if (refsPage.items.length > 0) {
        const d = await careService.getReferral(refsPage.items[0].id);
        setRefDetail(d);
      } else {
        setRefDetail(null);
      }
    } catch (err) {
      pushToast("Could not load Loop patient context", "error", err instanceof Error ? err.message : undefined);
    }
  }, [pushToast]);

  useEffect(() => {
    if (!selectedId) return;
    const timer = setTimeout(() => {
      void loadContext(selectedId);
    }, 0);
    return () => clearTimeout(timer);
  }, [selectedId, loadContext]);

  const phq9Total = phqItems.reduce((a, b) => a + b, 0);

  const handleScreeningSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedId) return;
    setSubmitting(true);
    try {
      const res = await signalsService.createScreening({
        patient_id: selectedId,
        programme: "IFHAS",
        screening_site: site.trim() || undefined,
        hba1c: hba1c ? Number(hba1c) : undefined,
        bp_systolic: bpSys ? Number(bpSys) : undefined,
        bp_diastolic: bpDia ? Number(bpDia) : undefined,
        total_cholesterol: totalChol ? Number(totalChol) : undefined,
        ldl_cholesterol: ldl ? Number(ldl) : undefined,
        hdl_cholesterol: hdl ? Number(hdl) : undefined,
        steps: steps ? Number(steps) : undefined,
        phq9_item_responses: phqItems,
        phq9_score: phq9Total,
        notes: notes.trim() || undefined,
        trigger_pipeline: true,
      });
      pushToast("IFHAS screening saved & evaluated", "success", `PHQ-9 Total: ${phq9Total}`);
      if (res.run_id) {
        const rd = await engineService.getRun(res.run_id);
        setLatestRun(rd);
      }
      await loadContext(selectedId);
    } catch (err) {
      pushToast("Screening intake failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setSubmitting(false);
    }
  };

  const handleEvaluateSlas = async () => {
    try {
      const res = await careService.evaluateSlas();
      pushToast("SLA check completed", "info", JSON.stringify(res));
      await loadContext(selectedId);
    } catch (err) {
      pushToast("SLA evaluation failed", "error", err instanceof Error ? err.message : undefined);
    }
  };

  if (!loading && patients.length === 0) {
    return (
      <EmptyState
        icon={<Workflow className="h-5 w-5" />}
        title="No patients enrolled in Recova Loop"
        description="Register an IFHAS participant on the Participants page enrolled in Recova Loop to begin screening-to-care navigation."
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-5">
          <div className="flex flex-wrap items-center gap-3">
            <Label className="text-xs uppercase tracking-wide text-slate-500">Loop Participant</Label>
            <div className="w-72">
              <Select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
                {patients.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.given_name} {p.family_name} ({p.mrn})
                  </option>
                ))}
              </Select>
            </div>
            {passport?.latest_risk_tier && <RiskBadge tier={passport.latest_risk_tier} />}
            {passport?.insurance_plan && (
              <Badge variant="info">
                <Shield className="h-3 w-3" /> {passport.insurance_plan.name} ({passport.insurance_plan.code})
              </Badge>
            )}
          </div>
          {hasPermission("referrals:write") && (
            <Button variant="outline" size="sm" onClick={() => void handleEvaluateSlas()}>
              Evaluate Referral SLAs Now
            </Button>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Screening Form */}
        {hasPermission("observations:write") && (
          <Card className="lg:col-span-7">
            <CardHeader>
              <CardTitle>IFHAS Screening-to-Care Intake</CardTitle>
              <CardDescription>
                Captures HbA1c, blood pressure, lipids, physical activity, and full 9-item PHQ-9 (item 9 screens self-harm safety).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleScreeningSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div className="space-y-1 sm:col-span-2">
                    <Label>Screening Site</Label>
                    <Input value={site} onChange={(e) => setSite(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>HbA1c (%)</Label>
                    <Input type="number" step="0.1" value={hba1c} onChange={(e) => setHba1c(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>Daily Steps</Label>
                    <Input type="number" value={steps} onChange={(e) => setSteps(e.target.value)} />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                  <div className="space-y-1">
                    <Label>Systolic BP</Label>
                    <Input type="number" value={bpSys} onChange={(e) => setBpSys(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>Diastolic BP</Label>
                    <Input type="number" value={bpDia} onChange={(e) => setBpDia(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>Total Chol</Label>
                    <Input type="number" value={totalChol} onChange={(e) => setTotalChol(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>LDL</Label>
                    <Input type="number" value={ldl} onChange={(e) => setLdl(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>HDL</Label>
                    <Input type="number" value={hdl} onChange={(e) => setHdl(e.target.value)} />
                  </div>
                </div>

                <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center justify-between">
                    <Label>PHQ-9 Depression Screen (0=Not at all, 3=Nearly every day)</Label>
                    <Badge variant={phq9Total >= 15 ? "danger" : phq9Total >= 10 ? "warning" : "secondary"}>
                      PHQ-9 Score: {phq9Total} / 27
                    </Badge>
                  </div>
                  <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                    {PHQ9_QUESTIONS.map((q, idx) => (
                      <div key={q} className="flex items-center justify-between gap-2 rounded bg-white px-2.5 py-1.5 text-xs border border-slate-100">
                        <span className="truncate" title={q}>
                          {idx + 1}. {q}
                        </span>
                        <select
                          aria-label={`PHQ-9 item ${idx + 1}`}
                          value={phqItems[idx]}
                          onChange={(e) => {
                            const next = [...phqItems];
                            next[idx] = Number(e.target.value);
                            setPhqItems(next);
                          }}
                          className="rounded border border-slate-300 px-1.5 py-0.5 text-xs"
                        >
                          <option value={0}>0</option>
                          <option value={1}>1</option>
                          <option value={2}>2</option>
                          <option value={3}>3</option>
                        </select>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-1">
                  <Label>Navigator / Clinician Notes</Label>
                  <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
                </div>

                <Button type="submit" disabled={submitting}>
                  {submitting ? "Running Navigation..." : "Submit IFHAS Screening & Navigate Care"}
                </Button>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Family Health Passport & Network Coverage */}
        <Card className="lg:col-span-5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileCheck2 className="h-4 w-4 text-indigo-700" />
              Family Health Passport
            </CardTitle>
            <CardDescription>
              Unified longitudinal screening biomarkers, Thiqa/Daman coverage &amp; active SLA countdowns.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {passport ? (
              <>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs space-y-1">
                  <div className="font-semibold text-slate-900">
                    {passport.patient.given_name} {passport.patient.family_name} · {passport.patient.mrn}
                  </div>
                  <div className="text-slate-600">
                    Coverage:{" "}
                    {passport.insurance_plan
                      ? `${passport.insurance_plan.name} (${passport.insurance_plan.network_tier || "Standard"})`
                      : "Self-pay / Plan not linked"}
                  </div>
                  <div className="text-slate-600">
                    Active Consents:{" "}
                    {passport.consents.filter((c) => c.status === "granted").map((c) => c.scope).join(", ") || "None"}
                  </div>
                </div>

                <div>
                  <div className="mb-1.5 text-xs font-semibold text-slate-700">
                    Configured Network Facilities ({facilities.length}) &amp; Plans ({plans.length})
                  </div>
                  {facilities.length === 0 ? (
                    <Alert variant="warning">
                      No Care Facilities configured yet in Organisation Settings. Agent 6 routes using default coverage fallback until facilities are registered.
                    </Alert>
                  ) : (
                    <div className="space-y-1.5 max-h-40 overflow-y-auto">
                      {facilities.map((f) => {
                        const acceptsPatientPlan =
                          passport.insurance_plan && f.accepted_plan_ids.includes(passport.insurance_plan.id);
                        return (
                          <div
                            key={f.id}
                            className="flex items-center justify-between rounded border border-slate-100 bg-white px-2.5 py-1.5 text-xs"
                          >
                            <div>
                              <span className="font-medium text-slate-800">{f.name}</span>
                              <span className="ml-2 text-slate-400">({formatLabel(f.facility_type)})</span>
                            </div>
                            <Badge variant={acceptsPatientPlan ? "success" : "secondary"}>
                              {acceptsPatientPlan ? "In-Network" : `${f.typical_wait_days ?? "—"}d wait`}
                            </Badge>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div>
                  <div className="mb-1.5 text-xs font-semibold text-slate-700">
                    Passport Referral SLAs ({passport.referrals.length})
                  </div>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {passport.referrals.length === 0 ? (
                      <p className="text-xs text-slate-500">No Loop referrals triggered yet.</p>
                    ) : (
                      passport.referrals.map((r) => (
                        <div key={r.id} className="rounded border border-slate-200 p-2 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold">{formatLabel(r.pathway)}</span>
                            <StatusBadge status={r.status} />
                          </div>
                          <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500">
                            <span>{r.facility_name || "Pending assignment"}</span>
                            <span>{formatRelativeCountdown(r.sla_due_at)}</span>
                          </div>
                          <div className="mt-0.5 text-[10px] text-slate-400">
                            Booked: {formatDateTime(r.appointment_at)}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </>
            ) : (
              <p className="text-xs text-slate-500">Select a patient to view Family Health Passport.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {latestRun && (
        <AgentExecutionGraph run={latestRun} canInspect={hasPermission("agents:inspect")} />
      )}

      {latestRun && (
        <DecideAiReviewWorkspace
          run={latestRun}
          referrals={referrals}
          canSign={hasPermission("reviews:sign")}
          onSigned={() => void loadContext(selectedId)}
        />
      )}

      {referrals.map((r) => (
        <ClosedLoopReferralTracker
          key={r.id}
          referral={r}
          detail={refDetail?.id === r.id ? refDetail : null}
          canWrite={hasPermission("referrals:write")}
          canVerifyOutcome={hasPermission("outcomes:verify")}
          onUpdated={() => void loadContext(selectedId)}
        />
      ))}
    </div>
  );
}
