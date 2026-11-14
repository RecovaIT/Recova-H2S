"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2, ShieldAlert } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
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
  const { session, loading, needsBootstrap, hasPermission, hasTrack } = useAuth();

  useEffect(() => {
    if (loading) return;
    if (needsBootstrap) {
      router.replace("/bootstrap");
      return;
    }
    if (!session) {
      router.replace("/login");
    }
  }, [loading, needsBootstrap, session, router]);

  if (loading || !session) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="flex items-center gap-2.5 text-sm text-slate-600">
          <Loader2 className="h-4 w-4 animate-spin text-teal-700" />
          <span>Verifying secure clinical session...</span>
        </div>
      </div>
    );
  }

  if (requiredPermission && !hasPermission(requiredPermission)) {
    return (
      <div className="p-8">
        <Card className="mx-auto max-w-lg border-red-200">
          <CardContent className="flex items-start gap-3 pt-6">
            <ShieldAlert className="h-5 w-5 text-red-600" />
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Access Restricted</h2>
              <p className="mt-1 text-xs text-slate-600">
                Your active role ({session.role}) does not include permission{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5">{requiredPermission}</code>.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (requiredTrack && !hasTrack(requiredTrack)) {
    return (
      <div className="p-8">
        <Card className="mx-auto max-w-lg border-amber-200">
          <CardContent className="flex items-start gap-3 pt-6">
            <ShieldAlert className="h-5 w-5 text-amber-600" />
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Track Not Enabled for Role/Org</h2>
              <p className="mt-1 text-xs text-slate-600">
                Track <code className="rounded bg-slate-100 px-1 py-0.5">{requiredTrack}</code> is not enabled for your role or active organisation.
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
