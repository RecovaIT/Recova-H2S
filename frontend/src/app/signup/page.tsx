"use client";

import React, { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { workspacePath } from "@/lib/auth-routing";
import { OrganizationOnboardingCard } from "@/components/OrganizationOnboardingCard";

function SignupContent() {
  const programme = useSearchParams().get("programme");
  const initialProgramme =
    programme === "loop" || programme === "neuro" || programme === "worksafe"
      ? programme
      : "core";
  const { session, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && session) {
      router.replace(workspacePath(session.role));
    }
  }, [loading, session, router]);

  if (loading || session) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-900 text-sm text-slate-300">
        Loading onboarding workspace...
      </div>
    );
  }

  return (
    <OrganizationOnboardingCard
      mode="register"
      initialProgramme={initialProgramme}
      key={initialProgramme}
    />
  );
}

export default function SignupPage() {
  return (
    <Suspense
      fallback={
        <p className="p-8 text-sm text-slate-600">
          Preparing your workspace setup...
        </p>
      }
    >
      <SignupContent />
    </Suspense>
  );
}
