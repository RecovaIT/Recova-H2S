"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { RecovaMark } from "@/components/RecovaMark";
import styles from "./landing-styles";

export function LandingNavigation() {
  const [open, setOpen] = useState(false);
  const { session } = useAuth();
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
        <Link href="/" className={styles.brand} aria-label="Recova home">
          <RecovaMark size={34} />
          <span>
            Recova
            <span className={styles.brandCaption}>
              Health intelligence, connected.
            </span>
          </span>
        </Link>
        <nav aria-label="Main navigation" className={styles.desktopNav}>
          <a href="#platform">The platform</a>
          <a href="#programmes">Programmes</a>
          <a href="#how-it-works">How it works</a>
          <a href="#trust">Our approach</a>
        </nav>
        <div className={styles.navActions}>
          <Link className={styles.signIn} href={session ? workspace : "/login"}>
            {session ? "Open workspace" : "Sign in"}
          </Link>
          <Link href="/register-organization" className={styles.navCta}>
            Get started <ArrowUpRight size={16} aria-hidden="true" />
          </Link>
        </div>
        <button
          className={styles.menuToggle}
          type="button"
          aria-expanded={open}
          aria-controls="landing-mobile-nav"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen(!open)}
        >
          {open ? <X /> : <Menu />}
        </button>
      </div>
      {open && (
        <nav
          id="landing-mobile-nav"
          aria-label="Mobile navigation"
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
            The platform
          </a>
          <a href="#programmes" onClick={() => setOpen(false)}>
            Programmes
          </a>
          <a href="#how-it-works" onClick={() => setOpen(false)}>
            How it works
          </a>
          <a href="#trust" onClick={() => setOpen(false)}>
            Our approach
          </a>
          <Link href={session ? workspace : "/login"}>
            {session ? "Open workspace" : "Sign in"}
          </Link>
          <Link href="/register-organization">
            Create a facility workspace <ArrowUpRight size={16} />
          </Link>
        </nav>
      )}
    </header>
  );
}
