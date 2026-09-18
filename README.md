# Envex Energy — Website

Single-page marketing site for Envex Energy (solar EPC), plus five solution detail views.

## Files

| File | What it is |
| --- | --- |
| `Envex Energy Landing.dc.html` | **Source.** Edit this one. Needs `support.js` beside it. |
| `envex-standalone-src.html` | Bundler input — same design with a preview thumbnail added. Generated from the source. |
| `Envex Energy Landing.html` | **Compiled standalone build.** Opens offline in any browser, no server or assets needed (~14 MB, media inlined). Do not hand-edit. |
| `support.js` | Runtime required by the source file. |
| `media/` | Logos, hero video/stills, About photo, Why-section consultation photo. |
| `frames/` | Working stills used while designing the hero. Not referenced by the site. |
| `uploads/` | Raw source material (reference PDF, hero video renders). Not referenced by the site. |

## Viewing

- Quickest: open `Envex Energy Landing.html` directly in a browser.
- To work on it: open `Envex Energy Landing.dc.html` (keep `support.js` and `media/` alongside).

## Page structure

Hero → About us (Vision / Mission / Core values) → Why Choose Us → Our Process → Our Solutions → Services → Contact → Footer.

**Why Choose Us** is a two-column editorial split: eyebrow + headline + consultation photo (with the Survey → Design → Install → Support process line overlaid) on the left; intro, "One team. One point of contact.", and the three differentiators on the right. The 01/02/03 rows run a blue → amber → green accent progression — color appears only on the numeral, icon, accent rule and hover tint.

**Our Solutions** is a deep-navy band; the five categories are rows in one translucent card, each with a line icon, capacity band and green hover bar.

**Our Solutions** has five cards — Rooftop Solar, On-Grid Systems, Hybrid Solar, Commercial & Industrial, Customized Solutions. Each "Explore →" opens a full detail view built from one shared template with five data sets:

Hero band → Overview → What's included (spec table) → How it works → What's inside every system (accordion of the 20 shared core components) → Cross-links to the other four → Talk-to-us CTA.

Detail content is driven by `Component.DETAIL` and `Component.CORE` in the logic class — add or edit a category there, not in the markup.

### Pricing

Deliberately **no ₹ figures anywhere.** The reference PDF is a GeM tendering classification whose own note says its ranges are indicative and must be verified against a real quotation. Pages show component type and capacity range only, with "as per system requirement" language, and drive to a quote. Publishing indicative pricing is a separate decision to confirm with the client first.

## Design notes

- Palette: navy `#05264a`, blue `#0b4f9c`, green `#6fb52f`, amber `#ffb84d` (Solutions band and detail heroes only), light surfaces `#f1f6fb` / `#ffffff`.
- Type: Clash Display / General Sans for headings, Manrope for body.
- Navy+amber is the Solutions treatment, not the whole site — detail pages use it for the hero band and closing CTA, light theme for everything between.
- Motion: scroll reveals via IntersectionObserver with a staggered inner rise on cards; nav tints past 40px; anchor scrolling is JS-eased with a 96px offset. The Why image reveals scale(1.04)→1, its process line draws stage by stage, and the trust dot pulses once. All respect `prefers-reduced-motion` except the anchor easing.
- Hover states that reach from a row into its children (Solutions rows, Why trust rows) live in the `<helmet>` block, since inline styles can't express parent-hover. Note `[data-accent]` is claimed by the About accent bars — the Why rows use `data-trust-accent` to avoid colliding with it.
- Spec tables are real `<table>` markup with `<th scope>` for screen readers, and collapse to stacked key-value cards under 640px.

## Outstanding

- Brand assets, contact details and the footer copyright line are placeholders pending client-supplied material.
- No portfolio numbers, client counts or years-in-business anywhere — the company has none yet and doesn't want fabricated claims.
- If this moves into the Next.js repo, the five detail views become real routes under `/solutions/`; they're in-page views here because this build is a single page.
