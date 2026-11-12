"use client";

import React, { useCallback, useEffect, useState } from "react";
import { ClipboardCheck } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { careService } from "@/services/care";
import { engineService } from "@/services/engine";
import type { ClinicalReview, PipelineRun, PipelineRunDetail, Referral } from "@/types/recova";
import { formatDateTime, formatLabel } from "@/lib/utils";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { DecideAiReviewWorkspace } from "@/components/DecideAiReviewWorkspace";
import { RiskBadge } from "@/components/RiskBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function ClinicalReviewsPage() {
  const { hasPermission } = useAuth();
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [reviews, setReviews] = useState<ClinicalReview[]>([]);
  const [selectedRun, setSelectedRun] = useState<PipelineRunDetail | null>(null);
  const [referrals, setReferrals] = useState<Referral[]>([]);

  const loadData = useCallback(async () => {
    const [rPage, revPage, refPage] = await Promise.all([
      engineService.listRuns({ page: 1, page_size: 30 }),
      careService.listReviews({ page: 1, page_size: 30 }),
      careService.listReferrals({ page: 1, page_size: 50 }),
    ]);
    setRuns(rPage.items);
    setReviews(revPage.items);
    setReferrals(refPage.items);
    if (rPage.items.length > 0 && !selectedRun) {
      setSelectedRun(await engineService.getRun(rPage.items[0].id));
    }
  }, [selectedRun]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadData();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadData]);

  const reviewedRunIds = new Set(reviews.map((r) => r.run_id));
  const pendingRuns = runs.filter(
    (r) =>
      !reviewedRunIds.has(r.id) &&
      ["AMBER", "RED", "EMERGENCY_BYPASS"].includes(r.risk_tier || "")
  );

  return (
    <AuthGuard requiredPermission="reviews:read">
      <AppShell
        title="DECIDE-AI Clinical Review Queue"
        subtitle="Human-in-the-loop governance: review Agent 4 deterministic drift and Agent 5 drafts prior to care action."
      >
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ClipboardCheck className="h-4 w-4 text-amber-600" />
                Runs Awaiting Clinician Sign-Off ({pendingRuns.length})
              </CardTitle>
              <CardDescription>
                Elevated AMBER, RED, and EMERGENCY_BYPASS executions without a cryptographic clinician review.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {pendingRuns.length === 0 ? (
                <EmptyState
                  title="Review queue is clear"
                  description="All elevated AMBER/RED pipeline runs have been signed, or no elevated drift runs have occurred yet."
                />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Run</TableHead>
                      <TableHead>Track</TableHead>
                      <TableHead>Risk Tier</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pendingRuns.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell className="font-mono text-xs">{r.id.slice(0, 8)}</TableCell>
                        <TableCell className="text-xs uppercase font-medium">{r.track}</TableCell>
                        <TableCell><RiskBadge tier={r.risk_tier} /></TableCell>
                        <TableCell className="text-xs text-slate-500">{formatDateTime(r.created_at)}</TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            onClick={async () => setSelectedRun(await engineService.getRun(r.id))}
                          >
                            Review &amp; Sign
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {selectedRun && (
            <DecideAiReviewWorkspace
              run={selectedRun}
              referrals={referrals.filter((ref) => ref.patient_id === selectedRun.patient_id)}
              existingReviews={reviews}
              canSign={hasPermission("reviews:sign")}
              onSigned={async () => {
                await loadData();
                setSelectedRun(await engineService.getRun(selectedRun.id));
              }}
            />
          )}

          <Card>
            <CardHeader>
              <CardTitle>Signed DECIDE-AI Audit Log ({reviews.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {reviews.length === 0 ? (
                <p className="text-xs text-slate-500">No clinician signatures recorded yet.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Decision</TableHead>
                      <TableHead>Role / License</TableHead>
                      <TableHead>Notes</TableHead>
                      <TableHead>Signed At</TableHead>
                      <TableHead>SHA-256</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {reviews.map((rv) => (
                      <TableRow key={rv.id}>
                        <TableCell className="text-xs font-semibold">{formatLabel(rv.decision)}</TableCell>
                        <TableCell className="text-xs">
                          {formatLabel(rv.reviewer_role)} {rv.reviewer_license ? `(${rv.reviewer_license})` : ""}
                        </TableCell>
                        <TableCell className="text-xs text-slate-600 max-w-md truncate">
                          {rv.clinician_notes || "—"}
                        </TableCell>
                        <TableCell className="text-xs text-slate-500">{formatDateTime(rv.signed_at)}</TableCell>
                        <TableCell className="font-mono text-[11px] text-slate-400">
                          {rv.signature_hash.slice(0, 12)}…
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      </AppShell>
    </AuthGuard>
  );
}
