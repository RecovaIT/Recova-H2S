"use client";

import React, { useCallback, useEffect, useState } from "react";
import { BarChart3, CheckCircle2, Eye, Megaphone, Send, ShieldAlert, XCircle } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { opsService } from "@/services/ops";
import type { AuthorityNotice, AuthorityReport } from "@/types/recova";
import { formatDateTime } from "@/lib/utils";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";

export default function AuthorityPage() {
  const { session } = useAuth();
  const { pushToast } = useToast();
  const canPublish = Boolean(
    session?.user?.is_platform_admin || session?.capability_flags?.authority_publish
  );

  const [authorityNotices, setAuthorityNotices] = useState<AuthorityNotice[]>([]);
  const [visibleNotices, setVisibleNotices] = useState<AuthorityNotice[]>([]);
  const [report, setReport] = useState<AuthorityReport | null>(null);
  const [previewInfo, setPreviewInfo] = useState<{
    organization_count: number;
    recipient_count: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [actionText, setActionText] = useState("");
  const [severity, setSeverity] = useState<"info" | "advisory" | "urgent">("advisory");
  const [scopeEmirate, setScopeEmirate] = useState("");
  const [programmes, setProgrammes] = useState<string[]>(["core", "loop", "neuro", "worksafe"]);

  const loadNotices = useCallback(async () => {
    setLoading(true);
    try {
      const vis = await opsService.listVisibleNotices().catch(() => []);
      setVisibleNotices(vis);
      if (canPublish) {
        const [authList, rep] = await Promise.all([
          opsService.listAuthorityNotices().catch(() => []),
          opsService.getAuthorityReports().catch(() => null),
        ]);
        setAuthorityNotices(authList);
        setReport(rep);
      }
    } finally {
      setLoading(false);
    }
  }, [canPublish]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadNotices();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadNotices]);

  const toggleProgramme = (prog: string) => {
    setProgrammes((prev) => (prev.includes(prog) ? prev.filter((p) => p !== prog) : [...prev, prog]));
  };

  const handlePreview = async () => {
    if (!title.trim() || !message.trim() || programmes.length === 0) {
      pushToast("Enter title, message, and at least one programme to preview audience.", "error");
      return;
    }
    setBusy(true);
    try {
      const res = await opsService.previewAuthorityNotice({
        title,
        message,
        plain_language_action: actionText || undefined,
        severity,
        scope_emirate: scopeEmirate || undefined,
        eligible_programmes: programmes,
      });
      setPreviewInfo({
        organization_count: res.organization_count,
        recipient_count: res.recipient_count,
      });
    } catch (err) {
      pushToast("Audience preview failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleCreateDraft = async (e: React.FormEvent) => {
    e.preventDefault();
    if (programmes.length === 0) {
      pushToast("Select at least one eligible programme", "error");
      return;
    }
    setBusy(true);
    try {
      await opsService.createAuthorityNotice({
        title,
        message,
        plain_language_action: actionText || undefined,
        severity,
        scope_emirate: scopeEmirate || undefined,
        eligible_programmes: programmes,
        acknowledgement_required: true,
        idempotency_key:
          typeof crypto !== "undefined" && "randomUUID" in crypto
            ? crypto.randomUUID()
            : undefined,
      });
      setTitle("");
      setMessage("");
      setActionText("");
      setPreviewInfo(null);
      pushToast("Draft notice created", "success");
      await loadNotices();
    } catch (err) {
      pushToast("Failed to create draft", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handlePublish = async (id: string) => {
    setBusy(true);
    try {
      await opsService.publishAuthorityNotice(id);
      pushToast("Notice published to scoped facilities and participants", "success");
      await loadNotices();
    } catch (err) {
      pushToast("Publish failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleWithdraw = async (id: string) => {
    setBusy(true);
    try {
      await opsService.withdrawAuthorityNotice(id);
      pushToast("Notice withdrawn", "success");
      await loadNotices();
    } catch (err) {
      pushToast("Withdraw failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthGuard requiredPermission="org:read">
      <AppShell
        title="Population-Health Coordination"
        subtitle="Shared public-health notice delivery, scoped authority publishing, and k-suppressed aggregate reporting."
      >
        <div className="space-y-6">
          <Alert variant="info">
            Shared population-health coordination is provisioned for every organisation independently of Recova Loop. Out-of-scope recipients cannot retrieve scoped notices.
          </Alert>

          {canPublish && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Megaphone className="h-4 w-4 text-[#003e5e]" />
                    Draft Scoped Public-Health Notice
                  </CardTitle>
                  <CardDescription>
                    Preview audience counts within your assigned authority scope before publishing.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleCreateDraft} className="space-y-3">
                    <div>
                      <Label htmlFor="notice_title">Notice Title</Label>
                      <Input
                        id="notice_title"
                        required
                        minLength={3}
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="Extreme Heat Advisory — Outdoor Shift Precautions"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label htmlFor="notice_sev">Severity</Label>
                        <Select
                          id="notice_sev"
                          value={severity}
                          onChange={(e) => setSeverity(e.target.value as "info" | "advisory" | "urgent")}
                        >
                          <option value="info">Info</option>
                          <option value="advisory">Advisory</option>
                          <option value="urgent">Urgent</option>
                        </Select>
                      </div>
                      <div>
                        <Label htmlFor="notice_emirate">Emirate Scope (Optional)</Label>
                        <Input
                          id="notice_emirate"
                          value={scopeEmirate}
                          onChange={(e) => setScopeEmirate(e.target.value)}
                          placeholder="e.g. Abu Dhabi"
                        />
                      </div>
                    </div>
                    <div>
                      <Label>Eligible Programmes</Label>
                      <div className="mt-1.5 flex flex-wrap gap-2">
                        {["core", "loop", "neuro", "worksafe"].map((p) => (
                          <button
                            key={p}
                            type="button"
                            onClick={() => toggleProgramme(p)}
                            className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                              programmes.includes(p)
                                ? "border-[#003e5e] bg-[#003e5e] text-[#aeff9a]"
                                : "border-[#e2edf2] bg-white text-[#5a7d93]"
                            }`}
                          >
                            {p.toUpperCase()}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <Label htmlFor="notice_msg">Message</Label>
                      <Textarea
                        id="notice_msg"
                        required
                        minLength={10}
                        rows={3}
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        placeholder="Clear public-health guidance for enrolled facilities and participants..."
                      />
                    </div>
                    <div>
                      <Label htmlFor="notice_action">Plain-Language Action (Optional)</Label>
                      <Input
                        id="notice_action"
                        value={actionText}
                        onChange={(e) => setActionText(e.target.value)}
                        placeholder="Hydrate every 20 minutes and report dizziness immediately."
                      />
                    </div>
                    {previewInfo && (
                      <div className="rounded-lg border border-[#c6edbc] bg-[#e4f3dd] px-3 py-2 text-xs text-[#214e40]">
                        Draft Preview: <strong>{previewInfo.organization_count}</strong> eligible organisation(s) ·{" "}
                        <strong>{previewInfo.recipient_count}</strong> recipient account(s)
                      </div>
                    )}
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" variant="outline" disabled={busy} onClick={() => void handlePreview()}>
                        <Eye className="h-3.5 w-3.5" /> Preview Audience
                      </Button>
                      <Button type="submit" disabled={busy}>
                        Save Draft Notice
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Published &amp; Draft Notices ({authorityNotices.length})</CardTitle>
                  <CardDescription>Audited delivery, read states, and acknowledgement counts</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {loading ? (
                    <div className="h-24 animate-pulse rounded-xl bg-slate-100" />
                  ) : authorityNotices.length === 0 ? (
                    <EmptyState
                      icon={<ShieldAlert className="h-5 w-5" />}
                      title="No notices yet"
                      description="Create a draft public-health notice to publish across eligible programmes."
                    />
                  ) : (
                    authorityNotices.map((n) => (
                      <div key={n.id} className="rounded-xl border border-[#e2edf2] bg-[#f8fbfc] p-3.5 text-xs">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <strong className="text-sm text-[#011621]">
                            {n.title} (v{n.version})
                          </strong>
                          <div className="flex items-center gap-1.5">
                            <Badge variant="outline">{n.severity}</Badge>
                            <Badge variant="outline">{n.status}</Badge>
                          </div>
                        </div>
                        <p className="mt-1.5 text-[#2a4558]">{n.message}</p>
                        <p className="mt-2 text-[11px] text-[#5a7d93]">
                          Scope: {n.scope_emirate || "All Emirates"} · Programmes: {n.eligible_programmes.join(", ")} ·{" "}
                          {n.read_count ?? 0} read ·{" "}
                          <CheckCircle2 className="inline h-3 w-3 text-[#1a7a0a]" /> {n.acknowledgement_count} acknowledged
                          {n.published_at ? ` · Published ${formatDateTime(n.published_at)}` : ""}
                        </p>
                        <div className="mt-3 flex gap-2">
                          {n.status === "draft" && (
                            <Button size="sm" disabled={busy} onClick={() => void handlePublish(n.id)}>
                              <Send className="h-3.5 w-3.5" /> Publish
                            </Button>
                          )}
                          {n.status === "published" && (
                            <Button size="sm" variant="outline" disabled={busy} onClick={() => void handleWithdraw(n.id)}>
                              <XCircle className="h-3.5 w-3.5" /> Withdraw
                            </Button>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            </div>
          )}

          {canPublish && report && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-[#003e5e]" />
                  Scoped Authority Population Report (k ≥ {report.k_threshold} Suppression)
                </CardTitle>
                <CardDescription>
                  Across {report.scoped_organization_count} scoped facility/facilities. Small cohorts (&lt; {report.k_threshold}) are suppressed.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-4 text-xs">
                {Object.entries(report.programme_summary).map(([prog, stats]) => (
                  <div key={prog} className="rounded-xl border border-[#e2edf2] bg-[#f8fbfc] p-3">
                    <div className="font-semibold uppercase text-[#003e5e]">{prog}</div>
                    <div className="mt-1 text-lg font-bold text-[#011621]">
                      {stats.suppressed_k_anonymity
                        ? "Suppressed (< k)"
                        : (stats.participant_count ?? 0)}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Active Scoped Notices for Your Organisation ({visibleNotices.length})</CardTitle>
              <CardDescription>In-app public-health notices visible to your active facility and programme.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {loading ? (
                <div className="h-20 animate-pulse rounded-xl bg-slate-100" />
              ) : visibleNotices.length === 0 ? (
                <EmptyState
                  icon={<Megaphone className="h-5 w-5" />}
                  title="No active public-health notices"
                  description="Published notices scoped to your facility's geography and programme appear here."
                />
              ) : (
                visibleNotices.map((n) => (
                  <div key={n.id} className="rounded-xl border border-[#e2edf2] bg-white p-4 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <strong className="text-sm text-[#011621]">{n.title}</strong>
                      <div className="flex items-center gap-1.5">
                        <Badge variant="outline">{n.severity}</Badge>
                        <Badge variant="outline">{n.recipient_state || (n.acknowledged ? "acknowledged" : "available")}</Badge>
                      </div>
                    </div>
                    <p className="mt-1.5 text-[#2a4558]">{n.message}</p>
                    {n.plain_language_action && (
                      <p className="mt-1.5 rounded-lg bg-[#f0f6f9] px-2.5 py-1.5 font-medium text-[#003e5e]">
                        Action: {n.plain_language_action}
                      </p>
                    )}
                    <div className="mt-3 flex flex-wrap gap-2">
                      {n.recipient_state === "available" && !n.acknowledged && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={async () => {
                            setBusy(true);
                            try {
                              await opsService.markNoticeRead(n.id);
                              await loadNotices();
                            } finally {
                              setBusy(false);
                            }
                          }}
                        >
                          Mark Read
                        </Button>
                      )}
                      <Button
                        size="sm"
                        disabled={busy || Boolean(n.acknowledged)}
                        onClick={async () => {
                          setBusy(true);
                          try {
                            await opsService.acknowledgeNotice(n.id);
                            pushToast("Notice acknowledged", "success");
                            await loadNotices();
                          } finally {
                            setBusy(false);
                          }
                        }}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        {n.acknowledged ? "Acknowledged" : "Acknowledge Notice"}
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </AppShell>
    </AuthGuard>
  );
}
