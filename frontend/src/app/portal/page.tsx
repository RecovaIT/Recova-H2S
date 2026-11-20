"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AccountSecurityPanel } from "@/components/AccountSecurityPanel";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Bell,
  Brain,
  Check,
  ChevronRight,
  Globe,
  Heart,
  Home,
  LogOut,
  ShieldCheck,
  Watch,
  Wind,
  ClipboardCheck,
  Users,
  Upload,
} from "lucide-react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { useAuth } from "@/hooks/useAuth";
import { useLanguage } from "@/hooks/useLanguage";
import { api } from "@/lib/api";
import { RecovaMark } from "@/components/RecovaMark";
import { Button } from "@/components/ui/button";
import { cn, nowTimestampMs } from "@/lib/utils";
import {
  getPortalDictionary,
  type PortalDictionary,
  type PortalLang,
} from "@/lib/portal-i18n";

type PortalEnrolment = {
  enrolment_id: string;
  patient_id: string;
  organization_id: string;
  facility: string;
  programme: string;
  track: string;
  status: string;
  active: boolean;
};

type PortalCareDetail = {
  enrolment_id: string;
  track: string;
  released_instructions: Array<{
    id: string;
    source: string;
    instruction?: string | { title?: string; detail?: string };
    signed_at?: string;
    decision?: string;
    notes?: string | null;
    summary_en?: string | null;
    summary_ar?: string | null;
  }>;
  appointments: Array<{
    referral_id: string;
    pathway: string;
    status: string;
    priority: string;
    facility_name?: string | null;
    appointment_at?: string | null;
    appointment_reference?: string | null;
    outcome?: string | null;
  }>;
  interventions: Array<{
    id: string;
    type: string;
    status: string;
    title: string;
    details?: string | null;
  }>;
};

type Portal = {
  name: string;
  track: string;
  facility: string;
  care_contact?: { name: string; role: string; facility?: string | null };
  active_enrolment?: PortalEnrolment;
  enrolments?: PortalEnrolment[];
  synthetic: boolean;
  scenario?: string;
  consents: string[];
  observations: {
    id: string;
    metric: string;
    value: number;
    unit: string;
    at: string;
    source: string;
  }[];
  checkins: {
    id: string;
    at: string;
    mood: number;
    stress: number;
    text: string;
    crisis: boolean;
  }[];
  care: {
    id: string;
    title: string;
    detail: string;
    status: string;
    at?: string;
  }[];
  referrals: { id: string; pathway: string; status: string }[];
  notices: {
    id: string;
    title: string;
    body: string;
    plain_language_action?: string | null;
    issuer: string;
    severity: string;
  }[];
  acknowledged: string[];
};

const PROGRAMME_ICONS = {
  core: Heart,
  loop: ClipboardCheck,
  neuro: Brain,
  worksafe: ShieldCheck,
} as const;

type Tab = "home" | "checkin" | "devices" | "care" | "profile";
const NAV_ITEMS = [
  { id: "home", icon: Home },
  { id: "checkin", icon: Heart },
  { id: "devices", icon: Watch },
  { id: "care", icon: Users },
  { id: "profile", icon: ShieldCheck },
] as const;

function MemoryActivity({
  t,
  onSave,
}: {
  t: PortalDictionary;
  onSave: (result: {
    correct: boolean;
    response: number[];
    expected: number[];
    reaction_time_ms: number;
  }) => Promise<void>;
}) {
  const [phase, setPhase] = useState<"ready" | "watch" | "repeat" | "done">(
    "ready",
  );
  const [pattern, setPattern] = useState<number[]>([]);
  const [answer, setAnswer] = useState<number[]>([]);
  const [highlight, setHighlight] = useState(-1);
  const [saveOutcome, setSaveOutcome] = useState<"idle" | "saved" | "failed">(
    "idle",
  );
  const started = useRef(0);

  useEffect(() => {
    if (phase !== "watch") return;
    const timers = pattern.flatMap((key, index) => [
      setTimeout(() => setHighlight(key), 600 + index * 900),
      setTimeout(() => setHighlight(-1), 1200 + index * 900),
    ]);
    timers.push(
      setTimeout(
        () => {
          started.current = nowTimestampMs();
          setPhase("repeat");
        },
        600 + pattern.length * 900,
      ),
    );
    return () => timers.forEach(clearTimeout);
  }, [phase, pattern]);

  async function press(key: number) {
    const response = [...answer, key];
    setAnswer(response);
    if (response.length === pattern.length) {
      setPhase("done");
      try {
        await onSave({
          correct: response.every((value, i) => value === pattern[i]),
          response,
          expected: pattern,
          reaction_time_ms: Math.round(nowTimestampMs() - started.current),
        });
        setSaveOutcome("saved");
      } catch {
        setSaveOutcome("failed");
      }
    }
  }

  return (
    <section className="patient-panel">
      <h2>{t.memoryTitle}</h2>
      <p className="patient-muted">{t.memoryDesc}</p>
      <div aria-live="polite" className="my-4 text-sm font-semibold">
        {phase === "ready"
          ? t.memoryReady
          : phase === "watch"
            ? t.memoryWatch
            : phase === "repeat"
              ? `${t.memoryRepeatPrefix} ${answer.length} ${t.memoryRepeatOfTotal}`
              : saveOutcome === "saved"
                ? t.memorySaved
                : saveOutcome === "failed"
                  ? t.memoryFailed
                  : t.memorySaving}
      </div>
      <div className="grid grid-cols-4 gap-3">
        {[0, 1, 2, 3].map((key) => (
          <button
            key={key}
            type="button"
            aria-label={`${t.memoryTilePrefix} ${key + 1}`}
            disabled={phase !== "repeat"}
            onClick={() => void press(key)}
            className={cn(
              "aspect-square rounded-2xl border text-xl font-semibold transition-colors",
              highlight === key
                ? "bg-[#003e5e] text-[#aeff9a]"
                : "bg-[#edf4f7] text-[#003e5e]",
            )}
          >
            {key + 1}
          </button>
        ))}
      </div>
      <Button
        className="mt-5"
        disabled={phase === "watch" || phase === "repeat"}
        onClick={() => {
          setPattern(
            Array.from(
              crypto.getRandomValues(new Uint32Array(3)),
              (n) => n % 4,
            ),
          );
          setAnswer([]);
          setSaveOutcome("idle");
          setPhase("watch");
        }}
      >
        {phase === "done" ? t.memoryAnother : t.memoryStart}
      </Button>
    </section>
  );
}

