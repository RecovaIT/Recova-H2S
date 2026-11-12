"use client";

import React, { useState } from "react";
import Link from "next/link";
import { authService } from "@/services/auth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<{ message: string; token?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await authService.requestPasswordReset(email.trim());
      setStatus({ message: res.message, token: res.reset_token });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Password Recovery</CardTitle>
          <CardDescription>
            Enter your account email to request a time-limited password reset token.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <Alert variant="danger">{error}</Alert>}
            {status && (
              <Alert variant="success" title="Reset Initiated">
                <p>{status.message}</p>
                {status.token && (
                  <p className="mt-2 font-mono text-[11px]">
                    Dev Token: <strong>{status.token}</strong>{" "}
                    <Link href={`/reset-password?token=${encodeURIComponent(status.token)}`} className="underline">
                      Reset now →
                    </Link>
                  </p>
                )}
              </Alert>
            )}
            <div className="space-y-1">
              <Label>Account Email</Label>
              <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <Button type="submit" disabled={busy} className="w-full">
              {busy ? "Requesting..." : "Request Reset"}
            </Button>
            <div className="text-center text-xs">
              <Link href="/login" className="text-teal-700 hover:underline">
                Back to Sign In
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
