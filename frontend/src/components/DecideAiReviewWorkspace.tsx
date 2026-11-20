"use client";

import React, { useState } from "react";
import { CheckCircle2, FileText, Globe, ShieldCheck } from "lucide-react";
import type {
  ClinicalReview,
  NotificationChannel,
  PipelineRunDetail,
  Referral,
  ReviewDecision,
} from "@/types/recova";
import { careService } from "@/services/care";
import { formatDateTime, formatLabel } from "@/lib/utils";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label, Select, Textarea } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { RiskBadge } from "@/components/RiskBadge";

export function DecideAiReviewWorkspace({
  run,
  referrals = [],
  existingReviews = [],
  canSign = false,
  onSigned,
}: {
  run: PipelineRunDetail;
  referrals?: Referral[];
  existingReviews?: ClinicalReview[];
  canSign?: boolean;
  onSigned?: (review: ClinicalReview) => void;
}) {
  const { pushToast } = useToast();
  const [langTab, setLangTab] = useState("en");
  const [decision, setDecision] = useState<ReviewDecision>("approve_referral");
  const [agreesWithTier, setAgreesWithTier] = useState(true);
  const [notes, setNotes] = useState("");
  const [selectedReferralId, setSelectedReferralId] = useState(
    referrals.find((r) => r.run_id === run.id || r.status === "proposed")?.id || ""
  );
  const [notifyChannel, setNotifyChannel] = useState<NotificationChannel | "">("in_app");
  const [labTestName, setLabTestName] = useState("Urine Toxicology & Comprehensive Panel");
  const [submitting, setSubmitting] = useState(false);

  const scoring = run.scoring;
  const synthesis = run.synthesis;
  const runReviews = existingReviews.filter((r) => r.run_id === run.id);

  const handleSign = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const review = await careService.createReview({
        run_id: run.id,
        decision,
        agrees_with_tier: agreesWithTier,
        clinician_notes: notes.trim() || undefined,
        lab_request:
          decision === "request_lab"
            ? { test: labTestName, requested_at: new Date().toISOString() }
            : undefined,
        modified_plan:
          decision === "modify_plan" ? { custom_instructions: notes.trim() } : undefined,
        referral_id: selectedReferralId || undefined,
        notify_patient_channel: notifyChannel ? (notifyChannel as NotificationChannel) : undefined,
      });
      pushToast("Clinical review signed", "success", `Signature hash ${review.signature_hash.slice(0, 12)}...`);
      setNotes("");
      onSigned?.(review);
    } catch (err) {
      pushToast("Failed to submit clinical review", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      <div className="space-y-4 lg:col-span-7">
        {/* Agent 4 Deterministic Math Table */}
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle>Agent 4 — Deterministic Mathematical Drift Matrix</CardTitle>
                <CardDescription>
                  Computed strictly in Python (v{scoring?.algorithm_version || run.algorithm_version}). The LLM never computes risk tiers.
                </CardDescription>
              </div>
              {scoring && <RiskBadge tier={scoring.risk_tier} />}
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {scoring ? (
              <>
                <div className="flex flex-wrap gap-2 text-xs">
                  <Badge variant="outline">
                    Composite |Z|: {scoring.composite_index !== null && scoring.composite_index !== undefined ? scoring.composite_index.toFixed(2) : "—"}
                  </Badge>
                  <Badge variant="outline">
                    Confidence: {Math.round(scoring.confidence_index * 100)}%
                  </Badge>
                  {scoring.primary_metric_code && (
                    <Badge variant="info">
                      Primary Driver: {formatLabel(scoring.primary_metric_code)} (Z={scoring.primary_z?.toFixed(2) ?? "—"})
                    </Badge>
                  )}
                </div>

                {scoring.confounders_applied.length > 0 && (
                  <Alert variant="info" title="Confounders Applied (SE Expansion / Practice Effect)">
                    {scoring.confounders_applied
                      .map((c) => String(c.description || c.factor || JSON.stringify(c)))
                      .join(" · ")}
                  </Alert>
                )}

                {scoring.missing_streams.length > 0 && (
                  <Alert variant="warning" title="Missing Data Streams">
                    Unavailable inputs degraded confidence without halting pipeline:{" "}
                    {scoring.missing_streams.join(", ")}
                  </Alert>
                )}

                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Metric</TableHead>
                      <TableHead>Current</TableHead>
                      <TableHead>Baseline Mean (SD)</TableHead>
                      <TableHead>Adj. SE</TableHead>
                      <TableHead>Z-Score</TableHead>
                      <TableHead>Tier</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {scoring.metric_results.map((m) => (
                      <TableRow key={m.metric_code}>
                        <TableCell className="text-xs font-medium">
                          {m.label || formatLabel(m.metric_code)}
                          {m.unit && <span className="ml-1 text-slate-400">({m.unit})</span>}
                        </TableCell>
                        <TableCell className="text-xs tabular-nums">
                          {m.current_value !== null && m.current_value !== undefined
                            ? m.current_value.toFixed(2)
                            : "—"}
                        </TableCell>
                        <TableCell className="text-xs tabular-nums">
                          {m.baseline_mean !== null && m.baseline_mean !== undefined
                            ? `${m.baseline_mean.toFixed(2)} (${m.baseline_sd?.toFixed(2) ?? "—"})`
                            : "Insufficient baseline"}
                        </TableCell>
                        <TableCell className="text-xs tabular-nums">
                          {m.adjusted_se !== null && m.adjusted_se !== undefined
                            ? m.adjusted_se.toFixed(2)
                            : "—"}
                        </TableCell>
                        <TableCell className="text-xs font-mono tabular-nums">
                          {m.signed_z !== null && m.signed_z !== undefined
                            ? `${m.signed_z >= 0 ? "+" : ""}${m.signed_z.toFixed(2)}`
                            : "—"}
                        </TableCell>
                        <TableCell>
                          <RiskBadge tier={m.risk_tier} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </>
            ) : (
              <p className="text-xs text-slate-500">
                No deterministic scoring output recorded (run was blocked at Gate 1 or bypassed at Gate 2).
              </p>
            )}
          </CardContent>
        </Card>

        {/* Agent 5 Bilingual Synthesis */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-4 w-4 text-teal-700" />
              Agent 5 — Clinical Synthesis Draft (Non-Autonomous)
            </CardTitle>
            <CardDescription>
              {synthesis
                ? `Status: ${formatLabel(synthesis.status)}${synthesis.provider ? ` · Provider: ${synthesis.provider} (${synthesis.model || "default"})` : ""}`
                : "No synthesis executed for this pipeline run."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!synthesis ? (
              <p className="text-xs text-slate-500">Synthesis step skipped for this run.</p>
            ) : synthesis.status === "completed" ? (
              <Tabs value={langTab} onValueChange={setLangTab}>
                <TabsList>
                  <TabsTrigger value="en">English Draft</TabsTrigger>
                  <TabsTrigger value="ar">الملخص العربي (Arabic)</TabsTrigger>
                  <TabsTrigger value="structured">Structured Recommendations</TabsTrigger>
                </TabsList>
                <TabsContent value="en" className="rounded-lg border border-slate-200 bg-slate-50 p-3.5 text-sm leading-relaxed text-slate-800">
                  {synthesis.summary_en || "No English text returned."}
                </TabsContent>
                <TabsContent
                  value="ar"
                  className="rounded-lg border border-slate-200 bg-slate-50 p-3.5 text-sm leading-relaxed text-slate-800"
                >
                  <div dir="rtl" lang="ar" className="space-y-2.5 text-right font-sans">
                    <p>{synthesis.summary_ar || "لم يتم إرجاع ملخص عربي."}</p>
                    <p className="border-t border-slate-200 pt-2 text-xs text-slate-500">
                      مسودة مساعدة للقرار السريري — القرار النهائي بيد الطبيب المختص.
                    </p>
                  </div>
                </TabsContent>
                <TabsContent value="structured">
                  <pre className="max-h-64 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                    {JSON.stringify(synthesis.structured || {}, null, 2)}
                  </pre>
                </TabsContent>
              </Tabs>
            ) : (
              <Alert
                variant="warning"
                title={`AI Synthesis Not Executed: ${formatLabel(synthesis.status)}`}
              >
                {synthesis.status === "provider_not_configured" &&
                  "Configure OpenAI, Azure OpenAI, Anthropic, or Gemini in Organisation Settings → Integrations to generate bilingual clinical drafts. Recova never fabricates AI output."}
                {synthesis.status === "consent_not_granted" &&
                  "Patient has not granted llm_synthesis consent. Deterministic Agent 4 scores remain valid."}
                {(synthesis.status === "provider_error" || synthesis.status === "validation_failed") &&
                  (synthesis.error || "Configured LLM provider returned an error or invalid schema.")}
              </Alert>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Clinician DECIDE-AI Sign-Off Panel */}
      <div className="space-y-4 lg:col-span-5">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-teal-700" />
              DECIDE-AI Clinician Governance Sign-Off
            </CardTitle>
            <CardDescription>
              Human-in-the-loop accountability required before non-emergency referral execution.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {runReviews.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Signed Audit Decisions ({runReviews.length})
                </div>
                {runReviews.map((rv) => (
                  <div key={rv.id} className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-3 text-xs">
                    <div className="flex items-center justify-between font-semibold text-emerald-950">
                      <span className="flex items-center gap-1.5">
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                        {formatLabel(rv.decision)}
                      </span>
                      <span className="text-[11px] font-normal text-slate-600">
                        {formatDateTime(rv.signed_at)}
                      </span>
                    </div>
                    <div className="mt-1 text-slate-700">
                      Role: {formatLabel(rv.reviewer_role)}
                      {rv.reviewer_license ? ` (${rv.reviewer_license})` : ""} · Tier Agreement:{" "}
                      {rv.agrees_with_tier ? "Confirmed" : "Overridden"}
                    </div>
                    {rv.clinician_notes && (
                      <p className="mt-1.5 rounded bg-white p-2 text-slate-700 border border-emerald-100">
                        {rv.clinician_notes}
                      </p>
                    )}
                    <div className="mt-1 font-mono text-[10px] text-slate-500">
                      SHA256: {rv.signature_hash}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {canSign ? (
              <form onSubmit={handleSign} className="space-y-3 border-t border-slate-100 pt-3">
                <div className="space-y-1">
                  <Label htmlFor="review-decision">Clinical Decision</Label>
                  <Select
                    id="review-decision"
                    value={decision}
                    onChange={(e) => setDecision(e.target.value as ReviewDecision)}
                  >
                    <option value="approve_referral">Approve Recommended Referral</option>
                    <option value="modify_plan">Modify Care Plan</option>
                    <option value="request_lab">Request Lab / Toxicology Screen</option>
                    <option value="no_action">No Action Required (Continue Monitoring)</option>
                    <option value="reject">Reject Agent Recommendation</option>
                  </Select>
                </div>

                {referrals.length > 0 && (
                  <div className="space-y-1">
                    <Label htmlFor="review-referral">Target Proposed Referral</Label>
                    <Select
                      id="review-referral"
                      value={selectedReferralId}
                      onChange={(e) => setSelectedReferralId(e.target.value)}
                    >
                      <option value="">Auto-select open referral from run</option>
                      {referrals.map((r) => (
                        <option key={r.id} value={r.id}>
                          {formatLabel(r.pathway)} ({formatLabel(r.priority)}) — {formatLabel(r.status)}
                        </option>
                      ))}
                    </Select>
                  </div>
                )}

                {decision === "request_lab" && (
                  <div className="space-y-1">
                    <Label htmlFor="lab-order">Diagnostic / Lab Request Details</Label>
                    <Select
                      id="lab-order"
                      value={labTestName}
                      onChange={(e) => setLabTestName(e.target.value)}
                    >
                      <option value="Urine Toxicology & Comprehensive Panel">Urine Toxicology & Comprehensive Panel</option>
                      <option value="HbA1c + Fasting Lipid Profile">HbA1c + Fasting Lipid Profile</option>
                      <option value="12-Lead ECG + Cardiac Enzymes">12-Lead ECG + Cardiac Enzymes</option>
                      <option value="Neurology MRI / MoCA Referral">Neurology MRI / MoCA Referral</option>
                    </Select>
                  </div>
                )}

                <div className="flex items-center gap-2 pt-1">
                  <input
                    id="agrees-tier"
                    type="checkbox"
                    checked={agreesWithTier}
                    onChange={(e) => setAgreesWithTier(e.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-teal-700"
                  />
                  <Label htmlFor="agrees-tier" className="cursor-pointer">
                    I confirm the deterministic risk tier ({scoring?.risk_tier || run.risk_tier || "N/A"})
                  </Label>
                </div>

                <div className="space-y-1">
                  <Label htmlFor="notify-channel">Patient Notification Channel Upon Approval</Label>
                  <Select
                    id="notify-channel"
                    value={notifyChannel}
                    onChange={(e) => setNotifyChannel(e.target.value as NotificationChannel | "")}
                  >
                    <option value="">Do not send notification now</option>
                    <option value="in_app">In-App Inbox (Immediate)</option>
                    <option value="email">Email (Configured SMTP)</option>
                    <option value="sms">SMS (Configured Twilio)</option>
                    <option value="whatsapp">WhatsApp (Configured Twilio)</option>
                    <option value="sahatna">Sahatna App Notification</option>
                  </Select>
                </div>

                <div className="space-y-1">
                  <Label htmlFor="clinician-notes">Clinician Review Rationale & Care Instructions</Label>
                  <Textarea
                    id="clinician-notes"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Document clinical judgement, confounders considered, and patient communication plan..."
                  />
                </div>

                <Button type="submit" disabled={submitting} className="w-full">
                  <FileText className="h-4 w-4" />
                  {submitting ? "Signing Cryptographically..." : "Sign DECIDE-AI Clinical Review"}
                </Button>
              </form>
            ) : (
              <Alert variant="info" title="Sign-off Requires Clinician Role">
                Your active role does not hold <code>reviews:sign</code> permission. Deterministic results and audit trails remain visible for care coordination.
              </Alert>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
