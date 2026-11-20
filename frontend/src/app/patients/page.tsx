"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Search, Users } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { opsService } from "@/services/ops";
import { patientsService } from "@/services/patients";
import { signalsService } from "@/services/signals";
import type { Department, InsurancePlan, PatientSummary } from "@/types/recova";
import { formatDate } from "@/lib/utils";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { PatientQuickCreateModal } from "@/components/PatientQuickCreateModal";
import { RiskBadge } from "@/components/RiskBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input, Select } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function PatientsPage() {
  const { session, hasPermission, hasTrack } = useAuth();
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [trackFilter, setTrackFilter] = useState("");
  const [tierFilter, setTierFilter] = useState("");
  const [loading, setLoading] = useState(true);

  const [createOpen, setCreateOpen] = useState(false);
  const [plans, setPlans] = useState<InsurancePlan[]>([]);
  const [depts, setDepts] = useState<Department[]>([]);

  const loadPatients = useCallback(async () => {
    setLoading(true);
    try {
      const res = await patientsService.list({
        page,
        page_size: 20,
        q: search.trim() || undefined,
        track: trackFilter || undefined,
        risk_tier: tierFilter || undefined,
      });
      setPatients(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [page, search, trackFilter, tierFilter]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadPatients();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadPatients]);

  useEffect(() => {
    opsService.listInsurancePlans().then(setPlans).catch(() => undefined);
    if (hasTrack("worksafe")) {
      signalsService.listDepartments().then(setDepts).catch(() => undefined);
    }
  }, [hasTrack]);

  return (
    <AuthGuard requiredPermission="patients:read">
      <AppShell
        title="Patients & Workforce Participants"
        subtitle={`Organisational directory (${total} active records). Synthetic test accounts are excluded.`}
        actions={
          hasPermission("patients:write") ? (
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" /> Register Participant
            </Button>
          ) : undefined
        }
      >
        <div className="space-y-4">
          <Card>
            <CardContent className="flex flex-wrap items-center gap-3 pt-5">
              <div className="relative flex-1 min-w-[220px]">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  value={search}
                  onChange={(e) => {
                    setPage(1);
                    setSearch(e.target.value);
                  }}
                  placeholder="Search by MRN, given name, or family name..."
                  className="pl-9"
                />
              </div>
              <div className="w-40">
                <Select
                  value={trackFilter}
                  onChange={(e) => {
                    setPage(1);
                    setTrackFilter(e.target.value);
                  }}
                >
                  <option value="">All Tracks</option>
                  {(["core", "loop", "neuro", "worksafe"] as const)
                    .filter((t) => hasTrack(t))
                    .map((t) => (
                      <option key={t} value={t}>
                        {t.charAt(0).toUpperCase() + t.slice(1)}
                      </option>
                    ))}
                </Select>
              </div>
              <div className="w-44">
                <Select
                  value={tierFilter}
                  onChange={(e) => {
                    setPage(1);
                    setTierFilter(e.target.value);
                  }}
                >
                  <option value="">All Risk Tiers</option>
                  <option value="GREEN">GREEN</option>
                  <option value="AMBER">AMBER</option>
                  <option value="RED">RED</option>
                  <option value="EMERGENCY_BYPASS">EMERGENCY_BYPASS</option>
                </Select>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-5">
              {!loading && patients.length === 0 ? (
                <EmptyState
                  icon={<Users className="h-5 w-5" />}
                  title="No participants match your criteria"
                  description="No fake sample patients are injected. Register your first patient or adjust search filters."
                  action={
                    hasPermission("patients:write") ? (
                      <Button size="sm" onClick={() => setCreateOpen(true)}>
                        <Plus className="h-4 w-4" /> Register First Participant
                      </Button>
                    ) : undefined
                  }
                />
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>MRN</TableHead>
                        <TableHead>Name</TableHead>
                        <TableHead>Type / Language</TableHead>
                        <TableHead>Enrolled Tracks</TableHead>
                        <TableHead>Latest Risk</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {patients.map((p) => {
                        const topTier =
                          p.enrollments.find((e) => e.latest_risk_tier === "EMERGENCY_BYPASS")?.latest_risk_tier ||
                          p.enrollments.find((e) => e.latest_risk_tier === "RED")?.latest_risk_tier ||
                          p.enrollments.find((e) => e.latest_risk_tier === "AMBER")?.latest_risk_tier ||
                          p.enrollments.find((e) => e.latest_risk_tier)?.latest_risk_tier;
                        return (
                          <TableRow key={p.id}>
                            <TableCell className="font-mono text-xs font-semibold">{p.mrn}</TableCell>
                            <TableCell className="text-xs font-semibold text-slate-900">
                              {p.given_name} {p.family_name}
                            </TableCell>
                            <TableCell className="text-xs text-slate-600">
                              {p.participant_type} · {p.preferred_language.toUpperCase()}
                            </TableCell>
                            <TableCell>
                              <div className="flex flex-wrap gap-1">
                                {p.enrollments.map((en) => (
                                  <Badge key={en.id} variant="outline" className="uppercase text-[10px]">
                                    {en.track}
                                  </Badge>
                                ))}
                              </div>
                            </TableCell>
                            <TableCell>
                              {topTier ? <RiskBadge tier={topTier} /> : <span className="text-xs text-slate-400">Unscored</span>}
                            </TableCell>
                            <TableCell className="text-xs text-slate-500">{formatDate(p.created_at)}</TableCell>
                            <TableCell className="text-right">
                              <Link href={`/patients/${p.id}`}>
                                <Button size="sm" variant="outline">Open Chart →</Button>
                              </Link>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>

                  <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
                    <span>Showing {patients.length} of {total}</span>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                        Previous
                      </Button>
                      <Button size="sm" variant="outline" disabled={patients.length < 20} onClick={() => setPage((p) => p + 1)}>
                        Next
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>

        <PatientQuickCreateModal
          open={createOpen}
          onOpenChange={setCreateOpen}
          allowedTracks={session?.tracks || []}
          insurancePlans={plans}
          departments={depts}
          onCreated={() => void loadPatients()}
        />
      </AppShell>
    </AuthGuard>
  );
}
