"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Clock, GitBranch } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { careService } from "@/services/care";
import type { Intervention, Referral, ReferralDetail } from "@/types/recova";
import { formatDateTime, formatLabel, formatRelativeCountdown } from "@/lib/utils";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { ClosedLoopReferralTracker } from "@/components/ClosedLoopReferralTracker";
import { StatusBadge } from "@/components/RiskBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Select } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";

export default function ReferralsPage() {
  const { hasPermission } = useAuth();
  const { pushToast } = useToast();

  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [selectedDetail, setSelectedDetail] = useState<ReferralDetail | null>(null);
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [trackFilter, setTrackFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const selectedIdRef = useRef<string | null>(null);

  useEffect(() => {
    selectedIdRef.current = selectedDetail?.id ?? null;
  }, [selectedDetail]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [refPage, ivList] = await Promise.all([
        careService.listReferrals({
          page: 1,
          page_size: 50,
          track: trackFilter || undefined,
          status: statusFilter || undefined,
        }),
        hasPermission("interventions:read") ? careService.listInterventions() : Promise.resolve([]),
      ]);
      setReferrals(refPage.items);
      setInterventions(ivList);
      const currentSelectedId = selectedIdRef.current;
      if (refPage.items.length > 0 && (!currentSelectedId || !refPage.items.some((r) => r.id === currentSelectedId))) {
        setSelectedDetail(await careService.getReferral(refPage.items[0].id));
      } else if (currentSelectedId) {
        setSelectedDetail(await careService.getReferral(currentSelectedId));
      }
    } finally {
      setLoading(false);
    }
  }, [trackFilter, statusFilter, hasPermission]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadAll();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadAll]);

  const handleEvaluateSlas = async () => {
    try {
      const res = await careService.evaluateSlas();
      pushToast("SLA evaluation executed", "info", JSON.stringify(res));
      await loadAll();
    } catch (err) {
      pushToast("SLA evaluation failed", "error", err instanceof Error ? err.message : undefined);
    }
  };

  return (
    <AuthGuard requiredPermission="referrals:read">
      <AppShell
        title="Closed-Loop Referrals &amp; Care Navigation"
        subtitle="Track Proposed → Approved → Patient Notified → Booked → Consultation Completed → Outcome Verified."
        actions={
          hasPermission("referrals:write") ? (
            <Button size="sm" variant="outline" onClick={() => void handleEvaluateSlas()}>
              <Clock className="h-3.5 w-3.5" /> Evaluate SLAs
            </Button>
          ) : undefined
        }
      >
        <div className="space-y-6">
          <Card>
            <CardContent className="flex flex-wrap items-center gap-3 pt-5">
              <div className="w-44">
                <Select value={trackFilter} onChange={(e) => setTrackFilter(e.target.value)}>
                  <option value="">All Tracks</option>
                  <option value="core">Core</option>
                  <option value="loop">Loop</option>
                  <option value="neuro">Neuro</option>
                  <option value="worksafe">WorkSafe</option>
                </Select>
              </div>
              <div className="w-52">
                <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                  <option value="">All Statuses</option>
                  <option value="proposed">Proposed</option>
                  <option value="approved">Approved</option>
                  <option value="patient_notified">Patient Notified</option>
                  <option value="booked">Booked</option>
                  <option value="consultation_completed">Consultation Completed</option>
                  <option value="outcome_verified">Outcome Verified</option>
                  <option value="missed">Missed</option>
                  <option value="escalated">Escalated</option>
                </Select>
              </div>
            </CardContent>
          </Card>

          {selectedDetail && (
            <ClosedLoopReferralTracker
              referral={selectedDetail}
              detail={selectedDetail}
              canWrite={hasPermission("referrals:write")}
              canVerifyOutcome={hasPermission("outcomes:verify")}
              onUpdated={() => void loadAll()}
            />
          )}

          <Card>
            <CardHeader>
              <CardTitle>Referral Queue ({referrals.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {!loading && referrals.length === 0 ? (
                <EmptyState
                  icon={<GitBranch className="h-5 w-5" />}
                  title="No referrals found"
                  description="Agent 6 creates proposed referrals automatically when AMBER/RED drift or emergencies occur."
                />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Track</TableHead>
                      <TableHead>Pathway</TableHead>
                      <TableHead>Facility</TableHead>
                      <TableHead>Coverage</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>SLA</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {referrals.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell className="text-xs uppercase font-semibold">{r.track}</TableCell>
                        <TableCell className="text-xs">{formatLabel(r.pathway)}</TableCell>
                        <TableCell className="text-xs">{r.owner_facility_label || "Pending"}</TableCell>
                        <TableCell className="text-xs">{formatLabel(r.coverage_status)}</TableCell>
                        <TableCell><StatusBadge status={r.status} /></TableCell>
                        <TableCell className="text-xs text-slate-500">
                          {formatRelativeCountdown(r.sla_due_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={async () => setSelectedDetail(await careService.getReferral(r.id))}
                          >
                            Manage Loop
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {interventions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Care &amp; Workforce Interventions ({interventions.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Track</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Title</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {interventions.map((iv) => (
                      <TableRow key={iv.id}>
                        <TableCell className="text-xs uppercase font-semibold">{iv.track}</TableCell>
                        <TableCell className="text-xs">{formatLabel(iv.intervention_type)}</TableCell>
                        <TableCell className="text-xs font-medium">{iv.title}</TableCell>
                        <TableCell><StatusBadge status={iv.status} /></TableCell>
                        <TableCell className="text-xs text-slate-500">{formatDateTime(iv.created_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </div>
      </AppShell>
    </AuthGuard>
  );
}
