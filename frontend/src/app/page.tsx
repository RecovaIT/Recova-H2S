import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Activity,
  Brain,
  Check,
  ClipboardCheck,
  Fingerprint,
  Globe2,
  HardHat,
  HeartHandshake,
  Layers3,
  LockKeyhole,
  MessageCircleHeart,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Waypoints,
} from "lucide-react";
import { RecovaMark } from "@/components/RecovaMark";
import { LandingNavigation } from "@/components/marketing/LandingNavigation";
import { ProgrammeExplorer } from "@/components/marketing/ProgrammeExplorer";
import "./landing.css";
import styles from "@/components/marketing/landing-styles";

export const metadata: Metadata = {
  title: "Recova | Connected intelligence. More human care.",
  description:
    "One shared health intelligence engine for recovery, screening, cognitive health and workforce readiness. Connect everyday signals, clinical review and follow-up with Recova.",
  alternates: { canonical: "https://h2s.recovahq.com" },
  openGraph: {
    title: "Recova | Care, one step ahead.",
    description:
      "One shared engine. Four care settings. A more connected health journey.",
    images: [
      {
        url: "https://h2s.recovahq.com/landing/connected-care.webp",
        width: 1440,
        height: 1080,
        alt: "Illustrative scene of a supportive care conversation",
      },
    ],
  },
};

