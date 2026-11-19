"use client";

import React, { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  Brain,
  Building2,
  CheckCircle2,
  Eye,
  EyeOff,
  HardHat,
  HeartPulse,
  Radio,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import type { BootstrapPayload } from "@/services/auth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const PROGRAMME_CARDS = [
  {
    id: "core",
    title: "Recovery (Recova Core)",
    subtitle: "Relapse prevention & rehabilitation monitoring",
    audience: "Rehabilitation centers, behavioral health clinics & outpatient recovery teams",
    inputs: "Daily reflections, craving/mood check-ins, wearable sleep/HRV/HR",
    tasks: "Early-warning review, Gate 2 crisis triage, rehab referral follow-up",
    outputs: "Personal baseline Z-scores, bilingual clinical synthesis & care plans",
    portalPreview: "Daily reflection, wearable CSV sync, approved care instructions & emergency support",
    icon: HeartPulse,
  },
  {
    id: "loop",
    title: "Recova Loop",
    subtitle: "Screening & closed-loop care navigation",
    audience: "Primary care clinics, IFHAS screening centers & care-navigation coordinators",
    inputs: "IFHAS labs (HbA1c, lipids), vitals (BP), PHQ-9 screening & activity",
    tasks: "Abnormal result triage, insurance/facility matching, SLA deadline tracking",
    outputs: "Closed-loop referral ownership, consultation booking & verified outcomes",
    portalPreview: "Dated screening results with units, assigned clinic, bookings & follow-up actions",
    icon: Workflow,
  },
  {
    id: "neuro",
    title: "Recova Neuro",
    subtitle: "Longitudinal cognitive health monitoring",
    audience: "Neurology clinics, geriatric memory centers & cognitive care teams",
    inputs: "Accessible cognitive sequences, reaction-time, rule-switch & recall + sleep",
    tasks: "Practice-adjusted baseline tracking, sensory/education confounder review",
    outputs: "Versioned cognitive drift alerts & specialist referral orchestration",
    portalPreview: "Accessible Brain Health cognitive activities, completion receipts & released results",
    icon: Brain,
  },
  {
    id: "worksafe",
    title: "Recova WorkSafe",
    subtitle: "Workforce readiness & occupational heat/fatigue safety",
    audience: "Industrial employers, construction sites & occupational health directors",
    inputs: "~10s pre-shift readiness checks, worksite ambient temp/humidity, thermal HRV",
    tasks: "k-anonymous (k >= 5) supervisor heatmaps, OH Director interventions, heatstroke bypass",
    outputs: "Shift clearance, hydration/stop-work alerts & occupational health follow-up",
    portalPreview: "10-second pre-shift readiness check & immediate safety/hydration instructions",
    icon: HardHat,
  },
] as const;

type ProgrammeId = (typeof PROGRAMME_CARDS)[number]["id"];
type OrgType = BootstrapPayload["org_type"];

const STEPS = [
  { id: 1, label: "Organisation" },
  { id: 2, label: "Programme" },
  { id: 3, label: "Service setup" },
  { id: 4, label: "Participation" },
  { id: 5, label: "Review & create" },
] as const;

