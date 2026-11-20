"use client";

import React, { useState } from "react";
import { AlertTriangle, Bell, CalendarCheck, CheckCircle2, Clock, ShieldCheck } from "lucide-react";
import type { NotificationChannel, Referral, ReferralDetail } from "@/types/recova";
import { careService } from "@/services/care";
import { cn, formatDateTime, formatLabel, formatRelativeCountdown } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { StatusBadge } from "@/components/RiskBadge";

const STAGES = [
  { key: "proposed", label: "Proposed" },
  { key: "approved", label: "Approved" },
  { key: "patient_notified", label: "Notified" },
  { key: "booked", label: "Booked" },
  { key: "consultation_completed", label: "Consulted" },
  { key: "outcome_verified", label: "Verified" },
];

export function ClosedLoopReferralTracker({
  referral,
  detail,
  canWrite = false,
  canVerifyOutcome = false,
  onUpdated,
}: {
  referral: Referral;
  detail?: ReferralDetail | null;
  canWrite?: boolean;
  canVerifyOutcome?: boolean;
  onUpdated?: () => void;
}) {
  const { pushToast } = useToast();
  const [modal, setModal] = useState<"notify" | "book" | "complete" | "missed" | "verify" | "cancel" | null>(null);
  const [busy, setBusy] = useState(false);

  const [channel, setChannel] = useState<NotificationChannel>("in_app");
  const [message, setMessage] = useState("");
  const [apptAt, setApptAt] = useState(() =>
    new Date(Date.now() + 86400000).toISOString().slice(0, 16)
  );
  const [apptRef, setApptRef] = useState("");
  const [notes, setNotes] = useState("");
  const [outcome, setOutcome] = useState<
    "improved" | "stable" | "deteriorated" | "relapsed" | "lost_to_follow_up" | "referred_onward"
  >("improved");
  const [verificationMethod, setVerificationMethod] = useState<
    "clinic_visit" | "teleconsult" | "phone" | "record_review" | "lab_result"
  >("clinic_visit");

  const activeStageIndex = STAGES.findIndex((s) => s.key === referral.status);
  const isClosed = ["outcome_verified", "cancelled", "rejected"].includes(referral.status);

  const runAction = async (fn: () => Promise<unknown>, successTitle: string) => {
    setBusy(true);
    try {
      await fn();
      pushToast(successTitle, "success");
      setModal(null);
      setNotes("");
      setMessage("");
      onUpdated?.();
    } catch (err) {
      pushToast("Referral action failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle className="flex items-center gap-2">
            {formatLabel(referral.pathway)}
            {referral.is_emergency && <Badge variant="danger">STAT EMERGENCY</Badge>}
          </CardTitle>
          <CardDescription>
            {referral.reason} · Facility: {referral.owner_facility_label || "Unassigned"} · Insurance:{" "}
            {formatLabel(referral.coverage_status)}
          </CardDescription>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={referral.status} />
          <Badge variant={referral.sla_status === "breached" ? "danger" : referral.sla_status === "at_risk" ? "warning" : "outline"}>
            <Clock className="h-3 w-3" />
            {formatRelativeCountdown(referral.sla_due_at)}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Horizontal Stepper */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-6">
          {STAGES.map((st, idx) => {
            const done = activeStageIndex >= idx || referral.status === "outcome_verified";
            const current = referral.status === st.key;
            return (
              <div
                key={st.key}
                className={cn(
                  "rounded-lg border px-2.5 py-2 text-center text-xs transition-colors",
                  current
                    ? "border-teal-600 bg-teal-50 font-semibold text-teal-900"
                    : done
                    ? "border-emerald-200 bg-emerald-50/70 text-emerald-800"
                    : "border-slate-200 bg-slate-50 text-slate-400"
                )}
              >
                <div className="text-[10px] uppercase tracking-wider">Stage {idx + 1}</div>
                <div>{st.label}</div>
              </div>
            );
          })}
        </div>

        {(referral.status === "missed" || referral.status === "escalated") && (
          <div className="flex items-center gap-2 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-900">
            <AlertTriangle className="h-4 w-4 text-red-600" />
            <span>
              Escalation Level {referral.escalation_level} ({formatLabel(referral.status)}) — immediate navigator re-engagement required.
            </span>
          </div>
        )}

        {/* Action Buttons */}
        {!isClosed && (
          <div className="flex flex-wrap gap-2">
            {canWrite && referral.status !== "proposed" && (
              <Button variant="outline" size="sm" onClick={() => setModal("notify")}>
                <Bell className="h-3.5 w-3.5" /> Notify Patient
              </Button>
            )}
            {canWrite && ["approved","patient_notified","booked","missed","escalated"].includes(referral.status) && (
              <Button variant="outline" size="sm" onClick={() => setModal("book")}>
                <CalendarCheck className="h-3.5 w-3.5" /> Book Appointment
              </Button>
            )}
            {canWrite && referral.status === "booked" && (
              <Button variant="outline" size="sm" onClick={() => setModal("complete")}>
                <CheckCircle2 className="h-3.5 w-3.5" /> Complete Consultation
              </Button>
            )}
            {canWrite && referral.status === "booked" && (
              <Button variant="destructive" size="sm" onClick={() => setModal("missed")}>
                <AlertTriangle className="h-3.5 w-3.5" /> Mark Missed / Escalate
              </Button>
            )}
            {canWrite && referral.status !== "consultation_completed" && (
              <Button variant="outline" size="sm" onClick={() => setModal("cancel")}>Cancel referral</Button>
            )}
            {canVerifyOutcome && referral.status === "consultation_completed" && (
              <Button size="sm" onClick={() => setModal("verify")}>
                <ShieldCheck className="h-3.5 w-3.5" /> Verify Outcome
              </Button>
            )}
          </div>
        )}

        {detail?.outcome_verification && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-950">
            <div className="font-semibold">
              Verified Outcome: {formatLabel(detail.outcome_verification.outcome)} (via{" "}
              {formatLabel(detail.outcome_verification.verification_method)})
            </div>
            {detail.outcome_verification.notes && (
              <p className="mt-1">{detail.outcome_verification.notes}</p>
            )}
          </div>
        )}

        {detail?.events && detail.events.length > 0 && (
          <div className="border-t border-slate-100 pt-3">
            <div className="mb-2 text-xs font-semibold text-slate-600">
              Closed-Loop Audit Timeline ({detail.events.length})
            </div>
            <div className="space-y-1.5 max-h-44 overflow-y-auto">
              {detail.events.map((ev) => (
                <div
                  key={ev.id}
                  className="flex items-center justify-between gap-2 rounded border border-slate-100 bg-slate-50 px-2.5 py-1.5 text-[11px]"
                >
                  <div>
                    <span className="font-semibold text-slate-800">{formatLabel(ev.event_type)}</span>
                    {ev.to_status && (
                      <span className="text-slate-500">
                        {" "}
                        → {formatLabel(ev.to_status)}
                      </span>
                    )}
                    <span className="ml-2 text-slate-500">by {ev.actor_label}</span>
                  </div>
                  <span className="text-slate-400 tabular-nums">{formatDateTime(ev.created_at)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>

      {/* Modals */}
      <Dialog open={modal === "cancel"} onOpenChange={(o) => !o && setModal(null)} title="Cancel referral">
        <div className="space-y-3">
          <Label htmlFor="cancel-reason">Reason for cancellation</Label>
          <Textarea id="cancel-reason" value={notes} onChange={(e) => setNotes(e.target.value)} />
          <p className="text-sm text-slate-600">The patient will see this change in My care. The audit history is retained.</p>
          <Button variant="destructive" disabled={busy || notes.trim().length < 3} onClick={() => runAction(() => careService.cancelReferral(referral.id, notes.trim()), "Referral cancelled")}>Confirm cancellation</Button>
        </div>
      </Dialog>
      <Dialog open={modal === "notify"} onOpenChange={(o) => !o && setModal(null)} title="Notify Patient">
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Notification Channel</Label>
            <Select value={channel} onChange={(e) => setChannel(e.target.value as NotificationChannel)}>
              <option value="in_app">In-App Notification</option>
              <option value="email">Email (SMTP)</option>
              <option value="sms">SMS (Twilio)</option>
              <option value="whatsapp">WhatsApp (Twilio)</option>
              <option value="sahatna">Sahatna App</option>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Message to Patient</Label>
            <Textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Optional tailored guidance..." />
          </div>
          <Button
            disabled={busy}
            onClick={() => runAction(() => careService.notifyReferral(referral.id, channel, message || undefined), "Notification processed")}
          >
            {busy ? "Sending..." : "Send Notification"}
          </Button>
        </div>
      </Dialog>

      <Dialog open={modal === "book"} onOpenChange={(o) => !o && setModal(null)} title="Book Care Appointment">
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Appointment Date & Time</Label>
            <Input type="datetime-local" value={apptAt} onChange={(e) => setApptAt(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Booking Reference / Ticket</Label>
            <Input value={apptRef} onChange={(e) => setApptRef(e.target.value)} placeholder="e.g. APT-2026-0412" />
          </div>
          <div className="space-y-1">
            <Label>Booking Notes</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <Button
            disabled={busy}
            onClick={() =>
              runAction(
                () =>
                  careService.bookReferral(referral.id, {
                    appointment_at: new Date(apptAt).toISOString(),
                    appointment_reference: apptRef || undefined,
                    notes: notes || undefined,
                  }),
                "Appointment booked"
              )
            }
          >
            {busy ? "Saving..." : "Confirm Booking"}
          </Button>
        </div>
      </Dialog>

      <Dialog open={modal === "complete"} onOpenChange={(o) => !o && setModal(null)} title="Complete Consultation">
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Consultation Clinical Notes</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Summary of clinician encounter..." />
          </div>
          <Button
            disabled={busy}
            onClick={() => runAction(() => careService.completeConsultation(referral.id, notes || undefined), "Consultation marked completed")}
          >
            {busy ? "Saving..." : "Mark Consultation Completed"}
          </Button>
        </div>
      </Dialog>

      <Dialog open={modal === "missed"} onOpenChange={(o) => !o && setModal(null)} title="Mark Missed & Escalate">
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Escalation & Follow-Up Reason</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Patient missed scheduled appointment; triggering navigator outreach..." />
          </div>
          <Button
            variant="destructive"
            disabled={busy}
            onClick={() => runAction(() => careService.markMissed(referral.id, notes || undefined), "Referral marked missed & escalated")}
          >
            {busy ? "Escalating..." : "Escalate Missed Referral"}
          </Button>
        </div>
      </Dialog>

      <Dialog open={modal === "verify"} onOpenChange={(o) => !o && setModal(null)} title="Verify Closed-Loop Clinical Outcome">
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Observed Clinical Outcome</Label>
            <Select value={outcome} onChange={(e) => setOutcome(e.target.value as typeof outcome)}>
              <option value="improved">Improved</option>
              <option value="stable">Stable</option>
              <option value="deteriorated">Deteriorated</option>
              <option value="relapsed">Relapsed</option>
              <option value="lost_to_follow_up">Lost to Follow-Up</option>
              <option value="referred_onward">Referred Onward</option>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Verification Method</Label>
            <Select value={verificationMethod} onChange={(e) => setVerificationMethod(e.target.value as typeof verificationMethod)}>
              <option value="clinic_visit">Clinic Visit</option>
              <option value="teleconsult">Teleconsult</option>
              <option value="phone">Phone Check</option>
              <option value="record_review">Medical Record Review</option>
              <option value="lab_result">Laboratory Result</option>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Verification Notes</Label>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <Button
            disabled={busy}
            onClick={() =>
              runAction(
                () => careService.verifyOutcome(referral.id, { outcome, verification_method: verificationMethod, notes: notes || undefined }),
                "Outcome verified and care loop closed"
              )
            }
          >
            {busy ? "Verifying..." : "Verify & Close Loop"}
          </Button>
        </div>
      </Dialog>
    </Card>
  );
}
