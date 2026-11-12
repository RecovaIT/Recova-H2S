"use client";

import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { LoopWorkspace } from "@/features/loop/LoopWorkspace";

export default function LoopPage() {
  return (
    <AuthGuard requiredPermission="pipeline:read" requiredTrack="loop">
      <AppShell
        title="Recova Loop"
        subtitle="IFHAS Screening-to-Care Navigation, Insurance Routing & Closed-Loop Follow-Up"
      >
        <LoopWorkspace />
      </AppShell>
    </AuthGuard>
  );
}
