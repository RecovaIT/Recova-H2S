"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useLanguage } from "@/hooks/useLanguage";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { RecovaMark } from "@/components/RecovaMark";
import styles from "./landing-styles";

export function LandingNavigation() {
  const [open, setOpen] = useState(false);
  const { session } = useAuth();
  const { t, tr } = useLanguage();
  const workspace =
    session?.role === "patient"
      ? "/portal"
      : session?.role === "supervisor"
        ? "/worksafe"
        : session?.role === "authority_user"
          ? "/authority"
          : "/dashboard";
  return (
    <header className={styles.header}>
      <div className={styles.navInner}>
        <Link href="/" className={styles.brand} aria-label={t("Recova home")}>
          <RecovaMark size={34} />
          <span>
            {t("Recova")}
            <span className={styles.brandCaption}>
              {t("Health intelligence, connected.")}
            </span>
          </span>
        </Link>
        <nav aria-label={t("Main navigation")} className={styles.desktopNav}>
          <a href="#platform">{tr("The platform", "المنصة")}</a>
          <a href="#programmes">{tr("Programmes", "البرامج")}</a>
          <a href="#how-it-works">{tr("How it works", "كيف يعمل")}</a>
          <a href="#trust">{tr("Our approach", "نهجنا")}</a>
        </nav>
        <div className={styles.navActions}>
          <LanguageSwitcher variant="inline" />
          <Link className={styles.signIn} href={session ? workspace : "/login"}>
            {session ? tr("Open workspace", "افتح مساحة العمل") : tr("Sign in", "تسجيل الدخول")}
          </Link>
          <Link href="/register-organization" className={styles.navCta}>
            {tr("Get started", "ابدأ الآن")} <ArrowUpRight size={16} aria-hidden="true" />
          </Link>
        </div>
        <button
          className={styles.menuToggle}
          type="button"
          aria-expanded={open}
          aria-controls="landing-mobile-nav"
          aria-label={open ? t("Close menu") : t("Open menu")}
          onClick={() => setOpen(!open)}
        >
          {open ? <X /> : <Menu />}
        </button>
      </div>
      {open && (
        <nav
          id="landing-mobile-nav"
          aria-label={t("Mobile navigation")}
          className={styles.mobileNav}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setOpen(false);
              document
                .querySelector<HTMLButtonElement>(
                  '[aria-controls="landing-mobile-nav"]',
                )
                ?.focus();
            }
          }}
        >
          <a href="#platform" onClick={() => setOpen(false)}>
            {tr("The platform", "المنصة")}
          </a>
          <a href="#programmes" onClick={() => setOpen(false)}>
            {tr("Programmes", "البرامج")}
          </a>
          <a href="#how-it-works" onClick={() => setOpen(false)}>
            {tr("How it works", "كيف يعمل")}
          </a>
          <a href="#trust" onClick={() => setOpen(false)}>
            {tr("Our approach", "نهجنا")}
          </a>
          <div className="py-1">
            <LanguageSwitcher variant="inline" />
          </div>
          <Link href={session ? workspace : "/login"}>
            {session ? tr("Open workspace", "افتح مساحة العمل") : tr("Sign in", "تسجيل الدخول")}
          </Link>
          <Link href="/register-organization">
            {tr("Create a facility workspace", "أنشئ مساحة منشأتك")} <ArrowUpRight size={16} />
          </Link>
        </nav>
      )}
    </header>
  );
}
