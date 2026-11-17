"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Bell,
  Brain,
  Check,
  ChevronRight,
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
import { api } from "@/lib/api";
import { RecovaMark } from "@/components/RecovaMark";
import { Button } from "@/components/ui/button";
import { cn, nowTimestampMs } from "@/lib/utils";

type Portal = {
  name: string;
  track: string;
  facility: string;
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
    issuer: string;
    severity: string;
  }[];
  acknowledged: string[];
};
const PROGRAMMES = {
  core: {
    name: "Recovery",
    title: "One day at a time.",
    description:
      "Make space for how you feel. Your care team is here for your recovery.",
    activity: "Your daily reflection",
    icon: Heart,
    prompt: "What has helped your recovery today?",
    subtitle: "A little reflection goes a long way.",
  },
  loop: {
    name: "Health Loop",
    title: "Your next step to better health.",
    description:
      "Keep your screening and follow-up care together, wherever life takes you.",
    activity: "Your wellbeing check",
    icon: ClipboardCheck,
    prompt: "Anything you would like your care team to know?",
    subtitle: "Keep your care team up to date.",
  },
  neuro: {
    name: "Brain Health",
    title: "A little practice. A clearer picture.",
    description:
      "Build a picture of your wellbeing over time with gentle cognitive activities.",
    activity: "Your memory activity",
    icon: Brain,
    prompt: "How did you feel during today's activity?",
    subtitle: "Take your time and find a quiet place.",
  },
  worksafe: {
    name: "WorkSafe",
    title: "Start your shift with you.",
    description:
      "A quick check on your energy, rest and wellbeing before the working day.",
    activity: "Your shift readiness",
    icon: ShieldCheck,
    prompt:
      "Tell your occupational-health team about your shift or any concerns.",
    subtitle: "A quick pause before your shift.",
  },
};
type Tab = "home" | "checkin" | "devices" | "care" | "profile";
const NAV = [
  { id: "home", label: "Home", icon: Home },
  { id: "checkin", label: "Check in", icon: Heart },
  { id: "devices", label: "Devices", icon: Watch },
  { id: "care", label: "My care", icon: Users },
  { id: "profile", label: "You", icon: ShieldCheck },
] as const;

function MemoryActivity({
  onSave,
}: {
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
  const [result, setResult] = useState("");
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
        setResult("Activity saved for your care team.");
      } catch {
        setResult("Could not save. Please try the activity again.");
      }
    }
  }
  return (
    <section className="patient-panel">
      <h2>Memory moments</h2>
      <p className="patient-muted">
        Watch three numbered tiles light up, then tap them in the same order.
        This is a practice activity. Your team can use the saved session when
        reviewing your progress.
      </p>
      <div aria-live="polite" className="my-4 text-sm font-semibold">
        {phase === "ready"
          ? "Ready when you are"
          : phase === "watch"
            ? "Watch the sequence"
            : phase === "repeat"
              ? `Your turn · ${answer.length} of 3`
              : result || "Saving your activity…"}
      </div>
      <div className="grid grid-cols-4 gap-3">
        {[0, 1, 2, 3].map((key) => (
          <button
            key={key}
            type="button"
            aria-label={`Tile ${key + 1}`}
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
          setResult("");
          setPhase("watch");
        }}
      >
        {" "}
        {phase === "done" ? "Try another activity" : "Start activity"}
      </Button>
    </section>
  );
}

