"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  BarChart3,
  Brain,
  Building2,
  ChevronDown,
  ClipboardCheck,
  FileBarChart2,
  GitBranch,
  HardHat,
  HeartPulse,
  LayoutDashboard,
  LogOut,
  Radio,
  Search,
  Settings,
  Shield,
  Users,
  Workflow,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/ui/toast";
import { RecovaMark } from "@/components/RecovaMark";
import { cn, formatLabel } from "@/lib/utils";

type NavigationItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  permission: string;
  track?: string;
};

const NAVIGATION_GROUPS = [
  {
    id: "overview",
    label: "Overview",
    icon: LayoutDashboard,
    items: [
      {
        href: "/dashboard",
        label: "Dashboard",
        icon: LayoutDashboard,
        permission: "org:read",
      },
      {
        href: "/reports",
        label: "Reports",
        icon: FileBarChart2,
        permission: "reports:read",
      },
    ],
  },
  {
    id: "care",
    label: "Care management",
    icon: Users,
    items: [
      {
        href: "/patients",
        label: "Participants",
        icon: Users,
        permission: "patients:read",
      },
      {
        href: "/core",
        label: "Recova Core",
        icon: HeartPulse,
        permission: "pipeline:read",
        track: "core",
      },
      {
        href: "/loop",
        label: "Recova Loop",
        icon: Workflow,
        permission: "pipeline:read",
        track: "loop",
      },
      {
        href: "/neuro",
        label: "Recova Neuro",
        icon: Brain,
        permission: "pipeline:read",
        track: "neuro",
      },
      {
        href: "/worksafe",
        label: "Recova WorkSafe",
        icon: HardHat,
        permission: "workforce:read_aggregate",
        track: "worksafe",
      },
      {
        href: "/reviews",
        label: "Clinical reviews",
        icon: ClipboardCheck,
        permission: "reviews:read",
      },
      {
        href: "/referrals",
        label: "Referrals & care",
        icon: GitBranch,
        permission: "referrals:read",
      },
      {
        href: "/authority",
        label: "Public-health notices",
        icon: Radio,
        permission: "org:read",
      },
    ],
  },
  {
    id: "tools",
    label: "Tools & settings",
    icon: Settings,
    items: [
      {
        href: "/agents",
        label: "Agent monitoring",
        icon: Radio,
        permission: "pipeline:read",
      },
      {
        href: "/benchmarks",
        label: "Benchmarks",
        icon: BarChart3,
        permission: "benchmarks:read",
      },
      {
        href: "/settings",
        label: "Organisation settings",
        icon: Settings,
        permission: "settings:read",
      },
      { href: "/account", label: "Account security", icon: Shield, permission: "org:read" },
      {
        href: "/admin",
        label: "Administration",
        icon: Shield,
        permission: "users:read",
      },
    ],
  },
] satisfies {
  id: string;
  label: string;
  icon: LucideIcon;
  items: NavigationItem[];
}[];

