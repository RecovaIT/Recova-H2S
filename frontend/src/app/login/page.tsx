"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Building2, Lock } from "lucide-react";
import { RecovaMark } from "@/components/RecovaMark";
import { useAuth } from "@/hooks/useAuth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";

export default function LoginPage() {
  const router = useRouter();
  const { session, needsBootstrap, loading, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (needsBootstrap) {
      router.replace("/bootstrap");
    } else if (session) {
      router.replace(session?.role === "patient" ? "/portal" : "/dashboard");
    }
  }, [loading, needsBootstrap, session, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await login({ email: email.trim(), password });
      router.replace(result.role === "patient" ? "/portal" : "/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <Card className="w-full max-w-md shadow-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-11 w-11 items-center justify-center rounded-xl bg-teal-700 text-[#aeff9a]">
            <RecovaMark size={28} />
          </div>
          <CardTitle className="text-xl">Welcome to Recova</CardTitle>
          <CardDescription>
            Sign in with your clinical or organisational credentials.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <Alert variant="danger">{error}</Alert>}

            <div className="space-y-1">
              <Label htmlFor="login-email">Email Address</Label>
              <Input
                id="login-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="clinician@hospital.ae"
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="login-password">Password</Label>
              <Input
                id="login-password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <Button type="submit" disabled={submitting} className="w-full">
              <Lock className="h-4 w-4" />
              {submitting ? "Authenticating..." : "Sign In"}
            </Button>

            <div className="flex items-center justify-between text-xs text-slate-500 pt-1">
              <Link href="/forgot-password" className="text-teal-700 hover:underline">
                Forgot password?
              </Link>
              <span>Zero hardcoded demo credentials</span>
            </div>

            <div className="border-t border-slate-200 pt-4">
              <p className="mb-2 text-center text-xs text-slate-500">
                Onboarding a new clinic, hospital, or employer workspace?
              </p>
              <Link
                href="/register-organization"
                className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-800 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600"
              >
                <Building2 className="h-4 w-4 text-teal-700" />
                Add New Organisation
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