function slugifyOrgName(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

export function OrganizationOnboardingCard({ mode }: { mode: "bootstrap" | "register" }) {
  const { bootstrap, registerOrganization } = useAuth();
  const router = useRouter();

  const [step, setStep] = useState(1);
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [orgType, setOrgType] = useState<OrgType>("hospital");
  const [emirate, setEmirate] = useState("Abu Dhabi");
  const [primaryProgramme, setPrimaryProgramme] = useState<ProgrammeId>("core");

  const [fullName, setFullName] = useState("");
  const [license, setLicense] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [serviceContact, setServiceContact] = useState("");
  const [participationAccepted, setParticipationAccepted] = useState(true);
  const [externalSynthesisOptIn, setExternalSynthesisOptIn] = useState(false);
  const idempotencyKeyRef = useRef<string | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isBootstrap = mode === "bootstrap";
  const selectedCard = PROGRAMME_CARDS.find((p) => p.id === primaryProgramme) || PROGRAMME_CARDS[0];

  const handleOrgNameChange = (value: string) => {
    setOrgName(value);
    if (!slugEdited) {
      setOrgSlug(slugifyOrgName(value));
    }
  };

  const handleSlugChange = (value: string) => {
    setSlugEdited(true);
    setOrgSlug(value.toLowerCase().replace(/[^a-z0-9-]/g, ""));
  };

  const validateStep = (currentStep: number): string | null => {
    if (currentStep === 1) {
      if (!orgName.trim() || orgName.trim().length < 2) return "Enter an organisation name (at least 2 characters).";
      if (!fullName.trim() || fullName.trim().length < 2) return "Enter the administrator full name.";
      if (!email.trim() || !email.includes("@")) return "Enter a valid administrator email.";
      if (password.length < 10) return "Administrator password must be at least 10 characters.";
    }
    if (currentStep === 4 && !participationAccepted) {
      return "Acknowledge the shared population-health coordination notice to continue.";
    }
    return null;
  };

  const goNext = () => {
    const err = validateStep(step);
    if (err) {
      setError(err);
      return;
    }
    setError(null);
    setStep((s) => Math.min(5, s + 1));
  };

  const goBack = () => {
    setError(null);
    setStep((s) => Math.max(1, s - 1));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setError(null);

    let cleanSlug = (orgSlug || slugifyOrgName(orgName)).trim().toLowerCase();
    if (!/^[a-z0-9-]{2,80}$/.test(cleanSlug)) {
      const sanitized = cleanSlug.replace(/[^a-z0-9-]/g, "");
      cleanSlug = sanitized.length >= 2 ? sanitized.slice(0, 80) : `org-${Date.now().toString(36)}`;
    }

    if (!idempotencyKeyRef.current) {
      idempotencyKeyRef.current =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `onb-${Date.now().toString(36)}`;
    }

    const payload: BootstrapPayload = {
      organization_name: orgName.trim(),
      organization_slug: cleanSlug,
      org_type: orgType,
      primary_programme: primaryProgramme,
      enabled_tracks: isBootstrap ? ["core", "loop", "neuro", "worksafe"] : [primaryProgramme],
      country: "UAE",
      emirate: emirate.trim() || "Abu Dhabi",
      idempotency_key: idempotencyKeyRef.current,
      service_setup: {
        primary_programme: primaryProgramme,
        facility_contact: serviceContact.trim() || undefined,
      },
      responsible_contact: serviceContact.trim()
        ? { email: serviceContact.trim(), name: fullName.trim() }
        : { email: email.trim().toLowerCase(), name: fullName.trim() },
      permitted_channels: ["in_app"],
      participation_consent: {
        policy_version: "v1.0",
        accepted_public_health_coordination: participationAccepted,
        external_synthesis_opt_in: externalSynthesisOptIn,
        external_channels: [],
      },
      admin_full_name: fullName.trim(),
      admin_license_number: license.trim() || undefined,
      admin_email: email.trim().toLowerCase(),
      admin_password: password,
    };

    setSubmitting(true);
    try {
      if (isBootstrap) {
        await bootstrap(payload);
      } else {
        await registerOrganization(payload);
      }
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Organisation setup failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f0f6f9] p-4 text-[#011621]">
      <Card className="recova-card w-full max-w-3xl border-[#e2edf2] bg-[#fafdff]">
        <CardHeader className="border-b border-[#e2edf2] pb-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-[#003e5e]">
              {isBootstrap ? <Activity className="h-5 w-5" /> : <Building2 className="h-5 w-5" />}
              <span className="text-xs font-bold uppercase tracking-wider">
                {isBootstrap ? "Initial Platform Setup" : "Health Center Onboarding"}
              </span>
            </div>
            <span className="rounded-full bg-[#d7e6ed] px-2.5 py-0.5 text-[11px] font-semibold text-[#004263]">
              Step {step} of 5
            </span>
          </div>
          <CardTitle className="text-xl text-[#011621]">
            {isBootstrap ? "Initialise Recova Engine & Primary Facility" : "Register a New Health Center"}
          </CardTitle>
          <CardDescription className="text-[#5a7d93]">
            Each health center selects one primary Recova sub-engine at signup. Additional programmes can be requested later from Settings.
          </CardDescription>

          {/* Stepper */}
          <nav aria-label="Onboarding steps" className="mt-4 grid grid-cols-5 gap-1.5">
            {STEPS.map((s) => {
              const active = step === s.id;
              const completed = step > s.id;
              return (
                <div
                  key={s.id}
                  className={cn(
                    "rounded-lg border px-2 py-1.5 text-center text-[11px] font-semibold transition-colors",
                    active && "border-[#003e5e] bg-[#003e5e] text-[#aeff9a]",
                    completed && "border-[#c6edbc] bg-[#e4f3dd] text-[#1a7a0a]",
                    !active && !completed && "border-[#e2edf2] bg-white text-[#5a7d93]"
                  )}
                >
                  {s.id}. {s.label}
                </div>
              );
            })}
          </nav>
        </CardHeader>

        <CardContent className="pt-5">
          {error && (
            <Alert variant="danger" className="mb-4">
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            {step === 1 && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="org_name">Organisation Name</Label>
                    <Input
                      id="org_name"
                      required
                      value={orgName}
                      onChange={(e) => handleOrgNameChange(e.target.value)}
                      placeholder="Al Noor Recovery Center"
                    />
                  </div>
                  <div>
                    <Label htmlFor="org_slug">Tenant Slug (URL-safe)</Label>
                    <Input
                      id="org_slug"
                      required
                      value={orgSlug}
                      onChange={(e) => handleSlugChange(e.target.value)}
                      placeholder="al-noor-recovery"
                    />
                  </div>
                  <div>
                    <Label htmlFor="org_type">Organisation Type</Label>
                    <Select
                      id="org_type"
                      value={orgType}
                      onChange={(e) => setOrgType(e.target.value as OrgType)}
                    >
                      <option value="hospital">Hospital / Health System</option>
                      <option value="rehab_center">Rehabilitation Center</option>
                      <option value="clinic">Outpatient Clinic</option>
                      <option value="employer">Employer / Industrial Worksite</option>
                      <option value="public_health">Public Health Authority</option>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="emirate">Emirate / Location</Label>
                    <Input
                      id="emirate"
                      value={emirate}
                      onChange={(e) => setEmirate(e.target.value)}
                      placeholder="Abu Dhabi"
                    />
                  </div>
                </div>

                <div className="border-t border-[#e2edf2] pt-4">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-[#5a7d93]">
                    Primary Facility Administrator
                  </p>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div>
                      <Label htmlFor="admin_name">Full Name</Label>
                      <Input
                        id="admin_name"
                        required
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="Dr. Amina Al-Mansoori"
                      />
                    </div>
                    <div>
                      <Label htmlFor="admin_license">DoH / MoHAP License (Optional)</Label>
                      <Input
                        id="admin_license"
                        value={license}
                        onChange={(e) => setLicense(e.target.value)}
                        placeholder="DOH-PHY-88210"
                      />
                    </div>
                    <div>
                      <Label htmlFor="admin_email">Admin Email</Label>
                      <Input
                        id="admin_email"
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="admin@healthcenter.ae"
                      />
                    </div>
                    <div>
                      <Label htmlFor="admin_password">Password (10+ chars)</Label>
                      <div className="relative">
                        <Input
                          id="admin_password"
                          type={showPassword ? "text" : "password"}
                          required
                          minLength={10}
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          placeholder="Strong passphrase"
                          className="pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword((prev) => !prev)}
                          aria-label={showPassword ? "Hide password" : "Show password"}
                          className="absolute inset-y-0 right-0 flex items-center px-3 text-[#5a7d93] hover:text-[#011621]"
                        >
                          {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-[#011621]">
                    Select One Primary Programme (Mutually Exclusive)
                  </p>
                  <span className="text-xs text-[#5a7d93]">
                    Determines staff dashboard &amp; patient portal experience
                  </span>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {PROGRAMME_CARDS.map((card) => {
                    const selected = primaryProgramme === card.id;
                    const Icon = card.icon;
                    return (
                      <button
                        key={card.id}
                        type="button"
                        onClick={() => setPrimaryProgramme(card.id)}
                        aria-pressed={selected}
                        className={cn(
                          "flex flex-col gap-2 rounded-2xl border p-4 text-left transition-all",
                          selected
                            ? "border-[#003e5e] bg-[#edf7ef] ring-2 ring-[#003e5e]/20"
                            : "border-[#e2edf2] bg-white hover:border-[#a8c4d4]"
                        )}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="flex items-center gap-2 font-semibold text-[#011621]">
                            <Icon className="h-4 w-4 text-[#003e5e]" />
                            {card.title}
                          </span>
                          {selected && <CheckCircle2 className="h-4 w-4 text-[#1a7a0a]" />}
                        </div>
                        <p className="text-xs font-medium text-[#2a4558]">{card.subtitle}</p>
                        <div className="space-y-1 text-[11px] text-[#5a7d93]">
                          <p><strong className="text-[#2a4558]">Audience:</strong> {card.audience}</p>
                          <p><strong className="text-[#2a4558]">Inputs:</strong> {card.inputs}</p>
                          <p><strong className="text-[#2a4558]">Daily Tasks:</strong> {card.tasks}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-4">
                <div className="rounded-2xl border border-[#e2edf2] bg-white p-4">
                  <p className="text-xs font-bold uppercase tracking-wider text-[#003e5e]">
                    Service Setup — {selectedCard.title}
                  </p>
                  <p className="mt-1 text-sm text-[#2a4558]">{selectedCard.outputs}</p>
                  <div className="mt-4">
                    <Label htmlFor="service_contact">Primary Care / Operations Contact (Optional)</Label>
                    <Input
                      id="service_contact"
                      value={serviceContact}
                      onChange={(e) => setServiceContact(e.target.value)}
                      placeholder="care-desk@healthcenter.ae"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-[#e2edf2] bg-[#f8fbfc] p-3.5">
                    <p className="text-xs font-semibold text-[#003e5e]">Staff Dashboard Preview</p>
                    <p className="mt-1 text-xs text-[#5a7d93]">{selectedCard.tasks}</p>
                  </div>
                  <div className="rounded-xl border border-[#c6edbc] bg-[#e4f3dd] p-3.5">
                    <p className="text-xs font-semibold text-[#214e40]">Participant Portal Preview (/portal)</p>
                    <p className="mt-1 text-xs text-[#214e40]/90">{selectedCard.portalPreview}</p>
                  </div>
                </div>
              </div>
            )}

            {step === 4 && (
              <div className="space-y-4">
                <div className="rounded-2xl border border-[#e2edf2] bg-white p-4">
                  <div className="flex items-center gap-2 text-[#003e5e]">
                    <Radio className="h-4 w-4" />
                    <p className="text-sm font-semibold text-[#011621]">
                      Shared Population-Health Coordination (All Programmes)
                    </p>
                  </div>
                  <ul className="mt-2 space-y-1.5 text-xs text-[#5a7d93]">
                    <li>• Every Recova organisation receives shared public-health notice delivery and emergency communication independently of Recova Loop.</li>
                    <li>• Authorised public-health authorities publish scoped notices by assigned facility and geography; recipients acknowledge in-app.</li>
                    <li>• Population summaries enforce aggregation and $k$-anonymity suppression thresholds.</li>
                    <li>• Separate consent records govern routine processing, wearable ingestion, and external LLM synthesis.</li>
                  </ul>
                  <label className="mt-4 flex cursor-pointer items-center gap-2 text-xs font-medium text-[#011621]">
                    <input
                      type="checkbox"
                      checked={participationAccepted}
                      onChange={(e) => setParticipationAccepted(e.target.checked)}
                      className="rounded border-[#c4d7e2] text-[#003e5e]"
                    />
                    I confirm the shared population-health notice &amp; consent policy (v1.0)
                  </label>
                  <label className="mt-2.5 flex cursor-pointer items-center gap-2 text-xs font-medium text-[#011621]">
                    <input
                      type="checkbox"
                      checked={externalSynthesisOptIn}
                      onChange={(e) => setExternalSynthesisOptIn(e.target.checked)}
                      className="rounded border-[#c4d7e2] text-[#003e5e]"
                    />
                    Enable de-identified external AI synthesis governance policy when configured (optional)
                  </label>
                </div>
              </div>
            )}

            {step === 5 && (
              <div className="space-y-3 rounded-2xl border border-[#e2edf2] bg-white p-4 text-xs">
                <p className="text-sm font-semibold text-[#011621]">Review &amp; Create Organisation</p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <p><span className="text-[#5a7d93]">Organisation:</span> <strong>{orgName}</strong> ({orgSlug || slugifyOrgName(orgName)})</p>
                  <p><span className="text-[#5a7d93]">Type &amp; Location:</span> <strong>{orgType}</strong> · {emirate}</p>
                  <p><span className="text-[#5a7d93]">Primary Programme:</span> <strong>{selectedCard.title}</strong></p>
                  <p><span className="text-[#5a7d93]">Administrator:</span> <strong>{fullName}</strong> ({email})</p>
                </div>
                <p className="rounded-lg bg-[#f8fbfc] p-2.5 text-[11px] text-[#5a7d93]">
                  Submitting creates your organisation, primary programme configuration, initial administrator membership, and shared public-health capability atomically.
                </p>
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[#e2edf2] pt-4">
              <div className="flex items-center gap-2">
                {step > 1 && (
                  <Button type="button" variant="outline" onClick={goBack}>
                    <ArrowLeft className="h-4 w-4" /> Back
                  </Button>
                )}
                {!isBootstrap && (
                  <Link href="/login">
                    <Button type="button" variant="ghost">Back to Sign In</Button>
                  </Link>
                )}
              </div>

              {step < 5 ? (
                <Button type="button" onClick={goNext} className="bg-[#003e5e] text-[#aeff9a] hover:bg-[#002e46]">
                  Continue <ArrowRight className="h-4 w-4" />
                </Button>
              ) : (
                <Button type="submit" disabled={submitting} className="bg-[#003e5e] text-[#aeff9a] hover:bg-[#002e46]">
                  <ShieldCheck className="h-4 w-4" />
                  {submitting
                    ? "Creating organisation..."
                    : isBootstrap
                    ? "Initialise Platform & Enter Dashboard"
                    : "Create Organisation & Sign In"}
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
