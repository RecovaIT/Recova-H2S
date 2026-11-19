"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, KeyRound, Loader2 } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { authService } from "@/services/auth";
import { RecovaMark } from "@/components/RecovaMark";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";

function AcceptInvitationContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { session, loading, refreshSession } = useAuth();
  const [token, setToken] = useState(() => searchParams.get("token") || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);

  const handleAccept = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token.trim()) {
      setError("Enter the portal invitation token issued by your care facility.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await authService.acceptPortalInvitation(token.trim());
      setAccepted(true);
      await refreshSession();
      router.replace("/portal");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not verify portal invitation.");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f0f6f9]">
        <Loader2 className="h-5 w-5 animate-spin text-[#003e5e]" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f0f6f9] p-4">
      <Card className="w-full max-w-md border-[#e2edf2] bg-white">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-11 w-11 items-center justify-center rounded-xl bg-[#003e5e] text-[#aeff9a]">
            <RecovaMark size={26} />
          </div>
          <CardTitle>Link Your Participant Portal</CardTitle>
          <CardDescription>
            Verify your single-use, recipient-bound facility invitation token to link your care record.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!session ? (
            <div className="space-y-3 text-center text-xs text-slate-600">
              <Alert variant="info">
                Sign in with the email address your care facility invited, then return here to verify your invitation token.
              </Alert>
              <Link href="/login">
                <Button className="w-full">Sign In to Continue</Button>
              </Link>
            </div>
          ) : (
            <form onSubmit={handleAccept} className="space-y-4">
              {error && <Alert variant="danger">{error}</Alert>}
              {accepted && (
                <Alert variant="success">
                  <CheckCircle2 className="inline h-4 w-4 mr-1" />
                  Invitation verified! Redirecting to your portal...
                </Alert>
              )}
              <div className="rounded-lg bg-[#f8fbfc] p-3 text-xs text-[#5a7d93]">
                Signed in as <strong className="text-[#011621]">{session.user.email}</strong>
              </div>
              <div className="space-y-1">
                <Label htmlFor="invite_token">Invitation Token</Label>
                <Input
                  id="invite_token"
                  required
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="Paste your 72h portal invitation token"
                />
              </div>
              <Button type="submit" disabled={busy} className="w-full">
                <KeyRound className="h-4 w-4" />
                {busy ? "Verifying..." : "Verify & Link My Care Record"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-[#f0f6f9]" />}>
      <AcceptInvitationContent />
    </Suspense>
  );
}
