"use client";

import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { NeuroActivityGame } from "@/features/neuro/NeuroActivityGame";

export default function NeuroPage() {
  return (
    <AuthGuard requiredPermission="pipeline:read" requiredTrack="neuro">
      <AppShell
        title="Recova Neuro"
        subtitle="Non-Diagnostic Cognitive Wellness Monitoring (Adults 50–75) with Confounder Calibration"
      >
        <NeuroActivityGame />
      </AppShell>
    </AuthGuard>
  );
}
