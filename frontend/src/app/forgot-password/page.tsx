"use client";

import React, { useState } from "react";
import Link from "next/link";
import { authService } from "@/services/auth";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useLanguage } from "@/hooks/useLanguage";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";

export default function ForgotPasswordPage() {
  const { tr } = useLanguage();
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<{ message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await authService.requestPasswordReset(email.trim());
      setStatus({ message: res.message });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <LanguageSwitcher variant="floating" />
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{tr("Password Recovery", "استعادة كلمة المرور")}</CardTitle>
          <CardDescription>
            {tr(
              "Enter your account email. If an account exists, we will send a private password setup link. Contact your facility if it does not arrive.",
              "أدخل بريدك الإلكتروني. إذا كان الحساب موجودًا، فسنرسل رابطًا خاصًا لإعداد كلمة المرور."
            )}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <Alert variant="danger">{error}</Alert>}
            {status && (
              <Alert variant="success" title="Reset Initiated">
                <p>{status.message}</p>

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
