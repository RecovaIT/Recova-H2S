"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  AlertOctagon,
  BarChart3,
  Bell,
  Brain,
  Building2,
  ClipboardCheck,
  FileBarChart2,
  GitBranch,
  HardHat,
  HeartPulse,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  Radio,
  Settings,
  Shield,
  Users,
  Workflow,
  X,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useRealtimeEvents } from "@/hooks/useRealtimeEvents";
import { careService } from "@/services/care";
import { engineService } from "@/services/engine";
import type { EmergencyEvent, NotificationItem } from "@/types/recova";
import { cn, formatDateTime, formatLabel } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  permission?: string;
  track?: string;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4" />, permission: "org:read" },
  { href: "/patients", label: "Participants", icon: <Users className="h-4 w-4" />, permission: "patients:read" },
  { href: "/core", label: "Recova Core", icon: <HeartPulse className="h-4 w-4" />, permission: "pipeline:read", track: "core" },
  { href: "/loop", label: "Recova Loop", icon: <Workflow className="h-4 w-4" />, permission: "pipeline:read", track: "loop" },
  { href: "/neuro", label: "Recova Neuro", icon: <Brain className="h-4 w-4" />, permission: "pipeline:read", track: "neuro" },
  { href: "/worksafe", label: "Recova WorkSafe", icon: <HardHat className="h-4 w-4" />, permission: "workforce:read_aggregate", track: "worksafe" },
  { href: "/agents", label: "Agent Monitoring", icon: <Radio className="h-4 w-4" />, permission: "pipeline:read" },
  { href: "/reviews", label: "Clinical Reviews", icon: <ClipboardCheck className="h-4 w-4" />, permission: "reviews:read" },
  { href: "/referrals", label: "Referrals & Care", icon: <GitBranch className="h-4 w-4" />, permission: "referrals:read" },
  { href: "/benchmarks", label: "Benchmarks", icon: <BarChart3 className="h-4 w-4" />, permission: "benchmarks:read" },
  { href: "/reports", label: "Reports", icon: <FileBarChart2 className="h-4 w-4" />, permission: "reports:read" },
  { href: "/settings", label: "Org & Integrations", icon: <Settings className="h-4 w-4" />, permission: "settings:read" },
  { href: "/admin", label: "Administration", icon: <Shield className="h-4 w-4" />, permission: "users:read" },
];