export default function ParticipantPortal() {
  const { session, loading: authLoading, logout } = useAuth();
  const { lang: globalLang, setLang: setGlobalLang, t: tGlobal } = useLanguage();
  const router = useRouter();
  const [lang, setLang] = useState<PortalLang>(() => {
    if (typeof window === "undefined") return "en";
    const saved =
      window.localStorage.getItem("recova_portal_lang") ||
      window.localStorage.getItem("recova_lang");
    return saved === "ar" ? "ar" : "en";
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved =
      window.localStorage.getItem("recova_portal_lang") ||
      window.localStorage.getItem("recova_lang");
    if (saved === "ar" || saved === "en") {
      setLang(saved);
    } else if (globalLang === "ar" || globalLang === "en") {
      setLang(globalLang);
    }
  }, [globalLang]);
  const [data, setData] = useState<Portal | null>(null);
  const [careDetail, setCareDetail] = useState<PortalCareDetail | null>(null);
  const [selectedEnrolmentId, setSelectedEnrolmentId] = useState<string | null>(
    null,
  );
  const [tab, setTab] = useState<Tab>("home");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [mood, setMood] = useState(6);
  const [stress, setStress] = useState(3);
  const [craving, setCraving] = useState(2);
  const [reflection, setReflection] = useState("");
  const [crisis, setCrisis] = useState(false);
  const [shift, setShift] = useState("");
  const [worksite, setWorksite] = useState("");
  const [escalationNotice, setEscalationNotice] = useState<{
    en: string;
    ar: string;
  } | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const submissionId = useRef(crypto.randomUUID());
  const [metric, setMetric] = useState("sleep_hours");

  const t = getPortalDictionary(lang);
  const isRtl = lang === "ar";

  function toggleLang() {
    const next: PortalLang = lang === "en" ? "ar" : "en";
    setLang(next);
    setGlobalLang(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("recova_portal_lang", next);
      window.localStorage.setItem("recova_lang", next);
    }
  }

  const refresh = useCallback(async () => {
    try {
      const mePath = selectedEnrolmentId
        ? `/portal/me?enrolment_id=${encodeURIComponent(selectedEnrolmentId)}`
        : "/portal/me";
      const me = await api.get<Portal>(mePath);
      setData(me);
      const carePath = selectedEnrolmentId
        ? `/portal/care?enrolment_id=${encodeURIComponent(selectedEnrolmentId)}`
        : "/portal/care";
      api
        .get<PortalCareDetail>(carePath)
        .then((c) => {
          if (c && Array.isArray(c.appointments)) setCareDetail(c);
        })
        .catch(() => undefined);
      setError("");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : t.loadErrorFallback,
      );
    }
  }, [selectedEnrolmentId, t.loadErrorFallback]);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/login");
      return;
    }
    const timer = setTimeout(() => {
      void refresh();
    }, 0);
    return () => clearTimeout(timer);
  }, [authLoading, session, router, refresh]);

  async function action(work: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await work();
      setMessage(success);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : t.tryAgain);
    } finally {
      setBusy(false);
    }
  }

  if (!data)
    return (
      <main
        dir={isRtl ? "rtl" : "ltr"}
        lang={lang}
        className={cn(
          "flex min-h-dvh items-center justify-center bg-[#f0f6f9] p-6",
          isRtl && "text-right font-sans",
        )}
      >
        <div role="status" className="max-w-sm space-y-4 text-center">
          <RecovaMark size={40} className="mx-auto text-[#003e5e]" />
          <p>{error || t.loadingText}</p>
          {error && (
            <>
              <Button onClick={() => void refresh()}>{t.tryAgain}</Button>
              <p>
                <a href="/login" className="text-sm underline">
                  {t.returnToSignIn}
                </a>
              </p>
            </>
          )}
        </div>
      </main>
    );

  const trackKey = (
    data.track in t.programmes ? data.track : "core"
  ) as keyof typeof t.programmes;
  const programme = t.programmes[trackKey];
  const ProgrammeIcon = PROGRAMME_ICONS[trackKey];

  const latest = (code: string) =>
    data.observations.find((o) => o.metric === code);
  const todaysCheckin = data.checkins.find(
    (c) => new Date(c.at).toDateString() === new Date().toDateString(),
  );
  const locale = lang === "ar" ? "ar-AE" : undefined;
  const samples = data.observations
    .filter((o) => o.metric === metric)
    .slice(0, 7)
    .reverse()
    .map((o) => ({
      day: new Date(o.at).toLocaleDateString(locale, { weekday: "short" }),
      value: o.value,
    }));
  const processing = data.consents.includes("data_processing");
  const title = t.nav[tab];

  async function importFile(file?: File) {
    if (!file) return;
    await action(async () => {
      if (file.size > 1024 * 1024) throw new Error(t.csvSizeError);
      const text = await file.text();
      const rows = text.trim().split(/\r?\n/);
      if (rows.shift()?.trim() !== "metric,value,unit,at")
        throw new Error(t.csvHeaderError);
      const readings = rows.filter(Boolean).map((row) => {
        const cells = row.split(",");
        if (cells.length !== 4 || !Number.isFinite(Number(cells[1])))
          throw new Error(t.csvRowError);
        return {
          metric: cells[0].trim(),
          value: Number(cells[1]),
          unit: cells[2].trim(),
          at: cells[3].trim(),
        };
      });
      const digest = await crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(text),
      );
      const hex = Array.from(new Uint8Array(digest))
        .map((value) => value.toString(16).padStart(2, "0"))
        .join("");
      const requestId = [
        hex.slice(0, 8),
        hex.slice(8, 12),
        hex.slice(12, 16),
        hex.slice(16, 20),
        hex.slice(20, 32),
      ].join("-");
      const response = await api.post<{ accepted: number }>(
        "/portal/wearable-import",
        { request_id: requestId, readings },
      );
      setMetric(readings[0]?.metric || "sleep_hours");
      return response;
    }, t.wearableImportSuccess);
  }

  return (
    <div
      dir={isRtl ? "rtl" : "ltr"}
      lang={lang}
      className={cn("patient-app", isRtl && "text-right font-sans")}
    >
      <header className="patient-header">
        <a
          href="/portal"
          aria-label={t.homeAriaLabel}
          className="flex items-center gap-2 text-[#003e5e]"
        >
          <RecovaMark size={29} />
          <span className="text-xl font-bold tracking-tight">Recova</span>
        </a>
        <span className="hidden text-xs text-slate-500 sm:block">
          {data.facility}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={toggleLang}
            aria-label={
              lang === "en"
                ? "Switch portal language to Arabic"
                : "التبديل إلى اللغة الإنجليزية"
            }
            className="inline-flex items-center gap-1.5 rounded-full border border-[#d6e5ed] bg-white px-3 py-1.5 text-xs font-semibold text-[#003e5e] hover:bg-[#edf4f7]"
          >
            <Globe className="h-3.5 w-3.5" />
            <span>{t.languageSwitchLabel}</span>
          </button>
          <button
            type="button"
            aria-label={t.profileAriaLabel}
            onClick={() => setTab("profile")}
            className="patient-avatar"
          >
            {data.name.slice(0, 1)}
          </button>
        </div>
      </header>
      <main className="patient-main" id="portal-content">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-widest text-slate-500">
              {t.formatSpaceTitle(programme.name)}
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">
              {tab === "home" ? t.formatHello(data.name) : title}
            </h1>
          </div>
          <ProgrammeIcon
            className="h-6 w-6 text-[#003e5e]"
            strokeWidth={1.5}
          />
        </div>
        {data.enrolments && data.enrolments.length > 1 && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-[#e2edf2] bg-white px-4 py-2.5 text-xs">
            <span className="font-semibold text-[#003e5e]">
              {t.enrolmentActiveLabel}
            </span>
            <select
              aria-label={t.enrolmentActiveLabel}
              value={
                selectedEnrolmentId ||
                data.active_enrolment?.enrolment_id ||
                ""
              }
              onChange={(e) => setSelectedEnrolmentId(e.target.value || null)}
              className="rounded-lg border border-slate-200 bg-[#f8fbfc] px-2.5 py-1.5 text-xs font-medium text-[#011621]"
            >
              {data.enrolments.map((enr) => (
                <option key={enr.enrolment_id} value={enr.enrolment_id}>
                  {`${tGlobal(enr.facility)} · ${tGlobal(enr.programme.toUpperCase())}`}
                </option>
              ))}
            </select>
          </div>
        )}
        {data.synthetic && (
          <div className="mb-4 rounded-xl bg-[#e8f1f6] px-3 py-2 text-[11px] text-slate-600">
            {`${t.syntheticAccountBadge}${data.scenario ? ` · ${tGlobal(data.scenario)}` : ""}`}
          </div>
        )}
        {error && (
          <div
            role="alert"
            className="mb-4 rounded-xl bg-red-50 p-4 text-sm text-red-800"
          >
            {error}
          </div>
        )}
        {message && (
          <div
            role="status"
            className="mb-4 flex items-start gap-2 rounded-xl bg-green-50 p-4 text-sm text-green-900"
          >
            <Check className="h-4 w-4 shrink-0" />
            {message}
          </div>
        )}
        {!processing && (
          <div className="mb-5 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
            <ShieldCheck className="h-5 w-5 shrink-0 text-amber-700" />
            <div>
              <p className="text-sm font-semibold">{t.permissionFirstTitle}</p>
              <p className="mt-1 text-xs leading-relaxed">
                {t.permissionFirstBody}
              </p>
              <button
                onClick={() => setTab("profile")}
                className="mt-2 text-xs font-semibold underline"
              >
                {t.reviewPrivacyChoices}
              </button>
            </div>
          </div>
        )}
        {tab === "home" && (
          <>
            <section className="patient-welcome">
              <div className="relative z-10 max-w-lg">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/60 px-3 py-1 text-[11px] font-medium text-[#32634f]">
                  <Wind className="h-3.5 w-3.5" /> {t.momentTag}
                </span>
                <h2 className="mt-5 text-[28px] font-semibold leading-tight tracking-tight">
                  {programme.title}
                </h2>
                <p className="mt-3 max-w-md text-sm leading-relaxed text-[#456858]">
                  {programme.description}
                </p>
                <Button onClick={() => setTab("checkin")} className="mt-6">
                  {todaysCheckin
                    ? t.viewTodaysCheckin
                    : data.track === "neuro"
                      ? t.exploreActivities
                      : t.letsCheckIn}
                  <ArrowRight className={cn("h-4 w-4", isRtl && "rotate-180")} />
                </Button>
              </div>
              <div aria-hidden className="patient-orbit">
                <Heart className="h-12 w-12" strokeWidth={1} />
              </div>
            </section>
            {data.track === "loop" && (
              <section className="patient-panel">
                <h2>{t.screeningTitle}</h2>
                <p className="patient-muted">{t.screeningSubtitle}</p>
                <div className="mt-5 grid grid-cols-3 gap-2">
                  {[
                    { code: "hba1c", label: t.metrics.hba1c },
                    { code: "bp_systolic", label: t.metrics.bp_systolic },
                    { code: "bp_diastolic", label: t.metrics.bp_diastolic },
                  ].map((item) => (
                    <div
                      key={item.code}
                      className="rounded-xl bg-[#f3f7f9] p-3"
                    >
                      <p className="text-[10px] text-slate-500">{item.label}</p>
                      <p className="mt-2 text-xl font-semibold">
                        {latest(item.code)?.value ?? "—"}
                      </p>
                      <p className="mt-1 text-[10px] text-slate-500">
                        {latest(item.code)?.unit || t.awaitingResult}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}
            {data.checkins[0]?.crisis && (
              <section className="patient-panel border-rose-200 bg-rose-50">
                <h2>{t.urgentTitle}</h2>
                <p className="patient-muted">{t.urgentBody}</p>
                <button
                  className="patient-text-button mt-3"
                  onClick={() => setTab("care")}
                >
                  {t.viewCareInfo}{" "}
                  <ArrowRight className={cn("h-4 w-4", isRtl && "rotate-180")} />
                </button>
              </section>
            )}
            <div className="patient-columns">
              <section className="patient-panel">
                <div className="flex items-center justify-between">
                  <h2>{t.todayTitle}</h2>
                  <span className="text-xs text-slate-500">
                    {new Date().toLocaleDateString(locale, {
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                </div>
                <button
                  className="patient-task"
                  onClick={() => setTab("checkin")}
                >
                  <span className="patient-icon">
                    <ProgrammeIcon className="h-5 w-5" />
                  </span>
                  <span className="flex-1 text-start">
                    <strong className="block text-sm font-semibold">
                      {programme.activity}
                    </strong>
                    <span className="mt-1 block text-xs text-slate-500">
                      {todaysCheckin
                        ? t.checkinDoneToday
                        : programme.subtitle}
                    </span>
                  </span>
                  {todaysCheckin ? (
                    <Check className="h-5 w-5 text-green-700" />
                  ) : (
                    <ChevronRight
                      className={cn("h-4 w-4", isRtl && "rotate-180")}
                    />
                  )}
                </button>
                <button
                  className="patient-task"
                  onClick={() => setTab("devices")}
                >
                  <span className="patient-icon">
                    <Watch className="h-5 w-5" />
                  </span>
                  <span className="flex-1 text-start">
                    <strong className="block text-sm font-semibold">
                      {t.wearableTaskTitle}
                    </strong>
                    <span className="mt-1 block text-xs text-slate-500">
                      {latest("sleep_hours")
                        ? t.wearableTaskHasData
                        : t.wearableTaskNoData}
                    </span>
                  </span>
                  <ChevronRight
                    className={cn("h-4 w-4", isRtl && "rotate-180")}
                  />
                </button>
              </section>
              <section className="patient-panel">
                <h2>{t.careConnectedTitle}</h2>
                <p className="patient-muted">{data.facility}</p>
                <div className="my-5 flex items-center gap-3">
                  <span className="patient-icon">
                    <Users className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold">
                      {data.care_contact?.name || t.defaultCareTeam}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {data.care_contact?.role || t.defaultCareRole}
                    </p>
                  </div>
                </div>
                <button
                  className="patient-text-button"
                  onClick={() => setTab("care")}
                >
                  {t.openCarePlan}{" "}
                  <ArrowRight className={cn("h-4 w-4", isRtl && "rotate-180")} />
                </button>
              </section>
            </div>
            <section className="patient-panel">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2>{t.healthSignalsTitle}</h2>
                  <p className="patient-muted">{t.healthSignalsSubtitle}</p>
                </div>
                <label className="sr-only" htmlFor="signal">
                  {t.healthSignalSelectAria}
                </label>
                <select
                  id="signal"
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs"
                  value={metric}
                  onChange={(event) => setMetric(event.target.value)}
                >
                  <option value="sleep_hours">{t.metrics.sleep_hours}</option>
                  <option value="hrv_rmssd">{t.metrics.hrv_rmssd}</option>
                  <option value="resting_hr">{t.metrics.resting_hr}</option>
                  <option value="steps">{t.metrics.steps}</option>
                </select>
              </div>
              <div className="mt-5 grid grid-cols-3 gap-2">
                {[
                  { code: "sleep_hours", label: t.metrics.sleep_hours },
                  { code: "resting_hr", label: t.metrics.resting_hr_short },
                  { code: "steps", label: t.metrics.steps },
                ].map((item) => (
                  <div key={item.code} className="rounded-2xl bg-[#f3f7f9] p-3">
                    <p className="text-[10px] text-slate-500">{item.label}</p>
                    <p className="mt-2 text-xl font-semibold tabular-nums">
                      {latest(item.code)?.value.toLocaleString(locale, {
                        maximumFractionDigits: 1,
                      }) ?? "—"}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {latest(item.code)?.unit || t.noReadingsYet}
                    </p>
                  </div>
                ))}
              </div>
              {samples.length ? (
                <div
                  className="mt-5 h-40"
                  role="img"
                  aria-label={`${t.healthSignalsTitle}: ${metric.replaceAll("_", " ")}`}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={samples}
                      margin={{ top: 8, right: 8, left: 8, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient
                          id="patient-signal"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="0%"
                            stopColor="#6aa58c"
                            stopOpacity={0.3}
                          />
                          <stop
                            offset="100%"
                            stopColor="#6aa58c"
                            stopOpacity={0.01}
                          />
                        </linearGradient>
                      </defs>
                      <XAxis
                        dataKey="day"
                        tickLine={false}
                        axisLine={false}
                        tick={{ fontSize: 10, fill: "#5a7d93" }}
                      />
                      <Tooltip
                        contentStyle={{ borderRadius: 14, fontSize: 12 }}
                      />
                      <Area
                        type="monotone"
                        dataKey="value"
                        stroke="#397d69"
                        strokeWidth={2.5}
                        fill="url(#patient-signal)"
                        isAnimationActive={false}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="my-8 text-center text-sm text-slate-500">
                  {t.observationsEmpty}
                </p>
              )}
              <p className="mt-3 text-[10px] leading-relaxed text-slate-500">
                {latest(metric)
                  ? `${t.latestReadingPrefix}: ${new Date(latest(metric)!.at).toLocaleString(locale)}`
                  : t.missingReadingsNote}
              </p>
            </section>
            {data.notices.map((notice) => (
              <section key={notice.id} className="patient-panel">
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Bell className="h-4 w-4" />
                  {notice.issuer}
                </div>
                <h2 className="mt-3">{notice.title}</h2>
                <p className="patient-muted">{notice.body}</p>
                <Button
                  className="mt-4"
                  size="sm"
                  variant="outline"
                  disabled={busy || data.acknowledged.includes(notice.id)}
                  onClick={() =>
                    void action(
                      () =>
                        api.post("/portal/notices/acknowledge", {
                          notice_id: notice.id,
                        }),
                      t.noticeAckSuccess,
                    )
                  }
                >
                  {data.acknowledged.includes(notice.id)
                    ? t.noticeAcknowledged
                    : t.noticeAcknowledge}
                </Button>
              </section>
            ))}
          </>
        )}
        {tab === "checkin" && (
          <>
            {data.track === "neuro" && (
              <MemoryActivity
                t={t}
                onSave={async (result) => {
                  await api.post("/portal/cognitive-sessions", {
                    request_id: crypto.randomUUID(),
                    enrolment_id: data.active_enrolment?.enrolment_id,
                    task_version: "neuro-visual-sequence-v1",
                    raw_trials: [
                      {
                        task_type: "sequence_4key",
                        modality: "visual",
                        expected: result.expected,
                        response: result.response,
                        reaction_time_ms: Math.max(
                          50,
                          Math.min(60000, result.reaction_time_ms),
                        ),
                        correct: result.correct,
                      },
                    ],
                  });
                  await refresh();
                }}
              />
            )}
            <form
              className="patient-panel"
              onSubmit={(event) => {
                event.preventDefault();
                void action(
                  async () => {
                    const response = await api.post<{
                      emergency: boolean;
                      escalation_instructions?: {
                        en: string;
                        ar: string;
                      } | null;
                    }>("/portal/check-ins", {
                      mood,
                      stress,
                      craving: data.track === "core" ? craving : null,
                      text: reflection,
                      crisis,
                      request_id: submissionId.current,
                      ...(data.active_enrolment?.enrolment_id
                        ? { enrolment_id: data.active_enrolment.enrolment_id }
                        : {}),
                      ...(data.track === "worksafe" && shift.trim()
                        ? { shift: shift.trim() }
                        : {}),
                      ...(data.track === "worksafe" && worksite.trim()
                        ? { worksite: worksite.trim() }
                        : {}),
                    });
                    if (response?.escalation_instructions) {
                      setEscalationNotice(response.escalation_instructions);
                    }
                    setSubmitted(true);
                    return response;
                  },
                  crisis ? t.checkinSuccessUrgent : t.checkinSuccessRoutine,
                );
              }}
            >
              <h2>{programme.activity}</h2>
              <p className="patient-muted">{programme.subtitle}</p>
              {[
                {
                  label:
                    data.track === "worksafe"
                      ? t.readinessLabel
                      : t.moodLabel,
                  value: mood,
                  change: setMood,
                  low: t.moodLow,
                  high: t.moodHigh,
                },
                {
                  label: t.stressLabel,
                  value: stress,
                  change: setStress,
                  low: t.stressLow,
                  high: t.stressHigh,
                },
                ...(data.track === "core"
                  ? [
                      {
                        label: t.cravingLabel,
                        value: craving,
                        change: setCraving,
                        low: t.cravingLow,
                        high: t.cravingHigh,
                      },
                    ]
                  : []),
              ].map((field) => (
                <label
                  key={field.label}
                  className="my-6 block text-sm font-medium"
                >
                  <span className="flex items-center justify-between gap-2">
                    <span>{field.label}</span>
                    <span className="text-[#003e5e]">{`${field.value}/10`}</span>
                  </span>
                  <input
                    className="mt-5 w-full accent-[#003e5e]"
                    type="range"
                    min="0"
                    max="10"
                    value={field.value}
                    onChange={(event) =>
                      field.change(Number(event.target.value))
                    }
                  />
                  <span className="mt-1 flex justify-between text-[10px] font-normal text-slate-500">
                    <span>{field.low}</span>
                    <span>{field.high}</span>
                  </span>
                </label>
              ))}
              {data.track === "worksafe" && (
                <div className="my-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <label className="block text-xs font-medium text-slate-700">
                    {t.shiftLabel}
                    <input
                      type="text"
                      value={shift}
                      onChange={(e) => setShift(e.target.value)}
                      placeholder={t.shiftPlaceholder}
                      className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#f8fbfc] px-3 py-2 text-sm font-normal"
                    />
                  </label>
                  <label className="block text-xs font-medium text-slate-700">
                    {t.worksiteLabel}
                    <input
                      type="text"
                      value={worksite}
                      onChange={(e) => setWorksite(e.target.value)}
                      placeholder={t.worksitePlaceholder}
                      className="mt-1.5 w-full rounded-xl border border-slate-200 bg-[#f8fbfc] px-3 py-2 text-sm font-normal"
                    />
                  </label>
                </div>
              )}
              {escalationNotice && (
                <div
                  role="alert"
                  className="my-4 space-y-2 rounded-xl border border-rose-300 bg-rose-50 p-4 text-xs text-rose-900"
                >
                  <p dir="ltr" className="text-left font-semibold">
                    {escalationNotice.en}
                  </p>
                  <p dir="rtl" className="text-right font-sans font-medium">
                    {escalationNotice.ar}
                  </p>
                </div>
              )}
              <label className="block text-sm font-medium">
                {programme.prompt}
                <textarea
                  value={reflection}
                  onChange={(event) => setReflection(event.target.value)}
                  maxLength={4000}
                  rows={4}
                  className="mt-3 w-full rounded-xl border border-slate-200 bg-[#f8fbfc] p-3 text-sm font-normal"
                  placeholder={t.reflectionPlaceholder}
                />
              </label>
              <label className="my-5 flex items-start gap-3 rounded-xl bg-rose-50 p-4 text-sm">
                <input
                  className="mt-1 accent-[#003e5e]"
                  type="checkbox"
                  checked={crisis}
                  onChange={(event) => setCrisis(event.target.checked)}
                />
                <span>{t.urgentCheckboxLabel}</span>
              </label>
              <p className="mb-4 text-xs leading-relaxed text-slate-500">
                {t.emergencyDisclaimer}
              </p>
              <Button
                type="submit"
                className="w-full"
                disabled={busy || (!processing && !crisis) || submitted}
              >
                {submitted
                  ? t.checkinReceived
                  : busy
                    ? t.checkinSending
                    : t.checkinSend}
              </Button>
              {submitted && (
                <button
                  type="button"
                  className="patient-text-button mt-4"
                  onClick={() => {
                    submissionId.current = crypto.randomUUID();
                    setSubmitted(false);
                    setReflection("");
                    setCrisis(false);
                  }}
                >
                  {t.startAnotherCheckin}
                </button>
              )}
            </form>
            <section className="patient-panel">
              <h2>{t.recentCheckinsTitle}</h2>
              {data.checkins.length ? (
                data.checkins.map((item) => (
                  <div key={item.id} className="patient-history">
                    <span className="patient-icon">
                      <Check className="h-4 w-4" />
                    </span>
                    <div>
                      <p className="text-sm font-medium">
                        {new Date(item.at).toLocaleString(locale)}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {`${t.moodShort} ${item.mood}/10 · ${t.stressShort} ${item.stress}/10`}
                      </p>
                      {item.text && (
                        <p className="mt-2 text-sm leading-relaxed">
                          {item.text}
                        </p>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <p className="patient-muted">{t.recentCheckinsEmpty}</p>
              )}
            </section>
          </>
        )}
        {tab === "devices" && (
          <>
            <section className="patient-panel">
              <span className="patient-icon mb-4">
                <Watch className="h-6 w-6" />
              </span>
              <h2>{t.wearableTitle}</h2>
              <p className="patient-muted">{t.wearableDesc}</p>
              <div className="my-5 rounded-xl bg-[#edf4f7] p-4 text-xs leading-relaxed">
                {t.wearableProviderNote}
              </div>
              {["Apple Health", "Fitbit", "Garmin"].map((provider) => (
                <div key={provider} className="patient-history">
                  <Watch className="h-5 w-5 text-[#003e5e]" />
                  <div className="flex-1">
                    <p className="text-sm font-semibold">{provider}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {t.wearableAwaitingConfig}
                    </p>
                  </div>
                  <span className="text-[10px] text-slate-500">
                    {t.wearableUnavailable}
                  </span>
                </div>
              ))}
            </section>
            <section className="patient-panel">
              <h2>{t.importTitle}</h2>
              <p className="patient-muted">{t.importDesc}</p>
              <label className="my-5 flex min-h-28 cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-[#b5cdd9] bg-[#f5f9fb] p-5 text-center">
                <Upload className="h-6 w-6 text-[#003e5e]" />
                <span className="text-sm font-semibold">{t.chooseCsv}</span>
                <span className="text-[11px] text-slate-500">
                  {t.csvLimitNote}
                </span>
                <input
                  className="mt-2 max-w-full text-xs"
                  aria-label={t.chooseCsv}
                  type="file"
                  accept=".csv,text/csv"
                  disabled={
                    busy ||
                    !processing ||
                    !data.consents.includes("wearable_ingestion")
                  }
                  onChange={(event) => {
                    void importFile(event.target.files?.[0]);
                    event.target.value = "";
                  }}
                />
              </label>
              <button
                type="button"
                className="patient-text-button"
                onClick={() => {
                  const blob = new Blob(
                    [
                      `metric,value,unit,at\nsleep_hours,7.2,h,${new Date().toISOString()}\nresting_hr,66,bpm,${new Date().toISOString()}\nhrv_rmssd,48,ms,${new Date().toISOString()}\nsteps,5600,count,${new Date().toISOString()}\n`,
                    ],
                    { type: "text/csv" },
                  );
                  const url = URL.createObjectURL(blob);
                  const anchor = document.createElement("a");
                  anchor.href = url;
                  anchor.download = "recova-wearable-example.csv";
                  anchor.click();
                  URL.revokeObjectURL(url);
                }}
              >
                {t.downloadExampleCsv}{" "}
                <ArrowRight className={cn("h-4 w-4", isRtl && "rotate-180")} />
              </button>
              <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
                {t.syntheticExampleNote}
              </p>
              <button
                onClick={() => setTab("profile")}
                className="patient-text-button mt-5"
              >
                {t.manageWearableConsent} <ShieldCheck className="h-4 w-4" />
              </button>
            </section>
          </>
        )}
        {tab === "care" && (
          <>
            <section className="patient-panel">
              <h2>{t.careHeroTitle}</h2>
              <p className="patient-muted">
                {`${t.careHeroPrefix} ${data.facility}. ${t.careHeroSuffix}`}
              </p>
            </section>
            {careDetail?.released_instructions.map((item) => (
              <section className="patient-panel" key={item.id}>
                <span className="rounded-full bg-[#edf4f7] px-3 py-1 text-[10px] text-[#003e5e]">
                  {item.decision
                    ? item.decision.replaceAll("_", " ")
                    : item.source.replaceAll("_", " ")}
                </span>
                {item.notes && (
                  <p className="mt-3 text-sm font-medium">{item.notes}</p>
                )}
                {lang === "ar" && item.summary_ar ? (
                  <>
                    <p
                      dir="rtl"
                      className="mt-2 text-right font-sans text-sm leading-relaxed text-slate-800"
                    >
                      {item.summary_ar}
                    </p>
                    {item.summary_en && (
                      <p dir="ltr" className="patient-muted mt-2 text-left text-xs">
                        {item.summary_en}
                      </p>
                    )}
                  </>
                ) : (
                  <>
                    {item.summary_en && (
                      <p dir="ltr" className="patient-muted mt-2 text-left">
                        {item.summary_en}
                      </p>
                    )}
                    {item.summary_ar && (
                      <p
                        dir="rtl"
                        className="mt-2 text-right font-sans text-xs text-slate-600"
                      >
                        {item.summary_ar}
                      </p>
                    )}
                  </>
                )}
              </section>
            ))}
            {careDetail?.appointments.map((appt) => (
              <section className="patient-panel" key={appt.referral_id}>
                <span className="rounded-full bg-[#e4f3dd] px-3 py-1 text-[10px] font-semibold text-[#214e40]">
                  {appt.status.replaceAll("_", " ")}
                </span>
                <h2 className="mt-3">{appt.pathway.replaceAll("_", " ")}</h2>
                <p className="patient-muted">
                  {[
                    appt.facility_name || t.assignedFacilityFallback,
                    appt.appointment_at
                      ? new Date(appt.appointment_at).toLocaleString(locale)
                      : null,
                    appt.outcome ? `${t.outcomePrefix} ${appt.outcome}` : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </section>
            ))}
            {!careDetail &&
              data.care.map((item) => (
                <section className="patient-panel" key={item.id}>
                  <span className="rounded-full bg-[#edf4f7] px-3 py-1 text-[10px] text-[#003e5e]">
                    {item.status}
                  </span>
                  <h2 className="mt-4">{item.title}</h2>
                  <p className="patient-muted">{item.detail}</p>
                  {item.at && (
                    <p className="mt-4 text-sm font-medium">
                      {new Date(item.at).toLocaleString(locale)}
                    </p>
                  )}
                </section>
              ))}
            {!careDetail &&
              data.referrals.map((item) => (
                <section className="patient-panel" key={item.id}>
                  <h2>{item.pathway.replaceAll("_", " ")}</h2>
                  <p className="patient-muted">
                    {item.status.replaceAll("_", " ")}
                  </p>
                </section>
              ))}
            {!(
              careDetail?.released_instructions.length ||
              careDetail?.appointments.length ||
              data.care.length ||
              data.referrals.length
            ) && (
              <section className="patient-panel">
                <p className="patient-muted">{t.careEmptyText}</p>
              </section>
            )}
          </>
        )}
        {tab === "profile" && (
          <>
            <AccountSecurityPanel lang={lang} />
            <section className="patient-panel">
              <span className="patient-avatar mb-4">
                {data.name.slice(0, 1)}
              </span>
              <h2>{data.name}</h2>
              <p className="patient-muted">
                {`${data.facility} · ${programme.name}`}
              </p>
              <p className="mt-4 text-xs leading-relaxed text-slate-500">
                {t.profileEnrolmentNote}
              </p>
            </section>
            <section className="patient-panel">
              <h2>{t.privacyTitle}</h2>
              <p className="patient-muted">{t.privacySubtitle}</p>
              {(
                [
                  "data_processing",
                  "wearable_ingestion",
                  "llm_synthesis",
                  "family_notification",
                  "hie_sharing",
                  "optional_channels",
                ] as const
              ).map((scope) => {
                const item = t.consents[scope];
                return (
                  <label key={scope} className="patient-history">
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium">
                        {item.title}
                      </span>
                      <span className="mt-1 block text-xs leading-relaxed text-slate-500">
                        {item.detail}
                      </span>
                    </span>
                    <input
                      aria-label={item.title}
                      type="checkbox"
                      role="switch"
                      checked={data.consents.includes(scope)}
                      disabled={busy}
                      className="h-5 w-5 shrink-0 accent-[#003e5e]"
                      onChange={(event) =>
                        void action(
                          () =>
                            api.post("/portal/consents", {
                              scope,
                              granted: event.target.checked,
                            }),
                          t.consentSavedSuccess,
                        )
                      }
                    />
                  </label>
                );
              })}
            </section>
            <button
              onClick={() => void logout().then(() => router.replace("/login"))}
              className="flex items-center gap-2 px-2 py-3 text-sm text-red-700"
            >
              <LogOut className="h-4 w-4" /> {t.signOut}
            </button>
          </>
        )}
        <footer className="py-4 text-center text-[10px] leading-relaxed text-slate-500">
          {t.footerPoweredBy}
          <br />
          {data.facility}
        </footer>
      </main>
      <nav className="patient-nav" aria-label={t.navAriaLabel}>
        {NAV_ITEMS.map((item) => (
          <button
            type="button"
            key={item.id}
            aria-current={tab === item.id ? "page" : undefined}
            onClick={() => {
              setTab(item.id);
              setMessage("");
              setError("");
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
            className={cn(
              "patient-nav-item",
              tab === item.id && "patient-nav-active",
            )}
          >
            <item.icon
              className="h-5 w-5"
              strokeWidth={tab === item.id ? 2 : 1.6}
            />
            <span>{t.nav[item.id]}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
