"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { authService } from "@/services/auth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";

function ResetPasswordInner() {
  const sp = useSearchParams();
  const [token, setToken] = useState(sp.get("token") || "");
  const [newPassword, setNewPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await authService.confirmPasswordReset(token.trim(), newPassword);
      setDone(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password reset failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <Alert variant="danger">{error}</Alert>}
      {done && (
        <Alert variant="success">
          {done}{" "}
          <Link href="/login" className="font-semibold underline">
            Proceed to Login →
          </Link>
        </Alert>
      )}
      <div className="space-y-1">
        <Label>Reset Token</Label>
        <Input required value={token} onChange={(e) => setToken(e.target.value)} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="reset-new-password">New Strong Password (min 10 chars)</Label>
        <div className="relative">
          <Input
            id="reset-new-password"
            type={showPassword ? "text" : "password"}
            required
            minLength={10}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="pr-10"
          />
          <button
            type="button"
            onClick={() => setShowPassword((prev) => !prev)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 focus:outline-none"
            aria-label={showPassword ? "Hide input" : "Reveal input"}
            title={showPassword ? "Hide input" : "Reveal input"}
          >
            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </div>
      <Button type="submit" disabled={busy} className="w-full">
        {busy ? "Updating..." : "Set New Password"}
      </Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Confirm Password Reset</CardTitle>
          <CardDescription>Apply your reset token and set a new strong password.</CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense fallback={<p className="text-xs text-slate-500">Loading form...</p>}>
            <ResetPasswordInner />
          </Suspense>
        </CardContent>
      </Card>
    </div>
  );
}