export default function ParticipantPortal() {
  const { session, loading: authLoading, logout } = useAuth();
  const router = useRouter();
  const [data, setData] = useState<Portal | null>(null);
  const [tab, setTab] = useState<Tab>("home");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [mood, setMood] = useState(6);
  const [stress, setStress] = useState(3);
  const [craving, setCraving] = useState(2);
  const [reflection, setReflection] = useState("");
  const [crisis, setCrisis] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const submissionId = useRef(crypto.randomUUID());
  const [metric, setMetric] = useState("sleep_hours");
  const refresh = useCallback(async () => {
    try {
      setData(await api.get<Portal>("/portal/me"));
      setError("");
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Your care information could not be loaded.",
      );
    }
  }, []);
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
      setError(e instanceof Error ? e.message : "Please try again.");
    } finally {
      setBusy(false);
    }
  }
  if (!data)
    return (
      <main className="flex min-h-dvh items-center justify-center bg-[#f0f6f9] p-6">
        <div role="status" className="max-w-sm space-y-4 text-center">
          <RecovaMark size={40} className="mx-auto text-[#003e5e]" />
          <p>{error || "Getting your care space ready…"}</p>
          {error && (
            <>
              <Button onClick={() => void refresh()}>Try again</Button>
              <p>
                <a href="/login" className="text-sm underline">
                  Return to sign in
                </a>
              </p>
            </>
          )}
        </div>
      </main>
    );
  const programme =
    PROGRAMMES[data.track as keyof typeof PROGRAMMES] || PROGRAMMES.core;
  const latest = (code: string) =>
    data.observations.find((o) => o.metric === code);
  const todaysCheckin = data.checkins.find(
    (c) => new Date(c.at).toDateString() === new Date().toDateString(),
  );
  const samples = data.observations
    .filter((o) => o.metric === metric)
    .slice(0, 7)
    .reverse()
    .map((o) => ({
      day: new Date(o.at).toLocaleDateString(undefined, { weekday: "short" }),
      value: o.value,
    }));
  const processing = data.consents.includes("data_processing");
  const title = NAV.find((item) => item.id === tab)?.label;
  async function importFile(file?: File) {
    if (!file) return;
    await action(async () => {
      if (file.size > 1024 * 1024)
        throw new Error("Choose a file smaller than 1 MB.");
      const text = await file.text();
      const rows = text.trim().split(/\r?\n/);
      if (rows.shift()?.trim() !== "metric,value,unit,at")
        throw new Error(
          "Use the CSV header metric,value,unit,at. Download the example below.",
        );
      const readings = rows.filter(Boolean).map((row) => {
        const cells = row.split(",");
        if (cells.length !== 4 || !Number.isFinite(Number(cells[1])))
          throw new Error(
            "Every row needs metric, numeric value, unit and timestamp.",
          );
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
    }, "Your wearable readings were imported. You can now see them in your health signals.");
  }
  return (
    <div className="patient-app">
      <header className="patient-header">
        <a
          href="/portal"
          aria-label="Recova patient home"
          className="flex items-center gap-2 text-[#003e5e]"
        >
          <RecovaMark size={29} />
          <span className="text-xl font-bold tracking-tight">Recova</span>
        </a>
        <span className="hidden text-xs text-slate-500 sm:block">
          {data.facility}
        </span>
        <button
          type="button"
          aria-label="Your profile and privacy"
          onClick={() => setTab("profile")}
          className="patient-avatar"
        >
          {data.name.slice(0, 1)}
        </button>
      </header>
      <main className="patient-main" id="portal-content">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-widest text-slate-500">
              Your {programme.name} space
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">
              {tab === "home" ? `Hello, ${data.name}` : title}
            </h1>
          </div>
          <programme.icon
            className="h-6 w-6 text-[#003e5e]"
            strokeWidth={1.5}
          />
        </div>
        {data.synthetic && (
          <div className="mb-4 rounded-xl bg-[#e8f1f6] px-3 py-2 text-[11px] text-slate-600">
            Synthetic test account · {data.scenario}
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
              <p className="text-sm font-semibold">
                Your permission comes first
              </p>
              <p className="mt-1 text-xs leading-relaxed">
                Review how your care information is used before sending an
                activity or importing wearable data.
              </p>
              <button
                onClick={() => setTab("profile")}
                className="mt-2 text-xs font-semibold underline"
              >
                Review privacy choices
              </button>
            </div>
          </div>
        )}
        {tab === "home" && (
          <>
            <section className="patient-welcome">
              <div className="relative z-10 max-w-lg">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/60 px-3 py-1 text-[11px] font-medium text-[#32634f]">
                  <Wind className="h-3.5 w-3.5" /> A moment for your wellbeing
                </span>
                <h2 className="mt-5 text-[28px] font-semibold leading-tight tracking-tight">
                  {programme.title}
                </h2>
                <p className="mt-3 max-w-md text-sm leading-relaxed text-[#456858]">
                  {programme.description}
                </p>
                <Button onClick={() => setTab("checkin")} className="mt-6">
                  {todaysCheckin
                    ? "View today's check-in"
                    : data.track === "neuro"
                      ? "Explore your activities"
                      : "Let's check in"}
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
              <div aria-hidden className="patient-orbit">
                <Heart className="h-12 w-12" strokeWidth={1} />
              </div>
            </section>
            {data.track === "loop" && (
              <section className="patient-panel">
                <h2>Your screening snapshot</h2>
                <p className="patient-muted">
                  Results recorded by your facility. Your care team will explain
                  your follow-up.
                </p>
                <div className="mt-5 grid grid-cols-3 gap-2">
                  {[
                    { code: "hba1c", label: "HbA1c" },
                    { code: "bp_systolic", label: "Systolic BP" },
                    { code: "bp_diastolic", label: "Diastolic BP" },
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
                        {latest(item.code)?.unit || "Awaiting result"}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}
            {data.checkins[0]?.crisis && (
              <section className="patient-panel border-rose-200 bg-rose-50">
                <h2>Urgent support requested</h2>
                <p className="patient-muted">
                  An urgent-support request is in your check-in history. Contact
                  your facility directly for support. Use your local emergency
                  service in immediate danger.
                </p>
                <button
                  className="patient-text-button mt-3"
                  onClick={() => setTab("care")}
                >
                  View my care information <ArrowRight className="h-4 w-4" />
                </button>
              </section>
            )}
            <div className="patient-columns">
              <section className="patient-panel">
                <div className="flex items-center justify-between">
                  <h2>Today, at your pace</h2>
                  <span className="text-xs text-slate-500">
                    {new Date().toLocaleDateString(undefined, {
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
                    <programme.icon className="h-5 w-5" />
                  </span>
                  <span className="flex-1 text-left">
                    <strong className="block text-sm font-semibold">
                      {programme.activity}
                    </strong>
                    <span className="mt-1 block text-xs text-slate-500">
                      {todaysCheckin
                        ? "Check-in received today"
                        : programme.subtitle}
                    </span>
                  </span>
                  {todaysCheckin ? (
                    <Check className="h-5 w-5 text-green-700" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </button>
                <button
                  className="patient-task"
                  onClick={() => setTab("devices")}
                >
                  <span className="patient-icon">
                    <Watch className="h-5 w-5" />
                  </span>
                  <span className="flex-1 text-left">
                    <strong className="block text-sm font-semibold">
                      Your wearable signals
                    </strong>
                    <span className="mt-1 block text-xs text-slate-500">
                      {latest("sleep_hours")
                        ? "View readings and import updates"
                        : "Bring your readings into your care"}
                    </span>
                  </span>
                  <ChevronRight className="h-4 w-4" />
                </button>
              </section>
              <section className="patient-panel">
                <h2>Your care, connected</h2>
                <p className="patient-muted">{data.facility}</p>
                <div className="my-5 flex items-center gap-3">
                  <span className="patient-icon">
                    <Users className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold">
                      Your facility care team
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      Check your next care actions
                    </p>
                  </div>
                </div>
                <button
                  className="patient-text-button"
                  onClick={() => setTab("care")}
                >
                  Open my care plan <ArrowRight className="h-4 w-4" />
                </button>
              </section>
            </div>
            <section className="patient-panel">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2>Your health signals</h2>
                  <p className="patient-muted">
                    Your recent observations, at a glance
                  </p>
                </div>
                <label className="sr-only" htmlFor="signal">
                  Health signal
                </label>
                <select
                  id="signal"
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs"
                  value={metric}
                  onChange={(event) => setMetric(event.target.value)}
                >
                  <option value="sleep_hours">Sleep</option>
                  <option value="hrv_rmssd">Heart rate variability</option>
                  <option value="resting_hr">Resting heart rate</option>
                  <option value="steps">Steps</option>
                </select>
              </div>
              <div className="mt-5 grid grid-cols-3 gap-2">
                {[
                  { code: "sleep_hours", label: "Sleep" },
                  { code: "resting_hr", label: "Resting HR" },
                  { code: "steps", label: "Steps" },
                ].map((item) => (
                  <div key={item.code} className="rounded-2xl bg-[#f3f7f9] p-3">
                    <p className="text-[10px] text-slate-500">{item.label}</p>
                    <p className="mt-2 text-xl font-semibold tabular-nums">
                      {latest(item.code)?.value.toLocaleString(undefined, {
                        maximumFractionDigits: 1,
                      }) ?? "—"}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {latest(item.code)?.unit || "No readings yet"}
                    </p>
                  </div>
                ))}
              </div>
              {samples.length ? (
                <div
                  className="mt-5 h-40"
                  role="img"
                  aria-label={`Recent ${metric.replaceAll("_", " ")} observations`}
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
                  Your observations will appear here after your first import.
                </p>
              )}
              <p className="mt-3 text-[10px] leading-relaxed text-slate-500">
                {latest(metric)
                  ? `Latest reading ${new Date(latest(metric)!.at).toLocaleString()}`
                  : "Missing readings stay visible so your care team can interpret the available information."}
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
                      "Notice acknowledged.",
                    )
                  }
                >
                  {data.acknowledged.includes(notice.id)
                    ? "Acknowledged"
                    : "I have read this"}
                </Button>
              </section>
            ))}
          </>
        )}
        {tab === "checkin" && (
          <>
            {data.track === "neuro" && (
              <MemoryActivity
                onSave={async (result) => {
                  await api.post("/portal/activities", {
                    ...result,
                    request_id: crypto.randomUUID(),
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
                    const response = await api.post<{ emergency: boolean }>(
                      "/portal/check-ins",
                      {
                        mood,
                        stress,
                        craving: data.track === "core" ? craving : null,
                        text: reflection,
                        crisis,
                        request_id: submissionId.current,
                      },
                    );
                    setSubmitted(true);
                    return response;
                  },
                  crisis
                    ? "Your urgent support request has been recorded. Contact your facility directly for immediate support."
                    : "Your check-in has been received by your care team.",
                );
              }}
            >
              <h2>{programme.activity}</h2>
              <p className="patient-muted">{programme.subtitle}</p>
              {[
                {
                  label:
                    data.track === "worksafe"
                      ? "How ready do you feel for your shift?"
                      : "How are you feeling today?",
                  value: mood,
                  change: setMood,
                  low: "Low",
                  high: "Very well",
                },
                {
                  label: "How much stress are you feeling?",
                  value: stress,
                  change: setStress,
                  low: "Very little",
                  high: "A lot",
                },
                ...(data.track === "core"
                  ? [
                      {
                        label: "How strong are your cravings?",
                        value: craving,
                        change: setCraving,
                        low: "None",
                        high: "Strong",
                      },
                    ]
                  : []),
              ].map((field) => (
                <label
                  key={field.label}
                  className="my-6 block text-sm font-medium"
                >
                  {field.label}
                  <span className="float-right text-[#003e5e]">
                    {field.value}/10
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
              <label className="block text-sm font-medium">
                {programme.prompt}
                <textarea
                  value={reflection}
                  onChange={(event) => setReflection(event.target.value)}
                  maxLength={4000}
                  rows={4}
                  className="mt-3 w-full rounded-xl border border-slate-200 bg-[#f8fbfc] p-3 text-sm font-normal"
                  placeholder="Share what feels important to you…"
                />
              </label>
              <label className="my-5 flex items-start gap-3 rounded-xl bg-rose-50 p-4 text-sm">
                <input
                  className="mt-1 accent-[#003e5e]"
                  type="checkbox"
                  checked={crisis}
                  onChange={(event) => setCrisis(event.target.checked)}
                />
                <span>I need urgent support from my care team.</span>
              </label>
              <p className="mb-4 text-xs leading-relaxed text-slate-500">
                For immediate danger, use your local emergency service.
                Check-ins may take time to be reviewed.
              </p>
              <Button
                type="submit"
                className="w-full"
                disabled={busy || !processing || submitted}
              >
                {submitted
                  ? "Check-in received"
                  : busy
                    ? "Sending…"
                    : "Send to my care team"}
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
                  Start another check-in
                </button>
              )}
            </form>
            <section className="patient-panel">
              <h2>Recent check-ins</h2>
              {data.checkins.length ? (
                data.checkins.map((item) => (
                  <div key={item.id} className="patient-history">
                    <span className="patient-icon">
                      <Check className="h-4 w-4" />
                    </span>
                    <div>
                      <p className="text-sm font-medium">
                        {new Date(item.at).toLocaleString()}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Mood {item.mood}/10 · Stress {item.stress}/10
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
                <p className="patient-muted">
                  Your first check-in will appear here.
                </p>
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
              <h2>Bring your wearable into your care</h2>
              <p className="patient-muted">
                Sleep, heart rate, heart rate variability and activity can help
                your care team understand changes over time.
              </p>
              <div className="my-5 rounded-xl bg-[#edf4f7] p-4 text-xs leading-relaxed">
                Direct device connections need your facility’s configured
                provider integration. You can import an exported CSV below
                today.
              </div>
              {["Apple Health", "Fitbit", "Garmin"].map((provider) => (
                <div key={provider} className="patient-history">
                  <Watch className="h-5 w-5 text-[#003e5e]" />
                  <div className="flex-1">
                    <p className="text-sm font-semibold">{provider}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      Provider connection awaiting configuration
                    </p>
                  </div>
                  <span className="text-[10px] text-slate-500">
                    Unavailable
                  </span>
                </div>
              ))}
            </section>
            <section className="patient-panel">
              <h2>Import your readings</h2>
              <p className="patient-muted">
                Export your readings into the supported CSV format. Each reading
                is validated before saving.
              </p>
              <label className="my-5 flex min-h-28 cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-[#b5cdd9] bg-[#f5f9fb] p-5 text-center">
                <Upload className="h-6 w-6 text-[#003e5e]" />
                <span className="text-sm font-semibold">
                  Choose a wearable CSV
                </span>
                <span className="text-[11px] text-slate-500">
                  Up to 500 readings · maximum 1 MB
                </span>
                <input
                  className="mt-2 max-w-full text-xs"
                  aria-label="Wearable CSV file"
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
                Download example CSV <ArrowRight className="h-4 w-4" />
              </button>
              <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
                The example contains synthetic values. Use your own exported
                measurements for an actual import.
              </p>
              <button
                onClick={() => setTab("profile")}
                className="patient-text-button mt-5"
              >
                Manage wearable permission <ShieldCheck className="h-4 w-4" />
              </button>
            </section>
          </>
        )}
        {tab === "care" && (
          <>
            <section className="patient-panel">
              <h2>We are on your side</h2>
              <p className="patient-muted">
                Your care is provided by {data.facility}. This space keeps your
                next steps together.
              </p>
            </section>
            {data.care.map((item) => (
              <section className="patient-panel" key={item.id}>
                <span className="rounded-full bg-[#edf4f7] px-3 py-1 text-[10px] text-[#003e5e]">
                  {item.status}
                </span>
                <h2 className="mt-4">{item.title}</h2>
                <p className="patient-muted">{item.detail}</p>
                {item.at && (
                  <p className="mt-4 text-sm font-medium">
                    {new Date(item.at).toLocaleString()}
                  </p>
                )}
              </section>
            ))}
            {data.referrals.map((item) => (
              <section className="patient-panel" key={item.id}>
                <h2>{item.pathway.replaceAll("_", " ")}</h2>
                <p className="patient-muted">
                  {item.status.replaceAll("_", " ")}
                </p>
              </section>
            ))}
            {!data.care.length && !data.referrals.length && (
              <section className="patient-panel">
                <p className="patient-muted">
                  Your team will share your next care steps here.
                </p>
              </section>
            )}
          </>
        )}
        {tab === "profile" && (
          <>
            <section className="patient-panel">
              <span className="patient-avatar mb-4">
                {data.name.slice(0, 1)}
              </span>
              <h2>{data.name}</h2>
              <p className="patient-muted">
                {data.facility} · {programme.name}
              </p>
              <p className="mt-4 text-xs leading-relaxed text-slate-500">
                Your facility enrolment determines the care activities you see.
                Contact your facility if your enrolment needs updating.
              </p>
            </section>
            <section className="patient-panel">
              <h2>Your information, your choices</h2>
              <p className="patient-muted">
                Your decisions are recorded and checked when information is
                processed.
              </p>
              {[
                {
                  scope: "data_processing",
                  title: "Care-data processing",
                  detail:
                    "Allow your observations and check-ins to support your care programme.",
                },
                {
                  scope: "wearable_ingestion",
                  title: "Wearable readings",
                  detail:
                    "Allow wearable file imports to be stored with your care record.",
                },
                {
                  scope: "llm_synthesis",
                  title: "AI-assisted clinical summaries",
                  detail:
                    "Allow eligible information to be sent to a configured summary provider for clinician review.",
                },
                {
                  scope: "family_notification",
                  title: "Family notifications",
                  detail:
                    "Allow the facility's approved family-contact workflow.",
                },
                {
                  scope: "hie_sharing",
                  title: "Health information exchange",
                  detail:
                    "Allow approved health-information sharing integrations.",
                },
              ].map((item) => (
                <label key={item.scope} className="patient-history">
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
                    checked={data.consents.includes(item.scope)}
                    disabled={busy}
                    className="h-5 w-5 shrink-0 accent-[#003e5e]"
                    onChange={(event) =>
                      void action(
                        () =>
                          api.post("/portal/consents", {
                            scope: item.scope,
                            granted: event.target.checked,
                          }),
                        "Your privacy choice has been saved.",
                      )
                    }
                  />
                </label>
              ))}
            </section>
            <button
              onClick={() => void logout().then(() => router.replace("/login"))}
              className="flex items-center gap-2 px-2 py-3 text-sm text-red-700"
            >
              <LogOut className="h-4 w-4" /> Sign out
            </button>
          </>
        )}
        <footer className="py-4 text-center text-[10px] leading-relaxed text-slate-500">
          Your care space, powered by Recova
          <br />
          {data.facility}
        </footer>
      </main>
      <nav className="patient-nav" aria-label="Patient navigation">
        {NAV.map((item) => (
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
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
