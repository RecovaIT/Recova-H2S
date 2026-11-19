"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { authService } from "@/services/auth";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { type PortalLang } from "@/lib/portal-i18n";

const COPY = {
  en: {
    title: "Account security",
    verified: "Email address verified",
    unverified: "Email address has not been verified yet.",
    sendVerification: "Send verification email",
    verifyNotConfigured:
      "Verification email is waiting for the server sender to be configured. Contact your facility.",
    verifyQueued: "Verification email queued. Check your inbox and spam folder.",
    verifyFailed: "Could not request verification",
    currentPassword: "Current password",
    newPassword: "New password",
    repeatPassword: "Confirm new password",
    passwordRule: "Use at least 10 characters, including a letter and a number.",
    passwordMismatch: "New passwords do not match",
    passwordChanged: "Password changed. Other signed-in sessions were revoked.",
    passwordFailed: "Password change failed",
    submit: "Change password",
  },
  ar: {
    title: "أمان الحساب",
    verified: "تم التحقق من البريد الإلكتروني",
    unverified: "لم يتم التحقق من عنوان البريد الإلكتروني بعد.",
    sendVerification: "إرسال رسالة التحقق",
    verifyNotConfigured:
      "رسالة التحقق بانتظار إعداد خادم البريد. يرجى التواصل مع منشأتك.",
    verifyQueued: "تم إرسال طلب رسالة التحقق. يرجى فحص البريد الوارد والرسائل غير المرغوب فيها.",
    verifyFailed: "تعذّر طلب رسالة التحقق",
    currentPassword: "كلمة المرور الحالية",
    newPassword: "كلمة المرور الجديدة",
    repeatPassword: "تأكيد كلمة المرور الجديدة",
    passwordRule: "استخدم 10 أحرف على الأقل تتضمن حرفاً ورقماً.",
    passwordMismatch: "كلمتا المرور الجديدتان غير متطابقتين",
    passwordChanged: "تم تغيير كلمة المرور وإلغاء جميع الجلسات الأخرى المسجلة.",
    passwordFailed: "تعذّر تغيير كلمة المرور",
    submit: "تغيير كلمة المرور",
  },
} as const;

export function AccountSecurityPanel({ lang = "en" }: { lang?: PortalLang }) {
  const { session } = useAuth();
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const t = COPY[lang];

  async function change(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (password !== repeat) throw new Error(t.passwordMismatch);
      await authService.changePassword(current, password);
      setCurrent("");
      setPassword("");
      setRepeat("");
      setMessage(t.passwordChanged);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : t.passwordFailed);
    } finally {
      setBusy(false);
    }
  }

  async function verify() {
    setBusy(true);
    try {
      const r = await api.post<{ status: string }>("/auth/resend-verification");
      setMessage(r.status === "not_configured" ? t.verifyNotConfigured : t.verifyQueued);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : t.verifyFailed);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      dir={lang === "ar" ? "rtl" : "ltr"}
      className={
        lang === "ar"
          ? "space-y-4 rounded-xl border border-slate-200 bg-white p-5 text-right font-sans"
          : "space-y-4 rounded-xl border border-slate-200 bg-white p-5"
      }
    >
      <h2 className="font-semibold">{t.title}</h2>
      <p className="break-all text-sm">{session?.user?.email}</p>
      <p className="text-xs text-slate-600">
        {session?.user?.email_verified_at ? t.verified : t.unverified}
      </p>
      {!session?.user?.email_verified_at && (
        <Button variant="outline" disabled={busy} onClick={() => void verify()}>
          {t.sendVerification}
        </Button>
      )}
      {message && (
        <p role="status" className="text-sm">
          {message}
        </p>
      )}
      <form onSubmit={change} className="space-y-3">
        <div>
          <Label htmlFor="current-password">{t.currentPassword}</Label>
          <Input
            id="current-password"
            autoComplete="current-password"
            type="password"
            required
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="new-password">{t.newPassword}</Label>
          <Input
            id="new-password"
            autoComplete="new-password"
            type="password"
            required
            minLength={10}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="repeat-password">{t.repeatPassword}</Label>
          <Input
            id="repeat-password"
            autoComplete="new-password"
            type="password"
            required
            value={repeat}
            onChange={(e) => setRepeat(e.target.value)}
          />
        </div>
        <p className="text-xs text-slate-500">{t.passwordRule}</p>
        <Button disabled={busy} type="submit">
          {t.submit}
        </Button>
      </form>
    </section>
  );
}
