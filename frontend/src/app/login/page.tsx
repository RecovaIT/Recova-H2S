"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Building2, Eye, EyeOff, Lock } from "lucide-react";
import { RecovaMark } from "@/components/RecovaMark";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useAuth } from "@/hooks/useAuth";
import { useLanguage } from "@/hooks/useLanguage";
import { workspacePath } from "@/lib/auth-routing";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";

export default function LoginPage() {
  const router = useRouter();
  const { session, loading, login } = useAuth();
  const { tr } = useLanguage();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (session) {
      const next = new URLSearchParams(window.location.search).get("next");
      if (next?.startsWith("/accept-invitation?")) {
        router.replace(next);
        return;
      }
      router.replace(workspacePath(session.role));
    }
  }, [loading, session, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await login({ email: email.trim(), password });
      const next = new URLSearchParams(window.location.search).get("next");
      if (next?.startsWith("/accept-invitation?")) {
        router.replace(next);
        return;
      }
      router.replace(workspacePath(result.role));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <LanguageSwitcher variant="floating" />
      <Card className="w-full max-w-md shadow-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-11 w-11 items-center justify-center rounded-xl bg-teal-700 text-[#aeff9a]">
            <RecovaMark size={28} />
          </div>
          <CardTitle className="text-xl">
            {tr("Welcome to Recova", "مرحبًا بك في ريكوفا")}
          </CardTitle>
          <CardDescription>
            {tr(
              "Sign in to your Recova account.",
              "سجّل الدخول إلى حسابك في ريكوفا.",
            )}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && <Alert variant="danger">{error}</Alert>}

            <div className="space-y-1">
              <Label htmlFor="login-email">
                {tr("Email Address", "البريد الإلكتروني")}
              </Label>
              <Input
                id="login-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="login-password">
                {tr("Password", "كلمة المرور")}
              </Label>
              <div className="relative">
                <Input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 focus:outline-none"
                  aria-label={showPassword ? "Hide input" : "Reveal input"}
                  title={showPassword ? "Hide input" : "Reveal input"}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <Button type="submit" disabled={submitting} className="w-full">
              <Lock className="h-4 w-4" />
              {submitting
                ? tr("Authenticating...", "جارٍ التحقق...")
                : tr("Sign In", "تسجيل الدخول")}
            </Button>

            <div className="flex items-center justify-between text-xs text-slate-500 pt-1">
              <Link
                href="/forgot-password"
                className="text-teal-700 hover:underline"
              >
                {tr("Forgot password?", "هل نسيت كلمة المرور؟")}
              </Link>
              <span>{tr("Private account access", "دخول خاص إلى حسابك")}</span>
            </div>

            <div className="border-t border-slate-200 pt-4">
              <p className="mb-2 text-center text-xs text-slate-500">
                {tr(
                  "Onboarding a new clinic, hospital, or employer workspace?",
                  "هل تقوم بتسجيل عيادة أو مستشفى أو جهة عمل جديدة؟",
                )}
              </p>
              <Link
                href="/signup"
                className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-800 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600"
              >
                <Building2 className="h-4 w-4 text-teal-700" />
                {tr("Sign up", "إنشاء حساب")}
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
