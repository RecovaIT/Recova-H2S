"use client";

import React, { useEffect, useState } from "react";
import { Download } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { opsService } from "@/services/ops";
import type { OverviewReport } from "@/types/recova";
import { downloadJsonFile, formatLabel } from "@/lib/utils";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";

export default function ReportsPage() {
  const [overview, setOverview] = useState<OverviewReport | null>(null);

  useEffect(() => {
    opsService.getOverview().then(setOverview).catch(() => undefined);
  }, []);

  const funnelData = overview
    ? Object.entries(overview.referral_funnel).map(([stage, count]) => ({
        stage: formatLabel(stage),
        count,
      }))
    : [];

  return (
    <AuthGuard requiredPermission="reports:read">
      <AppShell
        title="Clinical &amp; Operational Reports"
        subtitle="Aggregated closed-loop referral conversion, SLA compliance, and population risk metrics from PostgreSQL."
        actions={
          overview ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => downloadJsonFile("recova-overview-report.json", overview)}
            >
              <Download className="h-4 w-4" /> Export JSON Report
            </Button>
          ) : undefined
        }
      >
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Closed-Loop Referral Conversion Funnel</CardTitle>
              <CardDescription>
                Real database counts across referral lifecycle stages.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {funnelData.length === 0 ? (
                <EmptyState
                  title="No referral transitions recorded"
                  description="Once referrals are created and progressed, conversion metrics render here."
                />
              ) : (
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={funnelData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="stage" tick={{ fontSize: 11 }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#0f766e" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </AppShell>
    </AuthGuard>
  );
}
