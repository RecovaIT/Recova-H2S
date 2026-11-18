"use client";

import React, { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Megaphone, Send, ShieldAlert, XCircle } from "lucide-react";
import { api } from "@/lib/api";
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

interface AuthorityNotice {
  id: string;
  title: string;
  message: string;
  plain_language_action?: string | null;
  issuer: string;
  category: string;
  severity: "info" | "advisory" | "urgent";
  scope_emirate?: string | null;
  eligible_programmes: string[];
  acknowledgement_required: boolean;
  status: "draft" | "published" | "expired" | "withdrawn";
  version: number;
  published_at?: string | null;
  expires_at?: string | null;
  acknowledgement_count: number;
}

export default function AuthorityPage() {
  const { pushToast } = useToast();
  const [notices, setNotices] = useState<AuthorityNotice[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [actionText, setActionText] = useState("");
  const [severity, setSeverity] = useState<"info" | "advisory" | "urgent">("advisory");
  const [scopeEmirate, setScopeEmirate] = useState("");
  const [programmes, setProgrammes] = useState<string[]>(["core", "loop", "neuro", "worksafe"]);

  const loadNotices = useCallback(async () => {
    try {
      const list = await api.get<AuthorityNotice[]>("/authority/notices");
      setNotices(list);
    } catch {
      setNotices([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadNotices();
  }, [loadNotices]);

  const toggleProgramme = (prog: string) => {
    setProgrammes((prev) => (prev.includes(prog) ? prev.filter((p) => p !== prog) : [...prev, prog]));
  };

  const handleCreateDraft = async (e: React.FormEvent) => {
    e.preventDefault();
    if (programmes.length === 0) {
      pushToast("Select at least one eligible programme", "error");
      return;
    }
    setBusy(true);
    try {
      await api.post("/authority/notices", {
        title,
        message,
        plain_language_action: actionText || undefined,
        severity,
        scope_emirate: scopeEmirate || undefined,
        eligible_programmes: programmes,
        acknowledgement_required: true,
      });
      setTitle("");
      setMessage("");
      setActionText("");
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
      await api.post(`/authority/notices/${id}/publish`);
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
      await api.post(`/authority/notices/${id}/withdraw`);
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
        subtitle="Shared public-health notice drafting, scoped publishing, and audited acknowledgement tracking across all Recova programmes."
      >
        <div className="space-y-6">
          <Alert variant="info">
            Shared population-health coordination is provisioned for every organisation independently of Recova Loop. Out-of-scope recipients cannot retrieve scoped notices.
          </Alert>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Megaphone className="h-4 w-4 text-[#003e5e]" />
                  Draft Scoped Public-Health Notice
                </CardTitle>
                <CardDescription>Create a draft, verify scope, and publish with versioned audit logging.</CardDescription>
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
                        placeholder="All Emirates or e.g. Abu Dhabi"
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
                  <Button type="submit" disabled={busy}>
                    Save Draft Notice
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Published &amp; Draft Notices ({notices.length})</CardTitle>
                <CardDescription>Audited delivery and authenticated acknowledgement counts</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {loading ? (
                  <div className="h-24 animate-pulse rounded-xl bg-slate-100" />
                ) : notices.length === 0 ? (
                  <EmptyState
                    icon={<ShieldAlert className="h-5 w-5" />}
                    title="No notices yet"
                    description="Create a draft public-health notice to publish across eligible programmes."
                  />
                ) : (
                  notices.map((n) => (
                    <div key={n.id} className="rounded-xl border border-[#e2edf2] bg-[#f8fbfc] p-3.5 text-xs">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <strong className="text-sm text-[#011621]">{n.title}</strong>
                        <div className="flex items-center gap-1.5">
                          <Badge variant="outline">{n.severity}</Badge>
                          <Badge variant="outline">{n.status}</Badge>
                        </div>
                      </div>
                      <p className="mt-1.5 text-[#2a4558]">{n.message}</p>
                      <p className="mt-2 text-[11px] text-[#5a7d93]">
                        Scope: {n.scope_emirate || "All Emirates"} · Programmes: {n.eligible_programmes.join(", ")} ·{" "}
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
        </div>
      </AppShell>
    </AuthGuard>
  );
}
