"use client";

import React, { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { OrganizationOnboardingCard } from "@/components/OrganizationOnboardingCard";

function RegisterOrganizationContent() {
  const programme = useSearchParams().get("programme");
  const initialProgramme =
    programme === "loop" || programme === "neuro" || programme === "worksafe"
      ? programme
      : "core";
  const { session, loading, needsBootstrap } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && session) {
      router.replace("/dashboard");
    } else if (!loading && needsBootstrap) {
      router.replace("/bootstrap");
    }
  }, [loading, session, needsBootstrap, router]);

  if (loading || session || needsBootstrap) {
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

export default function RegisterOrganizationPage() {
  return (
    <Suspense
      fallback={
        <p className="p-8 text-sm text-slate-600">
          Preparing your workspace setup...
        </p>
      }
    >
      <RegisterOrganizationContent />
    </Suspense>
  );
}
