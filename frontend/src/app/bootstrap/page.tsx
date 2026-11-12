"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldPlus } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";

const ALL_TRACKS = ["core", "loop", "neuro", "worksafe"];

export default function BootstrapPage() {
  const router = useRouter();
  const { loading, needsBootstrap, session, bootstrap } = useAuth();

  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [orgType, setOrgType] = useState<"hospital" | "clinic" | "rehab_center" | "public_health" | "employer">("hospital");
  const [tracks, setTracks] = useState<string[]>(ALL_TRACKS);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [license, setLicense] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (session) {
      router.replace("/dashboard");
    } else if (!needsBootstrap) {
      router.replace("/login");
    }
  }, [loading, needsBootstrap, session, router]);

  const toggleTrack = (t: string) => {
    setTracks((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await bootstrap({
        organization_name: orgName.trim(),
        organization_slug: orgSlug.trim().toLowerCase(),
        org_type: orgType,
        enabled_tracks: tracks,
        admin_full_name: fullName.trim(),
        admin_email: email.trim(),
        admin_password: password,
        admin_license_number: license.trim() || undefined,
      });
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Platform bootstrap failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <Card className="w-full max-w-xl shadow-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xl">
            <ShieldPlus className="h-5 w-5 text-teal-700" />
            Initialise Recova Platform
          </CardTitle>
          <CardDescription>
            First-time setup: create the primary healthcare organisation and first Platform Administrator account. This endpoint locks permanently after creation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <Alert variant="danger">{error}</Alert>}

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label>Organisation Name *</Label>
                <Input
                  required
                  value={orgName}
                  onChange={(e) => {
                    setOrgName(e.target.value);
                    if (!orgSlug) {
                      setOrgSlug(
                        e.target.value
                          .toLowerCase()
                          .replace(/[^a-z0-9]+/g, "-")
                          .replace(/(^-|-$)/g, "")
                      );
                    }
                  }}
                  placeholder="Abu Dhabi Anticipatory Health Hub"
                />
              </div>
              <div className="space-y-1">
                <Label>Organisation Slug *</Label>
                <Input
                  required
                  pattern="[a-z0-9-]+"
                  value={orgSlug}
                  onChange={(e) => setOrgSlug(e.target.value.toLowerCase())}
                  placeholder="ad-health-hub"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label>Organisation Type</Label>
                <Select value={orgType} onChange={(e) => setOrgType(e.target.value as typeof orgType)}>
                  <option value="hospital">Hospital / Health System</option>
                  <option value="clinic">Outpatient Clinic</option>
                  <option value="rehab_center">Rehabilitation Center</option>
                  <option value="public_health">Public Health Authority</option>
                  <option value="employer">Workforce Employer</option>
                </Select>
              </div>
              <div className="space-y-1">
                <Label>Enabled Tracks</Label>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {ALL_TRACKS.map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => toggleTrack(t)}
                      className={`rounded border px-2 py-1 text-xs uppercase cursor-pointer ${
                        tracks.includes(t)
                          ? "border-teal-600 bg-teal-50 text-teal-900 font-semibold"
                          : "border-slate-200 bg-white text-slate-500"
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="border-t border-slate-100 pt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label>Administrator Full Name *</Label>
                <Input required value={fullName} onChange={(e) => setFullName(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>Clinician / Admin License No.</Label>
                <Input value={license} onChange={(e) => setLicense(e.target.value)} placeholder="DOH-12345" />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label>Administrator Email *</Label>
                <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>Strong Password (min 10 chars) *</Label>
                <Input
                  type="password"
                  required
                  minLength={10}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "Initialising Platform..." : "Create Organisation & Admin Account"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
