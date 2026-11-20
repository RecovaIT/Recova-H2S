"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useLanguage } from "@/hooks/useLanguage";
import { authService } from "@/services/auth";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import type { PortalLang } from "@/lib/portal-i18n";

const INVITE_COPY = {
  en: {
    title: "Your Recova patient portal",
    checking: "Checking your private invitation…",
    invitedDesc: (facility: string, email: string) =>
      `${facility} invited ${email}. Your care stays linked to this facility.`,
    unavailable: "Invitation unavailable",
    expiredSuffix: "Ask your facility to resend the invitation if it expired.",
    signedInAs: (email: string) => `Signed in as ${email}`,
    linking: "Linking…",
    acceptAndOpen: "Accept invitation and open portal",
    useDifferent: "Use a different account",
    existingHint:
      "Use your existing password. Accepting this invitation will add this facility to your patient portal.",
    signInToAccept: "Sign in to accept",
    forgotPassword: "Forgot password?",
    fullName: "Your full name",
    createPassword: "Create your password",
    passwordHint: "At least 10 characters, including a letter and number.",
    confirmPassword: "Confirm password",
    passwordMismatch: "Passwords do not match",
    settingUp: "Setting up…",
    setupPortal: "Set up my portal",
    setupError: "Could not complete setup",
    backToLogin: "Back to sign in",
    loading: "Loading invitation…",
    switchLang: "العربية",
  },
  ar: {
    title: "بوابة المريض الخاصة بك في ريكوفا",
    checking: "جارٍ التحقق من دعوتك الخاصة…",
    invitedDesc: (facility: string, email: string) =>
      `دعتك ${facility} عبر ${email}. تبقى رعايتك مرتبطة بهذه المنشأة.`,
    unavailable: "الدعوة غير متاحة",
    expiredSuffix: "اطلب من منشأتك إعادة إرسال الدعوة إذا انتهت صلاحيتها.",
    signedInAs: (email: string) => `مسجل الدخول باسم ${email}`,
    linking: "جارٍ الربط…",
    acceptAndOpen: "قبول الدعوة وفتح البوابة",
    useDifferent: "استخدام حساب آخر",
    existingHint:
      "استخدم كلمة المرور الحالية الخاصة بك. قبول هذه الدعوة سيضيف هذه المنشأة إلى بوابة المريض لديك.",
    signInToAccept: "تسجيل الدخول للقبول",
    forgotPassword: "هل نسيت كلمة المرور؟",
    fullName: "الاسم الكامل",
    createPassword: "أنشئ كلمة المرور",
    passwordHint: "10 أحرف على الأقل تتضمن حرفاً ورقماً.",
    confirmPassword: "تأكيد كلمة المرور",
    passwordMismatch: "كلمتا المرور غير متطابقتين",
    settingUp: "جارٍ الإعداد…",
    setupPortal: "إعداد بوابتي",
    setupError: "تعذّر إكمال الإعداد",
    backToLogin: "العودة إلى تسجيل الدخول",
    loading: "جارٍ تحميل الدعوة…",
    switchLang: "English",
  },
} as const;

function Setup() {
  const token = useSearchParams().get("token") || "";
  const router = useRouter();
  const { session, refreshSession, logout } = useAuth();
  const { setLang: setGlobalLang } = useLanguage();
  const [lang, setLang] = useState<PortalLang>(() => {
    if (typeof window === "undefined") return "en";
    const saved =
      window.localStorage.getItem("recova_portal_lang") ||
      window.localStorage.getItem("recova_lang");
    return saved === "ar" ? "ar" : "en";
  });
  const [details, setDetails] = useState<{
    facility: string;
    email_masked: string;
    existing_account: boolean;
    used: boolean;
  } | null>(null);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const t = INVITE_COPY[lang];

  function toggleLang() {
    const next: PortalLang = lang === "en" ? "ar" : "en";
    setLang(next);
    setGlobalLang(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("recova_portal_lang", next);
      window.localStorage.setItem("recova_lang", next);
    }
  }

  useEffect(() => {
    let active = true;
    api
      .post<{
        facility: string;
        email_masked: string;
        existing_account: boolean;
        used: boolean;
      }>("/auth/portal-invitations/inspect", { token })
      .then((d) => {
        if (active) setDetails(d);
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : "Invitation unavailable");
      });
    return () => {
      active = false;
    };
  }, [token]);

  async function accept(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (session) {
        await authService.acceptPortalInvitation(token);
      } else {
        if (password !== repeat) throw new Error(t.passwordMismatch);
        await authService.completePortalInvitation({
          token,
          new_password: password,
          full_name: name,
        });
      }
      await refreshSession();
      router.replace("/portal");
    } catch (err) {
      setError(err instanceof Error ? err.message : t.setupError);
    } finally {
      setBusy(false);
    }
  }

  const next = `/accept-invitation?token=${encodeURIComponent(token)}`;
  return (
    <main
      dir={lang === "ar" ? "rtl" : "ltr"}
      lang={lang}
      className={cn(
        "flex min-h-screen items-center justify-center bg-slate-100 p-4",
        lang === "ar" && "text-right font-sans",
      )}
    >
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <CardTitle>{t.title}</CardTitle>
            <Button type="button" variant="ghost" size="sm" onClick={toggleLang}>
              {t.switchLang}
            </Button>
          </div>
          <CardDescription>
            {details
              ? t.invitedDesc(details.facility, details.email_masked)
              : t.checking}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <Alert variant="danger">
              {error} {t.expiredSuffix}
            </Alert>
          )}
          {details &&
            (session ? (
              <form onSubmit={accept} className="space-y-4">
                <p className="text-sm">{t.signedInAs(session.user.email)}</p>
                <Button disabled={busy} type="submit">
                  {busy ? t.linking : t.acceptAndOpen}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => void logout()}
                >
                  {t.useDifferent}
                </Button>
              </form>
            ) : details.existing_account ? (
              <>
                <p className="text-sm">{t.existingHint}</p>
                <Link href={`/login?next=${encodeURIComponent(next)}`}>
                  <Button>{t.signInToAccept}</Button>
                </Link>
                <Link className="block text-sm underline" href="/forgot-password">
                  {t.forgotPassword}
                </Link>
              </>
            ) : (
              <form onSubmit={accept} className="space-y-4">
                <div>
                  <Label htmlFor="setup-name">{t.fullName}</Label>
                  <Input
                    id="setup-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    minLength={2}
                    autoComplete="name"
                  />
                </div>
                <div>
                  <Label htmlFor="setup-password">{t.createPassword}</Label>
                  <Input
                    id="setup-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={10}
                    autoComplete="new-password"
                  />
                  <p className="mt-1 text-xs text-slate-500">{t.passwordHint}</p>
                </div>
                <div>
                  <Label htmlFor="setup-repeat">{t.confirmPassword}</Label>
                  <Input
                    id="setup-repeat"
                    type="password"
                    value={repeat}
                    onChange={(e) => setRepeat(e.target.value)}
                    required
                    autoComplete="new-password"
                  />
                </div>
                <Button className="w-full" disabled={busy} type="submit">
                  {busy ? t.settingUp : t.setupPortal}
                </Button>
              </form>
            ))}
          <Link className="block text-sm underline" href="/login">
            {t.backToLogin}
          </Link>
        </CardContent>
      </Card>
    </main>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense fallback={<p className="p-6">Loading invitation…</p>}>
      <Setup />
    </Suspense>
  );
}
