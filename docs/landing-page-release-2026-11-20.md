# Public landing page release

The root URL now explains the Recova Engine and its Core, Loop, Neuro and WorkSafe programmes. Visitors stay on the public page instead of being redirected to login or operator setup. Signed-in users can explicitly open their own workspace from the navigation.

The page includes a responsive menu, keyboard-accessible programme explorer, conceptual engine workflow, shared public-health layer, trust information, patient invitation guidance, FAQs and contact links. Programme-specific calls to action preserve the selected programme in the existing onboarding form. The generated care image is illustrative; no patient records, testimonials or outcome statistics are invented.

## Deploy the frontend

From the existing H2S checkout on the VPS:

```bash
cd /var/www/recova-h2s
git pull --ff-only origin main
docker compose -f docker-compose.vps.yml --env-file .env.vps build frontend
docker compose -f docker-compose.vps.yml --env-file .env.vps up -d --no-deps frontend
```

This change adds no backend migration or application dependency. Preserve existing environment configuration. The configured public address is `https://h2s.recovahq.com`.

## Release checks

Verified locally on the production build: 30 frontend tests, TypeScript, ESLint, production build, and 10 browser checks passed. Responsive checks covered widths of 320, 390, 768, 1024 and 1440 pixels. The production site still requires the team's deployment.

- Open `/` without a session: the landing page must remain visible.
- Choose each programme; its description and participant experience must update.
- Choose Recova Loop and continue to onboarding: Loop must already be selected at the programme step.
- Check mobile menu, keyboard tab navigation, FAQ expansion and reduced motion.
- Confirm sign-in opens `/login` and the existing dashboard routing still applies.
- Verify the hero image loads and there is no horizontal overflow on mobile.

Styling uses prefixed global classes because the repository's existing Tailwind/Turbopack loader does not export CSS-module class mappings. The styles are scoped to the landing page and do not change dashboard components.

Design direction: Recova's existing navy, soft green and locally hosted Montserrat; a light theme, human imagery and restrained motion. Design-taste settings: DESIGN_VARIANCE 6, MOTION_INTENSITY 3, VISUAL_DENSITY 4, balancing a distinctive presentation with the clarity expected of healthcare software.
