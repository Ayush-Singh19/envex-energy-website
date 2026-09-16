# Envex Energy Website — Build Roadmap & Phase 1 Master Prompt

## The 3 phases

**Phase 1 — Landing Page (Foundation).** One high-impact home page that nails the look and feel: hero, why-us, services teaser, how-it-works, a lead CTA, footer. Placeholder branding (logo, colors) that's easy to swap later. Goal: something real to show the client and get sign-off on direction before building everything else.

**Phase 2 — Full Multi-Page Site.** Expand into About, Services, Contact, and any pages the client's materials call for (Projects/Products once they exist). Swap in real brand assets, credentials, and certificates as the client provides them. Wire the contact form to an actual inbox or CRM. Add SEO basics (meta tags, sitemap, Open Graph) and analytics.

**Phase 3 — Growth & Scale.** The parts that only make sense once the business has content to manage: a lightweight CMS (or admin-editable sections) for case studies, testimonials, and a blog as real projects accumulate; WhatsApp Business / CRM integration for lead handling; performance and accessibility polish; multi-language if needed. This phase is ongoing rather than a one-time build.

Each phase should ship as a working, reviewable site — not a half-finished attempt at everything at once.

---

## Master Prompt — Phase 1 (Landing Page)

Copy everything below into a fresh prompt when you're ready to start Phase 1.

```
You are acting as a senior product designer and front-end engineer who builds
high-end, industry-grade marketing websites for real businesses. Your taste
bar is Apple/Linear/Stripe-level polish, not template-level.

CONTEXT
Client: Envex Energy, a renewable energy (solar) startup.
Current site: an unfinished GoDaddy "Airo" template with a dark/teal theme —
being fully replaced.
Business reality: Envex Energy is early-stage. It has no public portfolio
numbers, case studies, or press yet. It currently generates business through
personal/offline connections and WhatsApp. The website's job is to look like
an established, trustworthy company and start generating inbound leads
directly — even though the company itself is still small.

HARD CONSTRAINT: Never invent statistics, client counts, project counts,
awards, testimonials, or "years in business" claims. If a section wants
a number Envex Energy doesn't have yet, write it without a number, or
frame it forward-looking, or leave a placeholder clearly marked as such.
This is non-negotiable — the client has explicitly said no fabricated claims.

DESIGN REFERENCE
Attached is a reference screenshot of a solar-energy landing page ("Ecovolt")
whose visual language to follow:
- Full-bleed hero photo/illustration of a home with rooftop solar panels
  under a bright blue sky
- Transparent nav bar overlaid on the hero image (logo left, links center,
  auth/CTA buttons right)
- Large centered white headline (2 lines), short subheadline, one white
  pill-shaped CTA button with a circular dark arrow icon
- Clean, bright, corporate feel — no dark/moody theme
Do not copy the "Ecovolt" name, logo, or exact copy — this is a style
reference only. Brand everything as Envex Energy.

SCOPE — PHASE 1 ONLY
Build a single, complete, production-quality HOME/LANDING PAGE. Do not build
other pages yet (no About/Services/Contact as separate routes) — a Phase 1
landing page can link to "#" or in-page anchors for now. Sections to include,
top to bottom:
1. Transparent header over the hero: logo, nav links (can be anchor links:
   Why Us / Services / How It Works / Contact), phone number, one primary
   CTA button ("Get a Free Quote" or similar — not "Sign up/Log in", this
   is a lead-gen site, not a SaaS product)
2. Hero: headline + subheadline + CTA button, matching the reference layout
3. "Why choose us" — 3 short trust-building points (certified installers,
   transparent pricing, end-to-end support, or similar) with no fake numbers
4. Services preview — 3 cards (e.g. Residential Solar, Commercial Solar,
   Maintenance) with 1-2 sentence descriptions, linking to a future
   /services page
5. How it works — a simple 3-4 step process (consultation → design →
   install → power up)
6. Final CTA banner — a strong, simple call to get a quote
7. Footer — logo, short tagline, quick links, contact details, copyright

BRAND
- Placeholder identity for now: build a clean wordmark/logo (text + simple
  icon, e.g. a bolt or leaf), and a blue/white solar-energy color palette
  inspired by the reference image (deep blue → sky blue gradient, white,
  a small warm accent color for icons/highlights). Structure colors as
  design tokens/CSS variables so they're trivial to swap once the client
  sends real brand assets.
- Do not use a stock photo of a house for the hero unless you have one that
  is genuinely free to use commercially — a well-crafted flat SVG/illustration
  of a house with solar panels is a perfectly good placeholder and avoids any
  licensing question. Real photography can replace it later.

TECHNICAL REQUIREMENTS
- Stack: Next.js (App Router) + TypeScript + Tailwind CSS
- Fully responsive: must look intentional at mobile (~390px), tablet, and
  desktop widths — not just scaled down
- Semantic HTML, accessible color contrast, keyboard-navigable nav and form
  elements, alt text on any meaningful imagery
- No placeholder Lorem Ipsum — write real, plausible marketing copy for a
  solar company, honest in tone, no exaggerated claims
- Keep the whole thing to clean, componentized code (Header, Footer, Hero,
  and section components) so Phase 2 can extend it without a rewrite
- No external font/image network dependencies that could fail to load in a
  restricted environment — self-contained system font stack or self-hosted
  fonts, inline SVG or embedded assets for graphics

DELIVERABLE
A working, buildable Next.js project with this single landing page, styled
to match the reference's visual energy but fully re-branded as Envex Energy,
ready to preview locally with `npm run dev`.
```

---

### Using this later

When you're ready for Phase 2, tell me what's changed (real logo/colors, any content the client has sent, which additional pages to prioritize) and I'll turn that into a Phase 2 master prompt the same way.
