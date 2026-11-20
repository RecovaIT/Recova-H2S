"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppSidebar } from "@/components/AppSidebar";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { AlertOctagon, Bell, Menu } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useLanguage } from "@/hooks/useLanguage";
import { useRealtimeEvents } from "@/hooks/useRealtimeEvents";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { careService } from "@/services/care";
import { engineService } from "@/services/engine";
import type { EmergencyEvent, NotificationItem } from "@/types/recova";
import { cn, formatDateTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

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
  const { session, hasPermission } = useAuth();
  const { isAr, t, tr } = useLanguage();
  const { pushToast } = useToast();

  const [mobileOpen, setMobileOpen] = useState(false);
  const [sidebarHovered, setSidebarHovered] = useState(false);
  const [sidebarFocused, setSidebarFocused] = useState(false);
  const collapsed = !sidebarHovered && !sidebarFocused;
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (!mobileOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [mobileOpen]);
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
    if (ev.type === "pipeline.emergency" || ev.type === "pipeline.emergency_bypass") {
      pushToast("Emergency Gate 2 Triggered", "error", "Routine pipeline bypassed — urgent triage required.");
      void loadShellAlerts();
    } else if (ev.type === "emergency.resolved" || ev.type === "referral.updated") {
      void loadShellAlerts();
    }
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

  return (
    <div className="flex min-h-dvh bg-[#f5f8fa]">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-white focus:p-3">Skip to content</a>
      <aside
        aria-label="Sidebar"
        onMouseEnter={() => setSidebarHovered(true)}
        onMouseLeave={() => setSidebarHovered(false)}
        onFocusCapture={() => setSidebarFocused(true)}
        onBlurCapture={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) setSidebarFocused(false);
        }}
        className={cn(
          "sticky top-0 hidden h-dvh shrink-0 border-e border-[#e8eff3] transition-[width] duration-300 ease-in-out md:block motion-reduce:transition-none",
          collapsed ? "w-[76px]" : "w-[248px]"
        )}
      >
        <AppSidebar collapsed={collapsed} connected={connected} />
      </aside>

      <AnimatePresence>
        {mobileOpen && (
          <div className="fixed inset-0 z-50 flex md:hidden">
            <motion.button
              type="button"
              aria-label="Close navigation"
              className="absolute inset-0 bg-slate-900/40 backdrop-blur-[2px]"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: reduceMotion ? 0 : 0.2 }}
              onClick={() => setMobileOpen(false)}
            />
            <motion.div
              role="dialog" aria-modal="true" aria-label="Navigation"
              className="relative h-full w-[min(280px,85vw)] shadow-xl"
              initial={{ x: isAr ? "100%" : "-100%" }} animate={{ x: 0 }} exit={{ x: isAr ? "100%" : "-100%" }}
              transition={{ duration: reduceMotion ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] }}
            >
              <AppSidebar connected={connected} onNavigate={() => setMobileOpen(false)} />
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        {openEmergencies.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-2 bg-red-600 px-4 py-2 text-xs font-medium text-white">
            <div className="flex items-center gap-2">
              <AlertOctagon className="h-4 w-4 shrink-0" />
              <span>
                {tr(
                  `ACTIVE EMERGENCY ESCALATION (${openEmergencies.length}): Gate 2 Red-Flag Bypass active. Immediate clinical triage required.`,
                  `تصعيد طوارئ نشط (${openEmergencies.length}): مسار الطوارئ (البوابة ٢) مفعّل. يلزم فرز سريري فوري.`
                )}
              </span>
            </div>
            <Link
              href="/agents"
              className="rounded bg-white px-2.5 py-1 text-xs font-semibold text-red-700 hover:bg-red-50"
            >
              {t("Open Emergency Console")}
            </Link>
          </div>
        )}

        <header className="sticky top-0 z-20 flex items-center justify-between flex-wrap gap-4 border-b border-[#e8eff3] bg-white/95 px-5 py-5 backdrop-blur-md lg:px-8">
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
              <h1 className="text-[22px] font-semibold tracking-tight text-slate-900 leading-tight">{t(title)}</h1>
              {subtitle && <p className="mt-1 max-w-2xl text-xs leading-relaxed text-slate-500">{t(subtitle)}</p>}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {actions}
            <LanguageSwitcher variant="inline" />
            {hasPermission("notifications:read") && (
              <div className="relative">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setNotifOpen((o) => !o)}
                  aria-label="Notifications"
                  aria-expanded={notifOpen}
                >
                  <Bell className="h-4 w-4" />
                  {unreadCount > 0 && (
                    <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">
                      {unreadCount}
                    </span>
                  )}
                </Button>
                {notifOpen && (
                  <div className="absolute end-0 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-2xl border border-slate-200 bg-white p-3 shadow-xl z-40">
                    <div className="mb-2 flex items-center justify-between border-b border-slate-100 pb-2">
                      <span className="text-xs font-semibold text-slate-900">{t("Notifications Inbox")}</span>
                      <button
                        type="button"
                        onClick={() => setNotifOpen(false)}
                        className="text-xs text-slate-500 hover:text-slate-900"
                      >
                        {t("Close")}
                      </button>
                    </div>
                    <div className="max-h-72 space-y-2 overflow-y-auto">
                      {notifications.length === 0 ? (
                        <p className="py-4 text-center text-xs text-slate-500">
                          {t("No notifications recorded yet.")}
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

        <main id="main-content" tabIndex={-1} className="recova-content flex-1 p-4 outline-none md:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
