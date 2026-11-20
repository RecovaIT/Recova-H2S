"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2, ShieldAlert } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useLanguage } from "@/hooks/useLanguage";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { Card, CardContent } from "@/components/ui/card";

export function AuthGuard({
  children,
  requiredPermission,
  requiredTrack,
}: {
  children: React.ReactNode;
  requiredPermission?: string;
  requiredTrack?: string;
}) {
  const router = useRouter();
  const { session, loading, hasPermission, hasTrack } = useAuth();
  const { t, tr } = useLanguage();

  useEffect(() => {
    if (loading) return;
    if (!session) {
      router.replace("/login");
    }
  }, [loading, session, router]);

  if (loading || !session) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="flex items-center gap-2.5 text-sm text-slate-600">
          <Loader2 className="h-4 w-4 animate-spin text-teal-700" />
          <span>
            {tr("Opening your workspace...", "جارٍ فتح مساحة عملك...")}
          </span>
        </div>
      </div>
    );
  }

  if (requiredPermission && !hasPermission(requiredPermission)) {
    return (
      <div className="relative p-8">
        <LanguageSwitcher variant="floating" />
        <Card className="mx-auto max-w-lg border-red-200">
          <CardContent className="flex items-start gap-3 pt-6">
            <ShieldAlert className="h-5 w-5 text-red-600" />
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                {t("Access Restricted")}
              </h2>
              <p className="mt-1 text-xs text-slate-600">
                {tr(
                  "Your account cannot access this area. Contact your facility administrator if you need access.",
                  "لا يتيح حسابك الوصول إلى هذا القسم. تواصل مع مسؤول منشأتك إذا كنت تحتاج إلى الوصول.",
                )}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (requiredTrack && !hasTrack(requiredTrack)) {
    return (
      <div className="relative p-8">
        <LanguageSwitcher variant="floating" />
        <Card className="mx-auto max-w-lg border-amber-200">
          <CardContent className="flex items-start gap-3 pt-6">
            <ShieldAlert className="h-5 w-5 text-amber-600" />
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                {tr("Programme unavailable", "البرنامج غير متاح")}
              </h2>
              <p className="mt-1 text-xs text-slate-600">
                {tr(
                  "This programme is not enabled for your account or facility. Contact your facility administrator.",
                  "هذا البرنامج غير مفعّل لحسابك أو منشأتك. تواصل مع مسؤول منشأتك.",
                )}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <React.Fragment key={session.active_organization?.id ?? "platform"}>
      {children}
    </React.Fragment>
  );
}
