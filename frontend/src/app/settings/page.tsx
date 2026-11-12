"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Building2, Plug, Shield } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { opsService } from "@/services/ops";
import type {
  CareFacility,
  InsurancePlan,
  IntegrationConfig,
  ReferralPathway,
} from "@/types/recova";
import { formatDateTime, formatLabel } from "@/lib/utils";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { StatusBadge } from "@/components/RiskBadge";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";

export default function SettingsPage() {
  const { hasPermission } = useAuth();
  const { pushToast } = useToast();
  const canManage = hasPermission("settings:manage");

  const [tab, setTab] = useState("integrations");
  const [integrations, setIntegrations] = useState<IntegrationConfig[]>([]);
  const [plans, setPlans] = useState<InsurancePlan[]>([]);
  const [facilities, setFacilities] = useState<CareFacility[]>([]);
  const [busy, setBusy] = useState(false);

  // LLM config state
  const [llmProvider, setLlmProvider] = useState("openai");
  const [llmModel, setLlmModel] = useState("gpt-4o-mini");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmEnabled, setLlmEnabled] = useState(true);

  // Insurance plan create
  const [planCode, setPlanCode] = useState("");
  const [planName, setPlanName] = useState("");
  const [planPayer, setPlanPayer] = useState("Daman / Thiqa");
  const [planPreauth, setPlanPreauth] = useState(false);

  // Care facility create
  const [facName, setFacName] = useState("");
  const [facType, setFacType] = useState<
    "primary_care" | "specialist" | "teleconsult" | "rehab" | "emergency" | "occupational_health" | "therapist"
  >("specialist");
  const [facPathway, setFacPathway] = useState<ReferralPathway>("specialist");
  const [facWaitDays, setFacWaitDays] = useState("3");
  const [facPlanId, setFacPlanId] = useState("");

  const loadSettings = useCallback(async () => {
    const [intList, pList, fList] = await Promise.all([
      opsService.listIntegrations(),
      opsService.listInsurancePlans(),
      opsService.listCareFacilities(),
    ]);
    setIntegrations(intList);
    setPlans(pList);
    setFacilities(fList);
    const llm = intList.find((x) => x.integration === "llm");
    if (llm?.settings) {
      if (typeof llm.settings.provider === "string") setLlmProvider(llm.settings.provider);
      if (typeof llm.settings.model === "string") setLlmModel(llm.settings.model);
      if (typeof llm.settings.base_url === "string") setLlmBaseUrl(llm.settings.base_url);
      setLlmEnabled(llm.enabled);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadSettings();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadSettings]);

  const handleSaveLlm = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await opsService.upsertIntegration("llm", {
        enabled: llmEnabled,
        settings: {
          provider: llmProvider,
          model: llmModel.trim(),
          base_url: llmBaseUrl.trim() || undefined,
        },
        secrets: llmApiKey.trim() ? { api_key: llmApiKey.trim() } : undefined,
      });
      setLlmApiKey("");
      pushToast("LLM provider settings saved encrypted", "success");
      await loadSettings();
    } catch (err) {
      pushToast("Save failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleTestIntegration = async (name: string) => {
    setBusy(true);
    try {
      const res = await opsService.testIntegration(name);
      pushToast(`${name.toUpperCase()} test: ${String(res.status)}`, res.connected ? "success" : "info", String(res.message || ""));
      await loadSettings();
    } catch (err) {
      pushToast("Connection test failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleCreatePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await opsService.createInsurancePlan({
        code: planCode.trim().toUpperCase(),
        name: planName.trim(),
        payer_name: planPayer.trim() || undefined,
        covered_pathways: [
          "primary_care",
          "specialist",
          "async_teleconsult",
          "outpatient_therapist",
          "emergency_triage",
        ],
        requires_preauthorization: planPreauth,
      });
      setPlanCode("");
      setPlanName("");
      pushToast("Insurance plan created", "success");
      await loadSettings();
    } catch (err) {
      pushToast("Create plan failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleCreateFacility = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await opsService.createCareFacility({
        name: facName.trim(),
        facility_type: facType,
        pathways: [facPathway],
        specialties: [facType],
        accepted_plan_ids: facPlanId ? [facPlanId] : [],
        typical_wait_days: Number(facWaitDays),
      });
      setFacName("");
      pushToast("Care facility added to Agent 6 routing table", "success");
      await loadSettings();
    } catch (err) {
      pushToast("Create facility failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthGuard requiredPermission="settings:read">
      <AppShell
        title="Organisation Settings &amp; Integrations"
        subtitle="Encrypted external provider configuration (LLM, Malaffi HIE, Sahatna, SMTP, Twilio) &amp; insurance network routing."
      >
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="integrations">External Integrations ({integrations.length})</TabsTrigger>
            <TabsTrigger value="network">Insurance Plans &amp; Care Facilities</TabsTrigger>
          </TabsList>

          <TabsContent value="integrations" className="space-y-4">
            <Alert variant="info">
              API secrets are encrypted at rest via Fernet and never echoed back. Unconfigured providers honestly report <code>not_configured</code> rather than faking external calls.
            </Alert>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {canManage && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Plug className="h-4 w-4 text-teal-700" />
                      Agent 5 — Clinical Synthesis LLM Provider
                    </CardTitle>
                    <CardDescription>
                      Configure OpenAI, Azure OpenAI, Anthropic Claude, or Google Gemini.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <form onSubmit={handleSaveLlm} className="space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <Label>Provider</Label>
                          <Select value={llmProvider} onChange={(e) => setLlmProvider(e.target.value)}>
                            <option value="openai">OpenAI</option>
                            <option value="azure_openai">Azure OpenAI</option>
                            <option value="anthropic">Anthropic Claude</option>
                            <option value="gemini">Google Gemini</option>
                            <option value="none">Disabled</option>
                          </Select>
                        </div>
                        <div className="space-y-1">
                          <Label>Model</Label>
                          <Input value={llmModel} onChange={(e) => setLlmModel(e.target.value)} />
                        </div>
                      </div>
                      <div className="space-y-1">
                        <Label>Custom Endpoint / Base URL (Optional)</Label>
                        <Input value={llmBaseUrl} onChange={(e) => setLlmBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" />
                      </div>
                      <div className="space-y-1">
                        <Label>API Key (leave blank to keep existing secret)</Label>
                        <Input type="password" value={llmApiKey} onChange={(e) => setLlmApiKey(e.target.value)} placeholder="sk-..." />
                      </div>
                      <label className="flex items-center gap-2 text-xs cursor-pointer">
                        <input type="checkbox" checked={llmEnabled} onChange={(e) => setLlmEnabled(e.target.checked)} />
                        Enable Agent 5 synthesis for consented patients
                      </label>
                      <Button type="submit" disabled={busy}>Save LLM Integration</Button>
                    </form>
                  </CardContent>
                </Card>
              )}

              <Card>
                <CardHeader>
                  <CardTitle>Adapter Health &amp; Verification Status</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2.5">
                  {integrations.map((cfg) => (
                    <div
                      key={cfg.integration}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3 text-xs"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold uppercase">{cfg.integration}</span>
                          <StatusBadge status={cfg.status} />
                          {cfg.has_secrets && <Badge variant="outline">Secret stored</Badge>}
                        </div>
                        <div className="mt-1 text-[11px] text-slate-500">
                          Last tested: {formatDateTime(cfg.last_tested_at)}
                        </div>
                      </div>
                      {canManage && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() => void handleTestIntegration(cfg.integration)}
                        >
                          Test Connection
                        </Button>
                      )}
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="network" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-indigo-700" />
                  Insurance Plans ({plans.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {canManage && (
                  <form onSubmit={handleCreatePlan} className="space-y-2.5 border-b border-slate-100 pb-4">
                    <div className="grid grid-cols-2 gap-2">
                      <Input required value={planCode} onChange={(e) => setPlanCode(e.target.value)} placeholder="Code (THIQA)" />
                      <Input required value={planName} onChange={(e) => setPlanName(e.target.value)} placeholder="Plan Name" />
                    </div>
                    <Input value={planPayer} onChange={(e) => setPlanPayer(e.target.value)} placeholder="Payer Name" />
                    <label className="flex items-center gap-2 text-xs">
                      <input type="checkbox" checked={planPreauth} onChange={(e) => setPlanPreauth(e.target.checked)} />
                      Requires Pre-authorization
                    </label>
                    <Button type="submit" size="sm" disabled={busy}>Add Insurance Plan</Button>
                  </form>
                )}
                <div className="space-y-2 text-xs">
                  {plans.map((p) => (
                    <div key={p.id} className="flex items-center justify-between rounded border border-slate-100 bg-slate-50 p-2.5">
                      <div>
                        <strong>{p.name}</strong> ({p.code})
                        <div className="text-[11px] text-slate-500">{p.payer_name || "Standard payer"}</div>
                      </div>
                      <Badge variant="outline">{p.requires_preauthorization ? "Pre-auth" : "Direct"}</Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-teal-700" />
                  Care Facilities ({facilities.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {canManage && (
                  <form onSubmit={handleCreateFacility} className="space-y-2.5 border-b border-slate-100 pb-4">
                    <Input required value={facName} onChange={(e) => setFacName(e.target.value)} placeholder="Facility Name (e.g. Cleveland Clinic Abu Dhabi)" />
                    <div className="grid grid-cols-2 gap-2">
                      <Select value={facType} onChange={(e) => setFacType(e.target.value as typeof facType)}>
                        <option value="primary_care">Primary Care</option>
                        <option value="specialist">Specialist</option>
                        <option value="teleconsult">Teleconsult</option>
                        <option value="rehab">Rehab Center</option>
                        <option value="therapist">Outpatient Therapist</option>
                        <option value="occupational_health">Occupational Health</option>
                        <option value="emergency">Emergency Dept</option>
                      </Select>
                      <Select value={facPathway} onChange={(e) => setFacPathway(e.target.value as ReferralPathway)}>
                        <option value="specialist">Specialist</option>
                        <option value="primary_care">Primary Care</option>
                        <option value="async_teleconsult">Async Teleconsult</option>
                        <option value="outpatient_therapist">Outpatient Therapist</option>
                        <option value="occupational_health">Occupational Health</option>
                        <option value="emergency_triage">Emergency Triage</option>
                      </Select>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <Select value={facPlanId} onChange={(e) => setFacPlanId(e.target.value)}>
                        <option value="">Accepts all / self-pay</option>
                        {plans.map((p) => (
                          <option key={p.id} value={p.id}>Accepts {p.code}</option>
                        ))}
                      </Select>
                      <Input type="number" min={0} value={facWaitDays} onChange={(e) => setFacWaitDays(e.target.value)} placeholder="Wait days" />
                    </div>
                    <Button type="submit" size="sm" disabled={busy}>Add Care Facility</Button>
                  </form>
                )}
                <div className="space-y-2 text-xs">
                  {facilities.map((f) => (
                    <div key={f.id} className="flex items-center justify-between rounded border border-slate-100 bg-slate-50 p-2.5">
                      <div>
                        <strong>{f.name}</strong>
                        <div className="text-[11px] text-slate-500">
                          {formatLabel(f.facility_type)} · Pathways: {f.pathways.join(", ")}
                        </div>
                      </div>
                      <Badge variant="outline">{f.typical_wait_days ?? "—"}d wait</Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </AppShell>
    </AuthGuard>
  );
}
