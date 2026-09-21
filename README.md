# Envex Energy — Website

Single-page marketing site for Envex Energy (solar EPC), plus five solution detail views.

## Files

| File | What it is |
| --- | --- |
| `Envex Energy Landing.dc.html` | **Source.** Edit this one. Needs `support.js` beside it. |
| `envex-standalone-src.html` | Bundler input — same design with a preview thumbnail added. Generated from the source. |
| `Envex Energy Landing.html` | **Generated standalone build — not tracked in git.** Opens offline in any browser, no server or assets needed (~15 MB, media inlined). Regenerate from the source via Claude Design when you need a shareable file; do not hand-edit. |
| `support.js` | Runtime required by the source file. |
| `media/` | Logos, hero video/stills, About photo, Why-section consultation photo. |
| `frames/` | Working stills used while designing the hero. Not referenced by the site. |
| `uploads/` | Raw source material (reference PDF, hero video renders). Not referenced by the site. |

## Viewing

- To work on it: serve the repo root over http and open `Envex Energy Landing.dc.html` (keep `support.js`, `image-slot.js` and `media/` alongside). It needs http rather than file://, and a network connection — the runtime pulls React from a CDN.

      python -m http.server 8080
      # http://127.0.0.1:8080/Envex%20Energy%20Landing.dc.html

- To share an offline copy: regenerate `Envex Energy Landing.html` from the source via Claude Design. It is a build artifact and is no longer tracked, so a fresh clone will not have it — and any stale copy on disk can silently lag the source.

## Page structure

Hero → About us (Vision / Mission / Core values) → Why Choose Us → Our Process → Our Solutions → Services → Contact → Footer.

**About us** is an editorial composition: oversized headline ("SOLAR" set in the logo green) paired with narrower support copy, the installation photo at native 3:2 with its caption outside the frame, then Vision / Mission / Core Values as three typographic columns — no cards, no dividers. Core Values pairs 01–04 into a two-column grid above 1000px with "Customer first" full-width, so the column balances Vision and Mission instead of running tall.

**Why Choose Us** is a two-column editorial split: eyebrow + headline + consultation photo (with the Survey → Design → Install → Support process line overlaid) on the left; intro, "One team. One point of contact.", and the three differentiators on the right. The 01/02/03 rows run a blue → amber → green accent progression — color appears only on the numeral, icon, accent rule and hover tint.

**Our Solutions** is a deep-navy band; the five categories are rows in one translucent card, each with a line icon, capacity band and green hover bar.

**Our Solutions** has five cards — Rooftop Solar, On-Grid Systems, Hybrid Solar, Commercial & Industrial, Customized Solutions. Each "Explore →" opens a full detail view built from one shared template with five data sets:

Hero band → Overview → What's included (spec table) → How it works → What's inside every system (accordion of the 20 shared core components) → Cross-links to the other four → Talk-to-us CTA.

Detail content is driven by `Component.DETAIL` and `Component.CORE` in the logic class — add or edit a category there, not in the markup.

### Pricing

Deliberately **no ₹ figures anywhere.** The reference PDF is a GeM tendering classification whose own note says its ranges are indicative and must be verified against a real quotation. Pages show component type and capacity range only, with "as per system requirement" language, and drive to a quote. Publishing indicative pricing is a separate decision to confirm with the client first.

## Design notes

- Palette: navy `#0b1f33` / `#05264a`, solar blue `#1769aa`, green `#5fae3b` (logo family; `#4f7a00` where small text needs contrast), amber `#c88a1e` / `#8a5605`, light surfaces `#f5f8fb` / `#ffffff`.
- Type: Clash Display / General Sans for headings, Manrope for body. The brand stack is set on `body` in the helmet — anything relying on inheritance falls back to Times New Roman without it.
- Navy+amber is the Solutions treatment, not the whole site — detail pages use it for the hero band and closing CTA, light theme for everything between.
- Motion: scroll reveals via IntersectionObserver with a staggered inner rise on cards; nav tints past 40px; anchor scrolling is JS-eased with a 96px offset. The Why image reveals scale(1.04)→1, its process line draws stage by stage, and the trust dot pulses once. All respect `prefers-reduced-motion` except the anchor easing.
- Hover states that reach from a row into its children (Solutions rows, Why trust rows) live in the `<helmet>` block, since inline styles can't express parent-hover. Note `[data-accent]` is claimed by the About accent bars — the Why rows use `data-trust-accent` to avoid colliding with it.
- Spec tables are real `<table>` markup with `<th scope>` for screen readers, and collapse to stacked key-value cards under 640px.

## Outstanding

- Brand assets, contact details and the footer copyright line are placeholders pending client-supplied material.
- No portfolio numbers, client counts or years-in-business anywhere — the company has none yet and doesn't want fabricated claims.
- If this moves into the Next.js repo, the five detail views become real routes under `/solutions/`; they're in-page views here because this build is a single page.
