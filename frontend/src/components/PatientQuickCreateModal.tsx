"use client";

import React, { useState } from "react";
import { patientsService } from "@/services/patients";
import type { ConsentScope, Department, InsurancePlan, PatientDetail, Track } from "@/types/recova";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";

const ALL_TRACKS: Track[] = ["core", "loop", "neuro", "worksafe"];

export function PatientQuickCreateModal({
  open,
  onOpenChange,
  allowedTracks,
  insurancePlans = [],
  departments = [],
  defaultTrack,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  allowedTracks: string[];
  insurancePlans?: InsurancePlan[];
  departments?: Department[];
  defaultTrack?: Track;
  onCreated: (patient: PatientDetail) => void;
}) {
  const { pushToast } = useToast();
  const [busy, setBusy] = useState(false);

  const [participantType, setParticipantType] = useState<"patient" | "employee">(
    defaultTrack === "worksafe" ? "employee" : "patient"
  );
  const [mrn, setMrn] = useState("");
  const [givenName, setGivenName] = useState("");
  const [familyName, setFamilyName] = useState("");
  const [dob, setDob] = useState("");
  const [sex, setSex] = useState<"male" | "female" | "other" | "unknown">("unknown");
  const [language, setLanguage] = useState<"en" | "ar">("en");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [insurancePlanId, setInsurancePlanId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [jobRole, setJobRole] = useState("");
  const [educationLevel, setEducationLevel] = useState<
    "none" | "primary" | "secondary" | "tertiary" | "postgraduate"
  >("secondary");
  const [hearingStatus, setHearingStatus] = useState<
    "normal" | "mild_loss" | "moderate_loss" | "severe_loss" | "aided"
  >("normal");
  const [visionStatus, setVisionStatus] = useState<
    "normal" | "corrected" | "mild_impairment" | "severe_impairment"
  >("normal");
  const [tracks, setTracks] = useState<Track[]>(
    defaultTrack ? [defaultTrack] : (allowedTracks.filter((t): t is Track => ALL_TRACKS.includes(t as Track)).slice(0, 1))
  );
  const [grantDataConsent, setGrantDataConsent] = useState(true);
  const [grantLlmConsent, setGrantLlmConsent] = useState(true);
  const [grantHieConsent, setGrantHieConsent] = useState(false);

  const toggleTrack = (t: Track) => {
    setTracks((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (tracks.length === 0) {
      pushToast("Select at least one track", "error");
      return;
    }
    setBusy(true);
    try {
      const created = await patientsService.create({
        participant_type: participantType,
        mrn: mrn.trim(),
        given_name: givenName.trim(),
        family_name: familyName.trim(),
        date_of_birth: dob || null,
        sex,
        preferred_language: language,
        phone: phone.trim() || null,
        email: email.trim() || null,
        insurance_plan_id: insurancePlanId || null,
        department_id: departmentId || null,
        job_role: jobRole.trim() || null,
        education_level: educationLevel,
        hearing_status: hearingStatus,
        vision_status: visionStatus,
        tracks,
      });

      const scopesToGrant: ConsentScope[] = [];
      if (grantDataConsent) {
        scopesToGrant.push("data_processing", "wearable_ingestion");
      }
      if (grantLlmConsent) scopesToGrant.push("llm_synthesis");
      if (grantHieConsent) scopesToGrant.push("hie_sharing");

      await Promise.all(
        scopesToGrant.map((scope) =>
          patientsService.grantConsent({
            patient_id: created.id,
            scope,
            method: "electronic",
            granted_by_name: `${created.given_name} ${created.family_name}`,
          })
        )
      );

      pushToast("Participant registered", "success", `${created.given_name} ${created.family_name} (${created.mrn})`);
      onOpenChange(false);
      setMrn("");
      setGivenName("");
      setFamilyName("");
      onCreated(created);
    } catch (err) {
      pushToast("Failed to register participant", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Register Patient / Participant"
      description="Create an encrypted clinical or workforce participant record and configure governance consents."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="space-y-1">
            <Label>Participant Type</Label>
            <Select
              value={participantType}
              onChange={(e) => setParticipantType(e.target.value as "patient" | "employee")}
            >
              <option value="patient">Clinical Patient</option>
              <option value="employee">WorkSafe Employee</option>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>MRN / Worker ID *</Label>
            <Input required value={mrn} onChange={(e) => setMrn(e.target.value)} placeholder="MRN-10042" />
          </div>
          <div className="space-y-1">
            <Label>Preferred Language</Label>
            <Select value={language} onChange={(e) => setLanguage(e.target.value as "en" | "ar")}>
              <option value="en">English (en)</option>
              <option value="ar">Arabic (ar)</option>
            </Select>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label>Given Name *</Label>
            <Input required value={givenName} onChange={(e) => setGivenName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Family Name *</Label>
            <Input required value={familyName} onChange={(e) => setFamilyName(e.target.value)} />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="space-y-1">
            <Label>Date of Birth</Label>
            <Input type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Sex</Label>
            <Select value={sex} onChange={(e) => setSex(e.target.value as typeof sex)}>
              <option value="unknown">Unspecified</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Phone</Label>
            <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+97150..." />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label>Email</Label>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          {insurancePlans.length > 0 && (
            <div className="space-y-1">
              <Label>Insurance Plan (Loop Routing)</Label>
              <Select value={insurancePlanId} onChange={(e) => setInsurancePlanId(e.target.value)}>
                <option value="">Self-pay / None</option>
                {insurancePlans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.code})
                  </option>
                ))}
              </Select>
            </div>
          )}
        </div>

        {departments.length > 0 && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label>WorkSafe Department</Label>
              <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
                <option value="">None</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Job Role</Label>
              <Input value={jobRole} onChange={(e) => setJobRole(e.target.value)} placeholder="Site Technician" />
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="space-y-1">
            <Label>Education (Neuro Confounder)</Label>
            <Select value={educationLevel} onChange={(e) => setEducationLevel(e.target.value as typeof educationLevel)}>
              <option value="none">None</option>
              <option value="primary">Primary</option>
              <option value="secondary">Secondary</option>
              <option value="tertiary">Tertiary</option>
              <option value="postgraduate">Postgraduate</option>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Hearing Status</Label>
            <Select value={hearingStatus} onChange={(e) => setHearingStatus(e.target.value as typeof hearingStatus)}>
              <option value="normal">Normal</option>
              <option value="aided">Aided</option>
              <option value="mild_loss">Mild Loss</option>
              <option value="moderate_loss">Moderate Loss</option>
              <option value="severe_loss">Severe Loss</option>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Vision Status</Label>
            <Select value={visionStatus} onChange={(e) => setVisionStatus(e.target.value as typeof visionStatus)}>
              <option value="normal">Normal</option>
              <option value="corrected">Corrected</option>
              <option value="mild_impairment">Mild Impairment</option>
              <option value="severe_impairment">Severe Impairment</option>
            </Select>
          </div>
        </div>

        <div className="space-y-1.5">
          <Label>Track Enrollments *</Label>
          <div className="flex flex-wrap gap-2">
            {ALL_TRACKS.filter((t) => allowedTracks.includes(t)).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => toggleTrack(t)}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium uppercase cursor-pointer ${
                  tracks.includes(t)
                    ? "border-teal-600 bg-teal-50 text-teal-900"
                    : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                Recova {t}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2 rounded-lg border border-slate-200 p-3 text-xs">
          <div className="font-semibold text-slate-800">Initial Electronic Consent Governance</div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={grantDataConsent} onChange={(e) => setGrantDataConsent(e.target.checked)} />
            Grant mandatory <code>data_processing</code> &amp; <code>wearable_ingestion</code> consent
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={grantLlmConsent} onChange={(e) => setGrantLlmConsent(e.target.checked)} />
            Grant de-identified <code>llm_synthesis</code> consent
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={grantHieConsent} onChange={(e) => setGrantHieConsent(e.target.checked)} />
            Grant UAE HIE FHIR sharing (<code>hie_sharing</code>)
          </label>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button type="submit" disabled={busy}>{busy ? "Saving..." : "Create Participant"}</Button>
        </div>
      </form>
    </Dialog>
  );
}