export function AppShell({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { session, logout, switchOrganization, hasPermission, hasTrack } = useAuth();
  const { pushToast } = useToast();

  const [mobileOpen, setMobileOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [openEmergencies, setOpenEmergencies] = useState<EmergencyEvent[]>([]);

  const loadShellAlerts = useCallback(async () => {
    if (!session) return;
    const tasks: Promise<void>[] = [];
    if (hasPermission("notifications:read")) {
      tasks.push(
        careService
          .listNotifications({ page: 1, page_size: 12 })
          .then((res) => setNotifications(res.items))
          .catch(() => undefined)
      );
    }
    if (hasPermission("pipeline:read")) {
      tasks.push(
        engineService
          .listEmergencies("open")
          .then((res) => setOpenEmergencies(res))
          .catch(() => undefined)
      );
    }
    await Promise.all(tasks);
  }, [session, hasPermission]);

  useEffect(() => {
    void loadShellAlerts();
  }, [loadShellAlerts]);

  const { connected } = useRealtimeEvents(Boolean(session && hasPermission("pipeline:read")), (ev) => {
    if (ev.type === "pipeline.emergency") {
      pushToast("Emergency Gate 2 Triggered", "error", "Routine pipeline bypassed — urgent triage required.");
      void loadShellAlerts();
    } else if (ev.type === "emergency.resolved" || ev.type === "referral.updated") {
      void loadShellAlerts();
    }
  });

  const visibleNav = NAV_ITEMS.filter((item) => {
    if (item.permission && !hasPermission(item.permission)) return false;
    if (item.track && !hasTrack(item.track)) return false;
    return true;
  });

  const unreadCount = notifications.filter((n) => !n.read_at).length;

  const handleMarkRead = async (id: string) => {
    try {
      const updated = await careService.markNotificationRead(id);
      setNotifications((prev) => prev.map((n) => (n.id === id ? updated : n)));
    } catch {
      // Ignore transient error
    }
  };

  const handleOrgChange = async (orgId: string) => {
    try {
      await switchOrganization(orgId);
      pushToast("Switched active organisation", "success");
      router.refresh();
    } catch (err) {
      pushToast("Could not switch organisation", "error", err instanceof Error ? err.message : undefined);
    }
  };

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  const sidebarContent = (
    <div className="flex h-full flex-col bg-slate-900 text-slate-100">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-4">
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-600 text-white shadow-xs">
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-tight text-white">RECOVA</div>
            <div className="text-[10px] font-medium uppercase tracking-wider text-teal-300">
              Anticipatory Health
            </div>
          </div>
        </Link>
        <button
          type="button"
          onClick={() => setMobileOpen(false)}
          className="rounded p-1 text-slate-400 hover:bg-slate-800 md:hidden"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {session && session.memberships.length > 0 && (
        <div className="border-b border-slate-800 px-3 py-3">
          <div className="mb-1 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            <span className="flex items-center gap-1.5">
              <Building2 className="h-3 w-3" /> Organisation
            </span>
            {hasPermission("platform:admin") && (
              <Link
                href="/admin?tab=orgs"
                className="flex items-center gap-0.5 font-medium text-teal-400 hover:text-teal-300"
                title="Add or manage organisations"
              >
                <Plus className="h-3 w-3" /> Add
              </Link>
            )}
          </div>
          {session.memberships.length > 1 ? (
            <Select
              value={session.active_organization?.id || ""}
              onChange={(e) => void handleOrgChange(e.target.value)}
              className="h-8 border-slate-700 bg-slate-800 text-xs text-slate-100"
            >
              {session.memberships.map((m) => (
                <option key={m.id} value={m.organization_id}>
                  {m.organization_name || m.organization_slug || m.organization_id}
                </option>
              ))}
            </Select>
          ) : (
            <div className="truncate rounded-md bg-slate-800/80 px-2.5 py-1.5 text-xs font-medium text-slate-200">
              {session.active_organization?.name || "Platform Scope"}
            </div>
          )}
        </div>
      )}

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-2.5 py-3">
        {visibleNav.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors",
                active
                  ? "bg-teal-600/20 text-teal-200 ring-1 ring-teal-500/30"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              )}
            >
              {item.icon}
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-800 p-3 text-xs">
        <div className="mb-2 flex items-center justify-between text-[11px] text-slate-400">
          <span className="flex items-center gap-1.5">
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                connected ? "bg-emerald-400" : "bg-slate-500"
              )}
            />
            {connected ? "SSE Live Stream" : "Stream Standby"}
          </span>
        </div>
        <div className="rounded-lg bg-slate-800/80 p-2.5">
          <div className="truncate font-medium text-white">{session?.user.full_name}</div>
          <div className="truncate text-[11px] text-slate-400">
            {formatLabel(session?.role)}
            {session?.user.license_number ? ` · ${session.user.license_number}` : ""}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void handleLogout()}
            className="mt-2 w-full justify-start text-slate-300 hover:bg-slate-700 hover:text-white px-2"
          >
            <LogOut className="h-3.5 w-3.5" /> Sign Out
          </Button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="hidden w-64 shrink-0 md:block">{sidebarContent}</aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div className="w-64">{sidebarContent}</div>
          <div className="flex-1 bg-slate-900/50" onClick={() => setMobileOpen(false)} />
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {openEmergencies.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-2 bg-red-600 px-4 py-2 text-xs font-medium text-white">
            <div className="flex items-center gap-2">
              <AlertOctagon className="h-4 w-4 shrink-0" />
              <span>
                ACTIVE EMERGENCY ESCALATION ({openEmergencies.length}): Gate 2 Red-Flag Bypass active. Immediate clinical triage required.
              </span>
            </div>
            <Link
              href="/agents"
              className="rounded bg-white px-2.5 py-1 text-xs font-semibold text-red-700 hover:bg-red-50"
            >
              Open Emergency Console
            </Link>
          </div>
        )}

        <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur-xs md:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="rounded-lg border border-slate-200 p-1.5 text-slate-700 md:hidden"
              aria-label="Open menu"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div>
              <h1 className="text-lg font-semibold text-slate-900 leading-tight">{title}</h1>
              {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {actions}
            {hasPermission("notifications:read") && (
              <div className="relative">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setNotifOpen((o) => !o)}
                  aria-label="Notifications"
                >
                  <Bell className="h-4 w-4" />
                  {unreadCount > 0 && (
                    <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">
                      {unreadCount}
                    </span>
                  )}
                </Button>
                {notifOpen && (
                  <div className="absolute right-0 mt-2 w-80 rounded-xl border border-slate-200 bg-white p-3 shadow-xl z-40">
                    <div className="mb-2 flex items-center justify-between border-b border-slate-100 pb-2">
                      <span className="text-xs font-semibold text-slate-900">Notifications Inbox</span>
                      <button
                        type="button"
                        onClick={() => setNotifOpen(false)}
                        className="text-xs text-slate-500 hover:text-slate-900"
                      >
                        Close
                      </button>
                    </div>
                    <div className="max-h-72 space-y-2 overflow-y-auto">
                      {notifications.length === 0 ? (
                        <p className="py-4 text-center text-xs text-slate-500">
                          No notifications recorded yet.
                        </p>
                      ) : (
                        notifications.map((n) => (
                          <div
                            key={n.id}
                            className={cn(
                              "rounded-lg border p-2 text-xs",
                              n.read_at
                                ? "border-slate-100 bg-slate-50 text-slate-600"
                                : "border-teal-200 bg-teal-50/40 text-slate-900"
                            )}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-semibold">{n.subject}</span>
                              <span className="text-[10px] uppercase text-slate-500">{n.status}</span>
                            </div>
                            <p className="mt-0.5 text-[11px] opacity-90">{n.body}</p>
                            <div className="mt-1 flex items-center justify-between text-[10px] text-slate-500">
                              <span>{formatDateTime(n.created_at)}</span>
                              {!n.read_at && (
                                <button
                                  type="button"
                                  onClick={() => void handleMarkRead(n.id)}
                                  className="font-medium text-teal-700 hover:underline"
                                >
                                  Mark read
                                </button>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </header>

        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
