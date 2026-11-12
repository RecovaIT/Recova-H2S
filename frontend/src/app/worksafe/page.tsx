"use client";

import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { WorkSafeWorkspace } from "@/features/worksafe/WorkSafeWorkspace";

export default function WorkSafePage() {
  return (
    <AuthGuard requiredPermission="workforce:read_aggregate" requiredTrack="worksafe">
      <AppShell
        title="Recova WorkSafe"
        subtitle="Workforce Heat-Stress, Fatigue Prevention & k-Anonymity Protected Department Analytics"
      >
        <WorkSafeWorkspace />
      </AppShell>
    </AuthGuard>
  );
}
