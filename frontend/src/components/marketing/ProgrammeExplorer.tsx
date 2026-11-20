"use client";

import { useState, type KeyboardEvent } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Brain,
  ClipboardCheck,
  HeartHandshake,
  HardHat,
  Check,
} from "lucide-react";
import { useLanguage } from "@/hooks/useLanguage";
import styles from "./landing-styles";

// Public product descriptions, not records or simulated application data.
const programmes = [
  {
    id: "core",
    name: "Recova Core",
    label: "Recovery & rehabilitation",
    icon: HeartHandshake,
    title: "Stay connected to the recovery journey.",
    description:
      "Give rehabilitation and behavioural health teams a clearer view of life between appointments, with everyday reflections, personal signals and a connected follow-up pathway.",
    audience:
      "Recovery centres, rehabilitation providers and behavioural health teams.",
    experience:
      "Daily check-ins, reflections, consent choices and released care instructions.",
    capabilities: [
      "Mood, stress and craving check-ins",
      "Longitudinal signals and personal baselines",
      "Urgent red-flag escalation",
      "Clinician review and referral follow-up",
    ],
    note: "Continuity beyond the appointment",
    patientTitle: "One day at a time.",
    patientDescription:
      "Daily reflections. A connected care team. Support for the next step.",
  },
  {
    id: "loop",
    name: "Recova Loop",
    label: "Screening & care navigation",
    icon: ClipboardCheck,
    title: "Turn a screening result into a next step.",
    description:
      "Connect screening information to review, referral ownership and follow-up, so the care journey can continue after a result is recorded.",
    audience:
      "Primary care clinics, screening providers and care-navigation teams.",
    experience:
      "Screening results, assigned facilities, appointments and approved follow-up information.",
    capabilities: [
      "Screening results and clinical context",
      "Referral ownership and due dates",
      "Booking and consultation tracking",
      "Clinician-verified outcomes",
    ],
    note: "From insight to follow-through",
    patientTitle: "Your next step to better health.",
    patientDescription:
      "Results with context. Clear appointments. Follow-up that stays connected.",
  },
  {
    id: "neuro",
    name: "Recova Neuro",
    label: "Cognitive health",
    icon: Brain,
    title: "Understand change over time.",
    description:
      "Bring repeated cognitive activities and everyday health context into a longitudinal view for professional review, with attention to practice effects and assessment accessibility.",
    audience: "Cognitive health, neurology, memory and ageing-care teams.",
    experience:
      "Guided brain-health activities, completion receipts and results released by the care team.",
    capabilities: [
      "Repeated cognitive activities",
      "Personal baseline and drift tracking",
      "Sleep and assessment context",
      "Professional review and onward referral",
    ],
    note: "A longitudinal perspective",
    patientTitle: "A little practice. A clearer picture.",
    patientDescription:
      "Accessible activities and a care team that can follow changes over time.",
  },
  {
    id: "worksafe",
    name: "Recova WorkSafe",
    label: "Workforce health & readiness",
    icon: HardHat,
    title: "Put people at the centre of a safer shift.",
    description:
      "Connect pre-shift readiness and workplace conditions with occupational health oversight, while keeping supervisor views focused on privacy-protected department aggregates.",
    audience: "Employers, industrial worksites and occupational health teams.",
    experience:
      "A mobile readiness check, workplace safety guidance and a private connection to occupational care.",
    capabilities: [
      "Pre-shift readiness and fatigue checks",
      "Workplace heat and humidity context",
      "Privacy-protected supervisor heatmaps",
      "Occupational health interventions",
    ],
    note: "Readiness, with privacy built in",
    patientTitle: "Start your shift with you.",
    patientDescription:
      "A quick check-in. Clear guidance. Individual care stays with the health team.",
  },
];

export function ProgrammeExplorer() {
  const [selected, setSelected] = useState(0);
  const { t, tr } = useLanguage();
  const current = programmes[selected];
  const Icon = current.icon;
  function navigate(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = index;
    if (["ArrowRight", "ArrowDown"].includes(event.key))
      next = (index + 1) % programmes.length;
    else if (["ArrowLeft", "ArrowUp"].includes(event.key))
      next = (index - 1 + programmes.length) % programmes.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = programmes.length - 1;
    else return;
    event.preventDefault();
    setSelected(next);
    document.getElementById(`programme-tab-${programmes[next].id}`)?.focus();
  }
  return (
    <div className={styles.programmeExplorer}>
      <div
        className={styles.programmeTabs}
        role="tablist"
        aria-label={t("Recova programmes")}
      >
        {programmes.map((programme, index) => {
          const TabIcon = programme.icon;
          return (
            <button
              id={`programme-tab-${programme.id}`}
              key={programme.id}
              type="button"
              role="tab"
              aria-selected={selected === index}
              aria-controls="programme-panel"
              tabIndex={selected === index ? 0 : -1}
              onClick={() => setSelected(index)}
              onKeyDown={(event) => navigate(event, index)}
              className={selected === index ? styles.activeTab : undefined}
            >
              <TabIcon size={23} strokeWidth={1.6} aria-hidden="true" />
              <span>
                <strong>{t(programme.name)}</strong>
                <small>{t(programme.label)}</small>
              </span>
              <ArrowRight
                size={18}
                className={styles.tabArrow}
                aria-hidden="true"
              />
            </button>
          );
        })}
      </div>
      <div
        id="programme-panel"
        role="tabpanel"
        aria-labelledby={`programme-tab-${current.id}`}
        tabIndex={0}
        className={styles.programmePanel}
      >
        <div key={current.id} className={styles.programmeContent}>
          <div className={styles.programmeCopy}>
            <span className={styles.eyebrow}>{t(current.note)}</span>
            <h3>{t(current.title)}</h3>
            <p>{t(current.description)}</p>
            <ul>
              {current.capabilities.map((item) => (
                <li key={item}>
                  <Check size={16} aria-hidden="true" />
                  {t(item)}
                </li>
              ))}
            </ul>
            <Link
              className={styles.textLink}
              href={`/signup?programme=${current.id}`}
            >
              {tr(`Choose ${current.name}`, `اختر ${t(current.name)}`)}{" "}
              <ArrowRight size={17} aria-hidden="true" />
            </Link>
          </div>
          <div className={styles.programmeAside}>
            <div className={styles.programmeSymbol}>
              <Icon size={68} strokeWidth={1} aria-hidden="true" />
            </div>
            <span className={styles.miniLabel}>{t("THE PARTICIPANT EXPERIENCE")}</span>
            <h4>{t(current.patientTitle)}</h4>
            <p>{t(current.patientDescription)}</p>
            <div className={styles.audience}>
              <span>{t("Built for")}</span>
              <p>{t(current.audience)}</p>
              <span>{t("On the patient side")}</span>
              <p>{t(current.experience)}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
