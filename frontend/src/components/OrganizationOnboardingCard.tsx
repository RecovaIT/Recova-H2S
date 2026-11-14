"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Activity, Building2, CheckSquare, ShieldCheck } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import type { BootstrapPayload } from "@/services/auth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";

const TRACK_OPTIONS = [
  { id: "core", label: "Recova Core — Relapse Prevention & Rehabilitation" },
  { id: "loop", label: "Recova Loop — IFHAS Screening-to-Care" },
  { id: "neuro", label: "Recova Neuro — Cognitive & Brain Health" },
  { id: "worksafe", label: "Recova WorkSafe — Workforce & Heat-Stress" },
];

type OrgType = BootstrapPayload["org_type"];

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

  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [orgType, setOrgType] = useState<OrgType>("hospital");
  const [tracks, setTracks] = useState<string[]>(["core", "loop", "neuro", "worksafe"]);

  const [fullName, setFullName] = useState("");
  const [license, setLicense] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isBootstrap = mode === "bootstrap";

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

  const toggleTrack = (trackId: string) => {
    setTracks((prev) =>
      prev.includes(trackId) ? prev.filter((t) => t !== trackId) : [...prev, trackId]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (tracks.length === 0) {
      setError("Select at least one enabled application track.");
      return;
    }
    const cleanSlug = orgSlug.trim().toLowerCase();
    if (!/^[a-z0-9-]{2,80}$/.test(cleanSlug)) {
      setError("Organisation slug must be 2–80 lowercase letters, numbers, or hyphens.");
      return;
    }

    const payload: BootstrapPayload = {
      organization_name: orgName.trim(),
      organization_slug: cleanSlug,
      org_type: orgType,
      enabled_tracks: tracks,
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
    <div className="flex min-h-screen items-center justify-center bg-slate-900 p-4">
      <Card className="w-full max-w-2xl shadow-xl border-slate-200">
        <CardHeader className="border-b border-slate-100 pb-4">
          <div className="mb-2 flex items-center gap-2 text-teal-700">
            {isBootstrap ? <Activity className="h-5 w-5" /> : <Building2 className="h-5 w-5" />}
            <span className="text-xs font-bold uppercase tracking-wider">
              {isBootstrap ? "Initial Platform Setup" : "Tenant Onboarding"}
            </span>
          </div>
          <CardTitle className="text-xl text-slate-900">
            {isBootstrap ? "Initialise Recova Platform" : "Add New Organisation"}
          </CardTitle>
          <CardDescription>
            {isBootstrap
              ? "Configure the first healthcare organisation and platform administrator account. This setup locks permanently once completed."
              : "Provision an isolated tenant healthcare organisation, choose active clinical tracks, and create its initial Organisation Admin."}
          </CardDescription>
        </CardHeader>

        <CardContent className="pt-5">
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && <Alert variant="danger">{error}</Alert>}

            <div className="space-y-3">
              <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-600">
                <Building2 className="h-3.5 w-3.5 text-teal-700" />
                Organisation Profile
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="org-name">Organisation Name</Label>
                  <Input
                    id="org-name"
                    required
                    minLength={2}
                    maxLength={200}
                    placeholder="Abu Dhabi Wellness Center"
                    value={orgName}
                    onChange={(e) => handleOrgNameChange(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="org-slug">Tenant Slug</Label>
                  <Input
                    id="org-slug"
                    required
                    minLength={2}
                    maxLength={80}
                    pattern="[a-z0-9-]+"
                    placeholder="abu-dhabi-wellness"
                    className="font-mono text-xs"
                    value={orgSlug}
                    onChange={(e) => handleSlugChange(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-1">
                <Label htmlFor="org-type">Organisation Type</Label>
                <Select
                  id="org-type"
                  value={orgType}
                  onChange={(e) => setOrgType(e.target.value as OrgType)}
                >
                  <option value="hospital">Hospital / Integrated Care Network</option>
                  <option value="clinic">Outpatient Clinic</option>
                  <option value="rehab_center">Rehabilitation Centre</option>
                  <option value="public_health">Public Health Authority</option>
                  <option value="employer">Employer / Occupational Health</option>
                </Select>
              </div>

              <div className="space-y-2 pt-1">
                <div className="flex items-center gap-1.5 text-xs font-medium text-slate-700">
                  <CheckSquare className="h-3.5 w-3.5 text-teal-700" />
                  Enabled Application Tracks
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {TRACK_OPTIONS.map((t) => {
                    const checked = tracks.includes(t.id);
                    return (
                      <label
                        key={t.id}
                        className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-xs transition-colors ${
                          checked
                            ? "border-teal-600 bg-teal-50 text-teal-950 font-medium"
                            : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleTrack(t.id)}
                          className="accent-teal-700"
                        />
                        <span>{t.label}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="border-t border-slate-200 pt-4 space-y-3">
              <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-600">
                <ShieldCheck className="h-3.5 w-3.5 text-teal-700" />
                {isBootstrap ? "Platform Administrator Account" : "Organisation Admin Account"}
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="admin-full-name">Full Name</Label>
                  <Input
                    id="admin-full-name"
                    required
                    minLength={2}
                    maxLength={200}
                    placeholder="Dr. Tariq Saeed"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="admin-license">Clinical License (Optional)</Label>
                  <Input
                    id="admin-license"
                    maxLength={80}
                    placeholder="DOH-PHY-1001"
                    value={license}
                    onChange={(e) => setLicense(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="admin-email">Admin Email</Label>
                  <Input
                    id="admin-email"
                    type="email"
                    required
                    placeholder="admin@organisation.ae"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="admin-password">Password (min 10 characters)</Label>
                  <Input
                    id="admin-password"
                    type="password"
                    required
                    minLength={10}
                    maxLength={128}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
              </div>
            </div>

            <Button type="submit" disabled={submitting} className="w-full">
              {submitting
                ? isBootstrap
                  ? "Initialising Platform..."
                  : "Creating Organisation..."
                : isBootstrap
                ? "Initialise Platform & Enter Workspace"
                : "Create Organisation & Sign In"}
            </Button>

            {!isBootstrap && (
              <div className="flex items-center justify-between pt-1 text-xs text-slate-500">
                <span>New organisations are strictly tenant-isolated</span>
                <Link href="/login" className="font-medium text-teal-700 hover:underline">
                  Already registered? Back to Sign In
                </Link>
              </div>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