function NavigationGroup({
  id,
  label,
  icon: GroupIcon,
  items,
  collapsed,
  searching,
  pathname,
  onNavigate,
}: {
  id: string;
  label: string;
  icon: LucideIcon;
  items: NavigationItem[];
  collapsed: boolean;
  searching: boolean;
  pathname: string;
  onNavigate?: () => void;
}) {
  const [open, setOpen] = useState(true);
  const reduceMotion = useReducedMotion();
  const navigationId = useId();
  const expanded = collapsed || searching || open;

  return (
    <section aria-label={label} className={collapsed ? "mb-2" : "mb-4"}>
      {!collapsed && (
        <button
          type="button"
          aria-expanded={expanded}
          aria-controls={navigationId}
          onClick={() => setOpen((value) => !value)}
          disabled={searching}
          className="group mb-1 flex w-full items-center rounded-[9px] px-3.5 py-1.5 text-left text-[10px] font-bold uppercase tracking-[0.1em] text-slate-500 hover:bg-slate-100 hover:text-slate-700"
        >
          <AnimatePresence initial={false} mode="popLayout">
            {!expanded && (
              <motion.span
                key={id}
                initial={{ opacity: 0, x: -8, scale: 0.8 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: -8, scale: 0.8 }}
                transition={
                  reduceMotion
                    ? { duration: 0 }
                    : { type: "spring", stiffness: 420, damping: 28 }
                }
                className="mr-2 flex h-5 w-5 items-center justify-center rounded-md bg-teal-700/8 text-teal-700"
              >
                <GroupIcon className="h-3 w-3" />
              </motion.span>
            )}
          </AnimatePresence>
          <span className="flex-1 whitespace-nowrap">{label}</span>
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 transition-transform duration-300 motion-reduce:transition-none",
              !expanded && "-rotate-90",
            )}
          />
        </button>
      )}
      <motion.div
        id={navigationId}
        initial={false}
        animate={{ height: expanded ? "auto" : 0, opacity: expanded ? 1 : 0 }}
        transition={
          reduceMotion
            ? { duration: 0 }
            : {
                height: { duration: 0.28, ease: [0.22, 1, 0.36, 1] },
                opacity: { duration: 0.18 },
              }
        }
        className="overflow-hidden"
        inert={!expanded}
      >
        <div className="flex flex-col gap-0.5">
          {items.map((item, index) => {
            const active =
              pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <motion.div
                key={item.href}
                initial={false}
                animate={
                  expanded
                    ? { opacity: 1, y: 0, scale: 1 }
                    : { opacity: 0, y: -9, scale: 0.98 }
                }
                transition={
                  reduceMotion
                    ? { duration: 0 }
                    : {
                        type: "spring",
                        stiffness: 380,
                        damping: 23,
                        delay: expanded ? Math.min(index, 5) * 0.035 : 0,
                      }
                }
              >
                <Link
                  href={item.href}
                  onClick={onNavigate}
                  title={collapsed ? item.label : undefined}
                  aria-label={collapsed ? item.label : undefined}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex min-h-10 items-center gap-2.5 rounded-[10px] px-3.5 py-2.5 text-[12px]",
                    active
                      ? "bg-teal-700/8 font-semibold text-teal-700"
                      : "font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                    collapsed && "justify-center px-0",
                  )}
                >
                  <item.icon className="h-4 w-4 shrink-0" strokeWidth={1.7} />
                  {!collapsed && (
                    <span className="whitespace-nowrap">{item.label}</span>
                  )}
                </Link>
              </motion.div>
            );
          })}
        </div>
      </motion.div>
    </section>
  );
}

