"use client";

import React, { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, Shield, Users } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { opsService } from "@/services/ops";
import type {
  AuditEvent,
  JobRecord,
  Organization,
  RolePermissionView,
  Track,
  UserWithMemberships,
} from "@/types/recova";
import { formatDateTime, formatLabel } from "@/lib/utils";
import { AppShell } from "@/components/AppShell";
import { AuthGuard } from "@/components/AuthGuard";
import { StatusBadge } from "@/components/RiskBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";

const ADMIN_TABS = new Set(["users", "rbac", "orgs", "audit", "jobs"]);

function AdminPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { session, hasPermission, refreshSession, switchOrganization } = useAuth();
  const { pushToast } = useToast();

  const requestedTab = searchParams.get("tab");
  const canViewAudit = hasPermission("audit:read");
  const tab =
    requestedTab &&
    ADMIN_TABS.has(requestedTab) &&
    (canViewAudit || (requestedTab !== "audit" && requestedTab !== "jobs"))
      ? requestedTab
      : "users";

  const handleTabChange = (next: string) => {
    router.replace(`/admin?tab=${next}`, { scroll: false });
  };
  const [users, setUsers] = useState<UserWithMemberships[]>([]);
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [roles, setRoles] = useState<RolePermissionView[]>([]);
  const [permCatalog, setPermCatalog] = useState<string[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditEvent[]>([]);
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [busy, setBusy] = useState(false);

  // New user form
  const [uEmail, setUEmail] = useState("");
  const [uName, setUName] = useState("");
  const [uRole, setURole] = useState("clinician");
  const [uPassword, setUPassword] = useState("");
  const [uLicense, setULicense] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // Role permission override form
  const [ovRole, setOvRole] = useState("supervisor");
  const [ovPerm, setOvPerm] = useState("workforce:read_identifiable");
  const [ovEffect, setOvEffect] = useState<"grant" | "revoke">("grant");

  // New organisation form
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [orgType, setOrgType] = useState("hospital");

  const loadAdmin = useCallback(async () => {
    const [uList, oList, rList, catRes] = await Promise.all([
      hasPermission("users:read") ? opsService.listUsers() : Promise.resolve([]),
      opsService.listOrganizations(),
      hasPermission("org:read") ? opsService.listRolePermissions() : Promise.resolve([]),
      hasPermission("org:read") ? opsService.getPermissionsCatalog() : Promise.resolve({ permissions: [] }),
    ]);
    setUsers(uList);
    setOrgs(oList);
    setRoles(rList);
    setPermCatalog(catRes.permissions);
    if (hasPermission("audit:read")) {
      const [aPage, jPage] = await Promise.all([
        opsService.listAuditLogs({ page: 1, page_size: 40 }),
        opsService.listJobs({ page: 1, page_size: 40 }),
      ]);
      setAuditLogs(aPage.items);
      setJobs(jPage.items);
    }
  }, [hasPermission]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadAdmin();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadAdmin]);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await opsService.createUser({
        email: uEmail.trim(),
        full_name: uName.trim(),
        role: uRole,
        password: uPassword,
        license_number: uLicense.trim() || undefined,
      });
      setUEmail("");
      setUName("");
      setUPassword("");
      setULicense("");
      pushToast("User added to active organisation", "success");
      await loadAdmin();
    } catch (err) {
      pushToast("Failed to create user", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const toggleUserActive = async (u: UserWithMemberships) => {
    try {
      await opsService.updateUser(u.id, { is_active: !u.is_active });
      pushToast(u.is_active ? "User deactivated" : "User activated", "info");
      await loadAdmin();
    } catch (err) {
      pushToast("Update failed", "error", err instanceof Error ? err.message : undefined);
    }
  };

  const handleSaveOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await opsService.setRoleOverride({ role: ovRole, permission: ovPerm, effect: ovEffect });
      pushToast(`RBAC override saved (${ovEffect} ${ovPerm} on ${ovRole})`, "success");
      await loadAdmin();
    } catch (err) {
      pushToast("Override failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const derivedSlug =
        (
          orgSlug.trim() ||
          orgName
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-|-$/g, "")
        ) || `tenant-${Math.floor(Math.random() * 10000)}`;

      await opsService.createOrganization({
        name: orgName.trim(),
        slug: derivedSlug,
        org_type: orgType,
        enabled_tracks: ["core", "loop", "neuro", "worksafe"] as Track[],
      });
      setOrgName("");
      setOrgSlug("");
      pushToast("Tenant organisation provisioned", "success");
      await refreshSession();
      await loadAdmin();
    } catch (err) {
      pushToast("Organisation creation failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  const handleSwitchOrg = async (orgId: string) => {
    setBusy(true);
    try {
      await switchOrganization(orgId);
      pushToast("Active organisation switched", "success");
      await loadAdmin();
    } catch (err) {
      pushToast("Organisation switch failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell
      title="Platform Administration &amp; Governance"
      subtitle="Users, Multi-Tenant Organisations, Dynamic RBAC Permission Overrides, Audit Logs, and Job Queue."
    >
      <Tabs value={tab} onValueChange={handleTabChange}>
          <TabsList>
            <TabsTrigger value="users">Users ({users.length})</TabsTrigger>
            <TabsTrigger value="rbac">RBAC Roles ({roles.length})</TabsTrigger>
            <TabsTrigger value="orgs">Organisations ({orgs.length})</TabsTrigger>
            {hasPermission("audit:read") && (
              <>
                <TabsTrigger value="audit">Audit Logs ({auditLogs.length})</TabsTrigger>
                <TabsTrigger value="jobs">Background Jobs ({jobs.length})</TabsTrigger>
              </>
            )}
          </TabsList>

          <TabsContent value="users" className="space-y-4">
            {hasPermission("users:manage") && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-teal-700" />
                    Provision Staff / Clinician Account
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleCreateUser} className="grid grid-cols-1 gap-3 sm:grid-cols-6 items-end">
                    <div className="space-y-1 sm:col-span-2">
                      <Label>Full Name</Label>
                      <Input required value={uName} onChange={(e) => setUName(e.target.value)} />
                    </div>
                    <div className="space-y-1 sm:col-span-2">
                      <Label>Email</Label>
                      <Input type="email" required value={uEmail} onChange={(e) => setUEmail(e.target.value)} />
                    </div>
                    <div className="space-y-1">
                      <Label>Role</Label>
                      <Select value={uRole} onChange={(e) => setURole(e.target.value)}>
                        <option value="clinician">Clinician</option>
                        <option value="psychiatrist">Psychiatrist</option>
                        <option value="care_coordinator">Care Coordinator</option>
                        <option value="screening_coordinator">Screening Coordinator</option>
                        <option value="occ_health_director">Occ Health Director</option>
                        <option value="supervisor">Supervisor</option>
                        <option value="org_admin">Org Admin</option>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label>License (Optional)</Label>
                      <Input value={uLicense} onChange={(e) => setULicense(e.target.value)} />
                    </div>
                    <div className="space-y-1 sm:col-span-4">
                      <Label htmlFor="admin-user-password">Initial Password (min 10 chars)</Label>
                      <div className="relative">
                        <Input
                          id="admin-user-password"
                          type={showPassword ? "text" : "password"}
                          required
                          minLength={10}
                          value={uPassword}
                          onChange={(e) => setUPassword(e.target.value)}
                          className="pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword((prev) => !prev)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 focus:outline-none"
                          aria-label={showPassword ? "Hide input" : "Reveal input"}
                        >
                          {showPassword ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </button>
                      </div>
                    </div>
                    <Button type="submit" disabled={busy} className="sm:col-span-2">Create User</Button>
                  </form>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardContent className="pt-5">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Memberships / Roles</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((u) => (
                      <TableRow key={u.id}>
                        <TableCell className="text-xs font-semibold">{u.full_name}</TableCell>
                        <TableCell className="text-xs">{u.email}</TableCell>
                        <TableCell className="text-xs">
                          {u.memberships.map((m) => (
                            <Badge key={m.id} variant="outline" className="mr-1">
                              {formatLabel(m.role)}
                            </Badge>
                          ))}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={u.is_active ? "completed" : "rejected"} />
                        </TableCell>
                        <TableCell className="text-right">
                          {hasPermission("users:manage") && (
                            <Button size="sm" variant="outline" onClick={() => void toggleUserActive(u)}>
                              {u.is_active ? "Deactivate" : "Reactivate"}
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="rbac" className="space-y-4">
            {hasPermission("org:manage") && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Shield className="h-4 w-4 text-teal-700" />
                    Organisation RBAC Permission Override
                  </CardTitle>
                  <CardDescription>
                    Grant or revoke permissions per role dynamically enforced by FastAPI dependencies.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleSaveOverride} className="flex flex-wrap items-end gap-3">
                    <div className="w-48 space-y-1">
                      <Label>Role</Label>
                      <Select value={ovRole} onChange={(e) => setOvRole(e.target.value)}>
                        {roles.map((r) => (
                          <option key={r.role} value={r.role}>{formatLabel(r.role)}</option>
                        ))}
                      </Select>
                    </div>
                    <div className="w-64 space-y-1">
                      <Label>Permission</Label>
                      <Select value={ovPerm} onChange={(e) => setOvPerm(e.target.value)}>
                        {permCatalog.map((p) => (
                          <option key={p} value={p}>{p}</option>
                        ))}
                      </Select>
                    </div>
                    <div className="w-32 space-y-1">
                      <Label>Effect</Label>
                      <Select value={ovEffect} onChange={(e) => setOvEffect(e.target.value as "grant" | "revoke")}>
                        <option value="grant">Grant</option>
                        <option value="revoke">Revoke</option>
                      </Select>
                    </div>
                    <Button type="submit" disabled={busy}>Apply Override</Button>
                  </form>
                </CardContent>
              </Card>
            )}

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {roles.map((r) => (
                <Card key={r.role}>
                  <CardHeader>
                    <CardTitle className="text-sm">{formatLabel(r.role)}</CardTitle>
                    <CardDescription>{r.effective_permissions.length} effective permissions</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-wrap gap-1">
                    {r.effective_permissions.map((p) => (
                      <Badge key={p} variant="secondary" className="text-[10px] font-mono">
                        {p}
                      </Badge>
                    ))}
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="orgs" className="space-y-4">
            {hasPermission("platform:admin") && (
              <Card>
                <CardHeader>
                  <CardTitle>Create Tenant Organisation</CardTitle>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleCreateOrg} className="flex flex-wrap items-end gap-3">
                    <Input required value={orgName} onChange={(e) => setOrgName(e.target.value)} placeholder="Organisation Name" className="w-64" />
                    <Input pattern="[a-z0-9-]*" value={orgSlug} onChange={(e) => setOrgSlug(e.target.value)} placeholder="slug (optional)" className="w-44" />
                    <Select value={orgType} onChange={(e) => setOrgType(e.target.value)} className="w-40">
                      <option value="hospital">Hospital</option>
                      <option value="clinic">Clinic</option>
                      <option value="employer">Employer</option>
                      <option value="rehab_center">Rehab Center</option>
                    </Select>
                    <Button type="submit" disabled={busy}>Provision Org</Button>
                  </form>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardContent className="pt-5">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Slug</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Tracks</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {orgs.map((o) => {
                      const isActive = o.id === session?.active_organization?.id;
                      const isMember = session?.memberships.some((m) => m.organization_id === o.id);
                      return (
                        <TableRow key={o.id}>
                          <TableCell className="text-xs font-semibold">{o.name}</TableCell>
                          <TableCell className="font-mono text-xs">{o.slug}</TableCell>
                          <TableCell className="text-xs">{formatLabel(o.org_type)}</TableCell>
                          <TableCell className="text-xs uppercase">{o.enabled_tracks.join(", ")}</TableCell>
                          <TableCell className="text-right">
                            {isActive ? (
                              <Badge variant="outline">Active</Badge>
                            ) : isMember ? (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={busy}
                                onClick={() => void handleSwitchOrg(o.id)}
                              >
                                Switch
                              </Button>
                            ) : (
                              <span className="text-[11px] text-slate-400">No membership</span>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="audit">
            <Card>
              <CardContent className="pt-5">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Timestamp</TableHead>
                      <TableHead>Actor</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>Resource</TableHead>
                      <TableHead>Outcome</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {auditLogs.map((a) => (
                      <TableRow key={a.id}>
                        <TableCell className="text-xs text-slate-500">{formatDateTime(a.occurred_at)}</TableCell>
                        <TableCell className="text-xs">{a.actor_label}</TableCell>
                        <TableCell className="font-mono text-xs">{a.action}</TableCell>
                        <TableCell className="text-xs">{a.resource_type}</TableCell>
                        <TableCell><StatusBadge status={a.outcome === "success" ? "completed" : "failed"} /></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="jobs">
            <Card>
              <CardContent className="pt-5">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Job Type</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Attempts</TableHead>
                      <TableHead>Created</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {jobs.map((j) => (
                      <TableRow key={j.id}>
                        <TableCell className="font-mono text-xs">{j.job_type}</TableCell>
                        <TableCell><StatusBadge status={j.status} /></TableCell>
                        <TableCell className="text-xs tabular-nums">{j.attempts} / {j.max_attempts}</TableCell>
                        <TableCell className="text-xs text-slate-500">{formatDateTime(j.created_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </AppShell>
  );
}

export default function AdminPage() {
  return (
    <AuthGuard requiredPermission="users:read">
      <Suspense
        fallback={
          <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-600">
            Loading administration workspace...
          </div>
        }
      >
        <AdminPageContent />
      </Suspense>
    </AuthGuard>
  );
}
