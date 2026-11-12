"use client";

import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { CoreWorkspace } from "@/features/core/CoreWorkspace";

export default function CorePage() {
  return (
    <AuthGuard requiredPermission="pipeline:read" requiredTrack="core">
      <AppShell
        title="Recova Core"
        subtitle="Relapse Prevention & Rehabilitation — Wearable HRV/Sleep/RHR & Daily Check-In Drift Intelligence"
      >
        <CoreWorkspace />
      </AppShell>
    </AuthGuard>
  );
}
