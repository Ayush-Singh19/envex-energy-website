# Envex Energy — Website

Marketing site for Envex Energy (solar EPC). Seven routes plus five solution detail views.

## Files

| File | What it is |
| --- | --- |
| `src/index.html` | **Source. Edit this one.** Markup, styles and the `Component` logic class in one file. |
| `Envex Energy Landing.dc.html` | **Generated — do not hand-edit.** The file the runtime actually boots. Same as the source minus the bundler-thumbnail `<template>`. |
| `sync-dc.py` | Regenerates the `.dc.html` from `src/index.html`. **Run after every edit.** |
| `Envex Energy Landing.html` | Generated standalone build, not tracked (~15 MB, media inlined). Regenerate via Claude Design when a shareable offline file is needed. |
| `support.js` / `image-slot.js` | The Claude Design runtime. Not ours; don't edit. |
| `media/` | Logos, hero still, section photography. |
| `frames/`, `uploads/` | Working material. Not referenced by the site. |

The two HTML files drifted silently in the past — one was two commits behind the other while both looked current. `sync-dc.py` exists so that cannot happen again:

    python sync-dc.py

## Viewing

Serve the repo root over http and open the `.dc.html` (not `src/index.html` — its relative `media/` paths resolve to `src/media/`, which does not exist):

    python -m http.server 8080
    # http://127.0.0.1:8080/Envex%20Energy%20Landing.dc.html

Needs http rather than `file://`, and a network connection — React and the fonts come from CDNs.

## Architecture

No router library, no build step, no component framework. One `<x-dc>` template plus one `class Component extends DCLogic`. The runtime (`support.js`) provides `sc-if`, `sc-for` and `{{ }}` interpolation, and renders through React 18 from unpkg.

### Routing

Routes are **hash-based** (`#/about`). Paths like `/about` would need a server able to rewrite them onto this file, and there isn't one — this is a static `.dc.html` opened directly.

| Route | Sections |
| --- | --- |
| `#/` | Hero, intro, solutions overview, six-stage process, CTA |
| `#/about` | About, Vision / Mission / Core values |
| `#/solutions` | The five categories |
| `#/solutions/<id>` | A category's detail view (`rooftop`, `ongrid`, `hybrid`, `ci`, `custom`) |
| `#/services` | Services hero, how we work, core services, journey, approach, what we handle, who we serve, FAQ |
| `#/why` | Why choose us, our process |
| `#/b2b` | Channel partners, four engagement types, how one starts |
| `#/contact` | Contact, quick contact, enquiry form, company information, CTA |

`Component.parseHash()` is the only place a URL is read; `_onHash` is the only place route state is written. A click, a Back press and a cold load with a deep link therefore all follow one path. The nav and footer sit outside the route blocks and render on every page.

Solution detail views are routes, not overlay state — so Back closes one, and a link to `#/solutions/hybrid` opens it directly.

To add a route: add it to `MENU` and `ROUTES`, wrap the sections in `<sc-if value="{{ isX }}">`, and return `isX` from `renderVals()`.

### Cross-route links

Use `this._goRoute('#/contact')`, or `this._goRoute('#/contact', 'enquiry')` to land on a specific block. Never write a bare `#element-id` into the URL — that replaces the route hash and the page falls back to Home on refresh.

### Content

All copy lives as static arrays on the logic class — `MENU`, `PILLARS`, `SOLUTIONS`, `DETAIL`, `CORE`, `HANDLE`, `SEGMENTS`, `B2B`, `FAQ`, `JOURNEY`, `REGISTRY`. Edit content there, not in the markup.

### Layout

Sections flow to their content. Only `#top` has a viewport-height floor. An earlier rule put `min-height: 100svh; align-content: center` on *every* desktop section, which was reasonable when the site was one continuous scroll but left ~350 px of symmetric dead space per section once each nav item became its own route. Rhythm comes from padding, not from a floor.

The page wrapper `<div>` must contain every section and the footer. A stray `</div>` once closed it two-thirds down the file, dropping `overflow-x: hidden`, `line-height` and the background from everything below.

## Constraints

- **No ₹ figures anywhere.** The reference PDF is a GeM tendering classification whose own note says its ranges are indicative and must be verified against a real quotation. Pages give component type and capacity range only.
- **No fabricated credibility.** No installation counts, MW figures, customer numbers, years in business, certifications, awards or client logos — the company has none to claim yet. Qualitative description only.
- Approval and liaisoning coverage is stated as Uttarakhand, which is verified. Do not broaden it.
- Brand assets, contact details and the footer copyright line are placeholders pending client-supplied material.

## Design notes

- Palette: navy `#0b1f33` / `#05264a`, solar blue `#1769aa` / `#0b4f9c`, green `#5fae3b` / `#8fd14f`, amber `#ffb84d` / `#c88a1e`, light surfaces `#f7fafd` / `#ffffff`.
- Type: Clash Display / General Sans for headings, Manrope for body. The brand stack is set on `body` in the helmet — anything relying on inheritance falls back to Times New Roman without it.
- Motion: scroll reveals via IntersectionObserver; accordions animate `grid-template-rows: 0fr → 1fr` so they expand to real height rather than a guessed `max-height`. All respect `prefers-reduced-motion`.
- Hover states that reach from a row into its children live in the `<helmet>` block, since inline styles can't express parent-hover.
- Spec tables are real `<table>` markup with `<th scope>`, collapsing to stacked cards under 640px.

## Known gaps

- The enquiry form hands off to `mailto:` with no backend, so anyone on webmail drops out of the funnel. The confirmation copy is honest ("Your enquiry has been prepared"), but leads are not captured anywhere.
- `media/hero-still.jpeg` is 6.2 MB and is the LCP element, set as a CSS background so it cannot take `srcset` or `fetchpriority`. Referenced media totals ~17 MB.
- No meta description, Open Graph tags, favicon or canonical URL.
- `media/` holds four hero `.mp4` files (~34 MB) that no `<video>` element references.