export default function HomePage() {
  return (
    <div className={styles.landing}>
      <a className={styles.skipLink} href="#main-content">
        Skip to content
      </a>
      <LandingNavigation />
      <main id="main-content">
        <section
          className={`${styles.hero} ${styles.container}`}
          aria-labelledby="hero-title"
        >
          <div className={styles.heroCopy}>
            <span className={styles.eyebrow}>
              <span className={styles.smallDot} /> ANTICIPATORY HEALTH
              INTELLIGENCE
            </span>
            <h1 id="hero-title">
              Care, one
              <br />
              step <span>ahead.</span>
            </h1>
            <p className={styles.heroLead}>
              A clearer picture of health.
              <br />A closer connection to care.
            </p>
            <p className={styles.heroDescription}>
              One shared intelligence engine connects everyday health signals
              with the teams who can act. Across recovery, screening, cognitive
              health and the working day.
            </p>
            <div className={styles.heroActions}>
              <Link href="#programmes" className={styles.primaryButton}>
                Find your programme{" "}
                <ArrowUpRight size={19} aria-hidden="true" />
              </Link>
              <a href="#platform" className={styles.secondaryButton}>
                Explore the platform <ArrowDown size={17} aria-hidden="true" />
              </a>
            </div>
            <p className={styles.patientEntry}>
              Already part of Recova?{" "}
              <Link href="/login">
                Sign in to your space{" "}
                <ArrowRight size={14} aria-hidden="true" />
              </Link>
            </p>
          </div>
          <div className={styles.heroVisual}>
            <div className={styles.heroHalo} aria-hidden="true" />
            <div className={styles.heroPhoto}>
              <Image
                src="/landing/connected-care.webp"
                alt="Illustrative scene of a supportive conversation in a welcoming care setting"
                fill
                sizes="(max-width: 900px) 92vw, 46vw"
                preload
              />
            </div>
            <div className={styles.humanLabel}>
              <HeartHandshake size={18} strokeWidth={1.5} aria-hidden="true" />
              <span>
                Human connection.
                <br />
                <strong>At the centre of it all.</strong>
              </span>
            </div>
            <div className={styles.engineLabel}>
              <div className={styles.engineLogo}>
                <RecovaMark size={29} />
              </div>
              <div>
                <span>THE RECOVA ENGINE</span>
                <strong>
                  Connected signals.
                  <br />
                  Care with context.
                </strong>
              </div>
              <Waypoints size={29} strokeWidth={1.3} aria-hidden="true" />
            </div>
            <span className={styles.visualCaption}>
              A shared foundation. A personal care journey.
            </span>
          </div>
        </section>
        <div
          className={`${styles.scopeStrip} ${styles.container}`}
          aria-label="Four Recova programmes"
        >
          <p>
            Different care settings.
            <br />
            <strong>The same connected foundation.</strong>
          </p>
          <span>
            <HeartHandshake aria-hidden="true" />
            Recovery
          </span>
          <span>
            <ClipboardCheck aria-hidden="true" />
            Health screening
          </span>
          <span>
            <Brain aria-hidden="true" />
            Cognitive health
          </span>
          <span>
            <HardHat aria-hidden="true" />
            Workforce readiness
          </span>
        </div>
        <section
          id="platform"
          className={`${styles.section} ${styles.container} ${styles.platformSection}`}
          aria-labelledby="platform-title"
        >
          <div className={styles.platformCopy}>
            <span className={styles.eyebrow}>
              THE SHARED INTELLIGENCE LAYER
            </span>
            <h2 id="platform-title">
              Different signals.
              <br />
              One connected view.
            </h2>
            <p>
              Health happens between appointments, across different places and
              throughout everyday life. Recova brings that context into a
              structured pathway for the people delivering care.
            </p>
            <p>
              The Recova Engine is the common foundation. Each programme applies
              it to a different care setting, with its own workspace and
              participant experience.
            </p>
            <a className={styles.textLink} href="#how-it-works">
              Meet the six-stage engine{" "}
              <ArrowRight size={17} aria-hidden="true" />
            </a>
          </div>
          <figure
            className={styles.architecture}
            aria-label="Conceptual platform architecture: consented health signals pass through the shared Recova Engine to clinician review and connected follow-up"
          >
            <div className={styles.architectureTop}>
              <span className={styles.miniLabel}>
                EVERYDAY SIGNALS, WITH CONTEXT
              </span>
              <div className={styles.signalChips}>
                <span>
                  <MessageCircleHeart size={16} />
                  Check-ins
                </span>
                <span>
                  <Activity size={16} />
                  Wearable data
                </span>
                <span>
                  <ClipboardCheck size={16} />
                  Screening
                </span>
                <span>
                  <Brain size={16} />
                  Cognitive activities
                </span>
              </div>
            </div>
            <div className={styles.connector} aria-hidden="true">
              <ArrowDown size={19} />
            </div>
            <div className={styles.coreEngine}>
              <RecovaMark size={44} />
              <div>
                <strong>Recova Engine</strong>
                <span>Consent-aware. Contextual. Clinician-led.</span>
              </div>
              <Layers3 size={23} strokeWidth={1.4} aria-hidden="true" />
            </div>
            <div className={styles.connector} aria-hidden="true">
              <ArrowDown size={19} />
            </div>
            <div className={styles.architectureOutput}>
              <span>
                <Stethoscope size={20} />
                Professional review
              </span>
              <ArrowRight size={18} aria-hidden="true" />
              <span>
                <Waypoints size={20} />
                Connected follow-up
              </span>
            </div>
            <figcaption>
              How the platform connects information to a care workflow.
            </figcaption>
          </figure>
        </section>
        <section
          id="programmes"
          className={`${styles.programmesSection} ${styles.section}`}
          aria-labelledby="programmes-title"
        >
          <div className={styles.container}>
            <div className={styles.sectionHeading}>
              <div>
                <span className={styles.eyebrow}>
                  FOUR PROGRAMMES. ONE RECOVA.
                </span>
                <h2 id="programmes-title">
                  Built around the care
                  <br />
                  you deliver.
                </h2>
              </div>
              <p>
                Choose one programme when your facility joins. Your team gets a
                focused workspace. Participants get the experience that fits
                their enrolment.
              </p>
            </div>
            <ProgrammeExplorer />
            <div className={styles.programmeFootnote}>
              <Fingerprint size={18} aria-hidden="true" />
              <p>
                One platform and one login. Additional programmes follow your
                facility’s approval and enrolment process.
              </p>
            </div>
          </div>
        </section>
        <section
          id="how-it-works"
          className={`${styles.section} ${styles.container}`}
          aria-labelledby="workflow-title"
        >
          <div className={styles.sectionHeading}>
            <div>
              <span className={styles.eyebrow}>
                FROM SIGNAL TO FOLLOW-THROUGH
              </span>
              <h2 id="workflow-title">
                Intelligence with a<br />
                clear path to action.
              </h2>
            </div>
            <p>
              A six-stage workflow connects consent, safety, context and review.
              Deterministic scoring and optional AI summaries remain separate,
              with clinical decisions in professional hands.
            </p>
          </div>
          <ol className={styles.workflow}>
            <li>
              <span>01</span>
              <LockKeyhole aria-hidden="true" />
              <h3>Permission first</h3>
              <p>Check consent and which information can be used.</p>
            </li>
            <li>
              <span>02</span>
              <ShieldCheck aria-hidden="true" />
              <h3>Safety upfront</h3>
              <p>
                Surface urgent red flags through the configured escalation
                pathway.
              </p>
            </li>
            <li>
              <span>03</span>
              <Layers3 aria-hidden="true" />
              <h3>Context together</h3>
              <p>Bring available observations into a longitudinal picture.</p>
            </li>
            <li>
              <span>04</span>
              <Activity aria-hidden="true" />
              <h3>Personal signals</h3>
              <p>Compare change with personal baselines and defined rules.</p>
            </li>
            <li>
              <span>05</span>
              <Sparkles aria-hidden="true" />
              <h3>Explain for review</h3>
              <p>
                Optional, configured AI supports professional interpretation.
              </p>
            </li>
            <li>
              <span>06</span>
              <Waypoints aria-hidden="true" />
              <h3>Follow through</h3>
              <p>
                Connect approved referrals, appointments and outcome review.
              </p>
            </li>
          </ol>
          <div className={styles.reviewNote}>
            <Stethoscope size={21} aria-hidden="true" />
            <p>
              <strong>
                More context for professionals. More clarity for people.
              </strong>{" "}
              Recova supports care decisions; it does not replace a qualified
              clinician or emergency services.
            </p>
          </div>
        </section>
        <section
          className={`${styles.publicHealth} ${styles.container}`}
          aria-labelledby="public-health-title"
        >
          <div className={styles.publicHealthArt} aria-hidden="true">
            <div>
              <Globe2 size={82} strokeWidth={0.8} />
            </div>
            <span className={styles.healthOrbitOne} />
            <span className={styles.healthOrbitTwo} />
            <span className={styles.healthOrbitDot} />
            <span className={styles.healthOrbitDotTwo} />
          </div>
          <div>
            <span className={styles.eyebrow}>
              CONNECTED BEYOND A SINGLE FACILITY
            </span>
            <h2 id="public-health-title">
              Individual care.
              <br />A shared public-health layer.
            </h2>
            <p>
              Public-health coordination sits across the programmes. Authorised
              authorities can issue scoped notices, and eligible participants
              can receive and acknowledge them in their own space.
            </p>
            <p>
              Population reporting uses aggregation and privacy controls. A
              shared platform connects the response while role and facility
              boundaries govern access.
            </p>
            <span className={styles.inlineNote}>
              <Check size={16} />
              Shared coordination, with clear access boundaries
            </span>
          </div>
        </section>
        <section
          id="trust"
          className={`${styles.section} ${styles.container}`}
          aria-labelledby="trust-title"
        >
          <div className={styles.sectionHeading}>
            <div>
              <span className={styles.eyebrow}>A THOUGHTFUL FOUNDATION</span>
              <h2 id="trust-title">
                Trust is part
                <br />
                of the architecture.
              </h2>
            </div>
            <p>
              Connected care needs clear permissions, accountable workflows and
              an honest view of what each integration can do.
            </p>
          </div>
          <div className={styles.trustGrid}>
            <article>
              <LockKeyhole aria-hidden="true" />
              <h3>Permission with purpose</h3>
              <p>
                Separate choices for care processing, wearable information,
                external AI and health information exchange.
              </p>
            </article>
            <article>
              <Fingerprint aria-hidden="true" />
              <h3>The right view for each role</h3>
              <p>
                Facility-scoped access, private participant spaces and
                privacy-protected supervisor reporting.
              </p>
            </article>
            <article>
              <ClipboardCheck aria-hidden="true" />
              <h3>Review you can trace</h3>
              <p>
                Recorded clinical sign-off, referral history and a distinction
                between calculated signals and AI-supported summaries.
              </p>
            </article>
            <article>
              <Waypoints aria-hidden="true" />
              <h3>Connections with clarity</h3>
              <p>
                Device and external service availability depend on supported
                integrations and provider configuration.
              </p>
            </article>
          </div>
        </section>
        <section
          className={`${styles.faqSection} ${styles.container}`}
          aria-labelledby="faq-title"
        >
          <div>
            <span className={styles.eyebrow}>A LITTLE MORE CLARITY</span>
            <h2 id="faq-title">
              Good questions.
              <br />
              Clear answers.
            </h2>
            <p>Something else on your mind?</p>
            <a
              className={styles.textLink}
              href="mailto:info@recovahq.com?subject=Recova%20platform%20enquiry"
            >
              Talk to the Recova team <ArrowUpRight size={17} />
            </a>
          </div>
          <div className={styles.faqList}>
            <details>
              <summary>
                Is Recova one platform or four separate products?<span>+</span>
              </summary>
              <p>
                Recova has one shared backend engine and a common login. Core,
                Loop, Neuro and WorkSafe apply that engine to different care
                needs, with focused team dashboards and participant activities.
              </p>
            </details>
            <details>
              <summary>
                How does a facility get started?<span>+</span>
              </summary>
              <p>
                Create a facility workspace, choose one primary programme and
                complete the guided onboarding. Additional programmes can be
                requested through the platform approval process.
              </p>
            </details>
            <details>
              <summary>
                How do patients and workers join?<span>+</span>
              </summary>
              <p>
                Your facility registers your participant record and sends a
                private invitation. New users set their own password; existing
                users sign in and accept the facility invitation. Your enrolment
                determines the activities you see.
              </p>
            </details>
            <details>
              <summary>
                How does public health fit into each programme?<span>+</span>
              </summary>
              <p>
                The shared public-health layer supports scoped notices and
                eligible recipient acknowledgements across programmes. Authority
                publishing and reporting require appropriate roles and assigned
                scope.
              </p>
            </details>
            <details>
              <summary>
                Does the platform make clinical decisions automatically?
                <span>+</span>
              </summary>
              <p>
                The platform organises signals, applies defined scoring rules
                and can generate an optional AI summary when configured and
                permitted. Clinical review and care decisions remain with
                authorised professionals.
              </p>
            </details>
            <details>
              <summary>
                Can I connect a wearable?<span>+</span>
              </summary>
              <p>
                Participant spaces support wearable file imports where enabled
                and consented. Direct device connections depend on supported
                providers and configuration. Your care team can confirm what is
                available for your programme.
              </p>
            </details>
          </div>
        </section>
        <section
          className={`${styles.finalCta} ${styles.container}`}
          aria-labelledby="cta-title"
        >
          <div>
            <span className={styles.eyebrow}>A MORE CONNECTED NEXT STEP</span>
            <h2 id="cta-title">
              Bring the bigger picture
              <br />
              into everyday care.
            </h2>
            <p>Start with your care setting. Build on one shared foundation.</p>
            <div className={styles.heroActions}>
              <Link
                className={styles.primaryButton}
                href="/register-organization"
              >
                Create a facility workspace <ArrowUpRight size={18} />
              </Link>
              <a
                className={styles.textLink}
                href="mailto:info@recovahq.com?subject=Recova%20platform%20enquiry"
              >
                Let’s talk <ArrowRight size={17} />
              </a>
            </div>
            <p className={styles.patientEntry}>
              Joining as a patient or worker?{" "}
              <Link href="/login">Sign in with your invitation account.</Link>
            </p>
          </div>
          <div className={styles.ctaMark} aria-hidden="true">
            <RecovaMark size={205} />
          </div>
        </section>
      </main>
      <footer className={`${styles.footer} ${styles.container}`}>
        <div className={styles.footerTop}>
          <div>
            <Link className={styles.brand} href="/" aria-label="Recova home">
              <RecovaMark size={31} />
              <span>Recova</span>
            </Link>
            <p>
              Connected intelligence.
              <br />
              More human care.
            </p>
          </div>
          <nav aria-label="Footer platform links">
            <span>EXPLORE</span>
            <a href="#platform">The platform</a>
            <a href="#programmes">Our programmes</a>
            <a href="#how-it-works">How it works</a>
          </nav>
          <nav aria-label="Footer access links">
            <span>YOUR NEXT STEP</span>
            <Link href="/register-organization">Create a workspace</Link>
            <Link href="/login">Patient & team sign in</Link>
            <a href="mailto:info@recovahq.com">info@recovahq.com</a>
          </nav>
          <div className={styles.footerPurpose}>
            <span>BUILT AROUND PEOPLE</span>
            <p>
              From individual wellbeing to shared population health. One
              connected foundation.
            </p>
            <a
              href="https://recovahq.com"
              target="_blank"
              rel="noopener noreferrer"
            >
              About Recova <ArrowUpRight size={15} />
            </a>
          </div>
        </div>
        <div className={styles.footerBottom}>
          <span>© 2026 Recova Health Systems.</span>
          <span>
            Recovery · Screening · Cognitive health · Workforce readiness
          </span>
          <a href="#main-content">Back to top ↑</a>
        </div>
      </footer>
    </div>
  );
}