export function AppSidebar({
  collapsed = false,
  onNavigate,
  connected,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
  connected: boolean;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { session, hasPermission, hasTrack, switchOrganization, logout } =
    useAuth();
  const { pushToast } = useToast();
  const [query, setQuery] = useState("");
  const [profileOpen, setProfileOpen] = useState(false);
  const reduceMotion = useReducedMotion();
  const initials =
    session?.user.full_name
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join("") || "R";
  const primaryProgramme = session?.active_organization?.primary_programme;
  const isPlatformAdmin = Boolean(session?.user?.is_platform_admin);
  const groups = NAVIGATION_GROUPS.map((group) => ({
    ...group,
    items: (group.items as NavigationItem[]).filter(
      (item) =>
        hasPermission(item.permission) &&
        (!item.track ||
          (isPlatformAdmin
            ? hasTrack(item.track)
            : primaryProgramme && (session?.active_organization?.enabled_tracks?.length ?? 0) <= 1
            ? item.track === primaryProgramme
            : hasTrack(item.track))) &&
        (collapsed ||
          item.label.toLowerCase().includes(query.trim().toLowerCase())),
    ),
  })).filter((group) => group.items.length > 0);

  const changeOrganization = async (id: string) => {
    try {
      await switchOrganization(id);
      router.refresh();
    } catch (error) {
      pushToast(
        "Could not switch organisation",
        "error",
        error instanceof Error ? error.message : undefined,
      );
    }
  };

  return (
    <div className="flex h-full flex-col bg-white p-3.5">
      <div
        className={cn(
          "flex h-10 shrink-0 items-center gap-2.5 px-1 pb-1",
          collapsed && "justify-center px-0",
        )}
      >
        <Link
          href="/dashboard"
          aria-label="Recova dashboard"
          onClick={onNavigate}
          className="flex h-10 w-10 shrink-0 items-center justify-center text-teal-700"
        >
          <RecovaMark size={32} />
        </Link>
        {!collapsed && (
          <span className="flex-1 text-[23px] font-bold tracking-[-0.05em] text-slate-900">
            Recova
          </span>
        )}
        {onNavigate && (
          <button
            type="button"
            aria-label="Close menu"
            onClick={onNavigate}
            className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-slate-100"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {!collapsed && (
        <div className="relative my-4 shrink-0">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            aria-label="Search navigation"
            placeholder="Search menu…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="h-10 w-full rounded-[9px] border border-slate-200 bg-slate-100 pl-9 pr-3 text-xs text-slate-900 placeholder:text-slate-500"
          />
        </div>
      )}

      <nav
        aria-label="Main navigation"
        className={cn(
          "min-h-0 flex-1 overflow-y-auto overscroll-contain [scrollbar-width:thin]",
          collapsed && "mt-5",
        )}
      >
        {groups.map((group) => (
          <NavigationGroup
            key={group.id}
            {...group}
            pathname={pathname}
            collapsed={collapsed}
            searching={Boolean(query.trim()) && !collapsed}
            onNavigate={onNavigate}
          />
        ))}
        {groups.length === 0 && (
          <p
            role="status"
            className="px-3 py-6 text-xs leading-relaxed text-slate-500"
          >
            No pages match “{query}”.
          </p>
        )}
      </nav>

      <div className="relative shrink-0 space-y-2 border-t border-slate-200 pt-3">
        {!collapsed && session && session.memberships.length > 1 && (
          <div className="relative">
            <Building2 className="pointer-events-none absolute left-3 top-3 h-3.5 w-3.5 text-slate-500" />
            <select
              aria-label="Active organisation"
              value={session.active_organization?.id || ""}
              onChange={(event) => void changeOrganization(event.target.value)}
              className="h-10 w-full rounded-[9px] border border-slate-200 bg-slate-100 pl-8 pr-2 text-xs text-slate-700"
            >
              {session.memberships.map((membership) => (
                <option key={membership.id} value={membership.organization_id}>
                  {membership.organization_name || membership.organization_slug}
                </option>
              ))}
            </select>
          </div>
        )}
        {profileOpen && (
          <button
            type="button"
            tabIndex={-1}
            aria-label="Close account menu"
            className="fixed inset-0 z-40 cursor-default"
            onClick={() => setProfileOpen(false)}
          />
        )}
        <AnimatePresence>
          {profileOpen && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ duration: reduceMotion ? 0 : 0.18 }}
              className="absolute bottom-full left-0 z-50 mb-2 w-56 rounded-2xl border border-slate-200 bg-white p-2 shadow-lg"
              onKeyDown={(event) => {
                if (event.key === "Escape") setProfileOpen(false);
              }}
            >
              <div className="border-b border-slate-100 px-3 py-2">
                <p className="truncate text-xs font-semibold">
                  {session?.user.full_name}
                </p>
                <p className="mt-1 truncate text-[10px] text-slate-500">
                  {session?.active_organization?.name}
                </p>
              </div>
              <button
                type="button"
                onClick={() =>
                  void logout().then(() => router.replace("/login"))
                }
                className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-xs font-medium text-red-700 hover:bg-red-50"
              >
                <LogOut className="h-3.5 w-3.5" /> Sign out
              </button>
            </motion.div>
          )}
        </AnimatePresence>
        <button
          type="button"
          aria-expanded={profileOpen}
          aria-label="Account options"
          onClick={() => setProfileOpen((value) => !value)}
          className={cn(
            "relative flex w-full items-center gap-2.5 rounded-[11px] bg-slate-100 p-2.5 text-left hover:bg-slate-200/60",
            collapsed && "justify-center p-1.5",
          )}
        >
          <span className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-700 text-[10px] font-bold text-[#aeff9a]">
            {initials}
            <span
              title={
                connected ? "Live updates connected" : "Live updates connecting"
              }
              className={cn(
                "absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-[#fafdff]",
                connected ? "bg-emerald-500" : "bg-slate-400",
              )}
            />
          </span>
          {!collapsed && (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs font-semibold text-slate-900">
                  {session?.user.full_name}
                </span>
                <span className="mt-0.5 block truncate text-[10px] text-slate-500">
                  {formatLabel(session?.role)}
                </span>
              </span>
              <ChevronDown className="h-3.5 w-3.5 shrink-0 text-slate-500" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
