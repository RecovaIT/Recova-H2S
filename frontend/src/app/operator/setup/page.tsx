"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { workspacePath } from "@/lib/auth-routing";
import { OrganizationOnboardingCard } from "@/components/OrganizationOnboardingCard";

export default function OperatorSetupPage() {
  const { session, loading, needsBootstrap } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && session) {
      router.replace(workspacePath(session.role));
    } else if (!loading && !needsBootstrap) {
      router.replace("/login");
    }
  }, [loading, session, needsBootstrap, router]);

  if (loading || session || !needsBootstrap) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-900 text-sm text-slate-300">
        Checking operator setup availability...
      </div>
    );
  }

  return <OrganizationOnboardingCard mode="bootstrap" />;
}
