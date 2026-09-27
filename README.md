# Envex Energy — Website

Marketing site for Envex Energy, a solar EPC company. Seven routes plus five
solution detail views.

## Technology

There is no framework, no package manager and no build step. The site is a
single HTML document interpreted at runtime by the Claude Design runtime.

| Layer | What it is |
| --- | --- |
| Runtime | `support.js` — the Claude Design template engine (`sc-for`, `sc-if`, `{{ }}` interpolation). Third-party; do not edit. |
| View layer | React 18, loaded from a CDN by `support.js`. No local install. |
| Markup, styles, logic | All three live in `src/index.html`. Styles are in a `<helmet><style>` block; behaviour is one `class Component extends DCLogic`. |
| Routing | Hash-based, implemented in that class. `#/about`, `#/solutions/hybrid`. |
| Images | `image-slot.js` — the Claude Design image-slot element. Third-party; do not edit. |

Path routing is not possible here: the site boots as a static `.dc.html` opened
over plain HTTP, so there is no server able to rewrite `/about` back onto the
file. That is why every route is a hash.

## Project structure

```
src/index.html                  Source of truth. Edit only this.
src/support.js                  Runtime copy, so src/ can be served directly.
src/image-slot.js               Image-slot copy, same reason.

Envex Energy Landing.dc.html    Generated. The file the runtime boots.
support.js  image-slot.js       Runtime, loaded by the generated file.
media/                          Production images. Everything here is referenced.

sync-dc.py                      Regenerates the generated file from the source.
docs/                           Project documentation.
```

Directories kept for history and **not referenced by the site**: `design/`
(an earlier snapshot of the generated file, together with the `public/media/`
copies it points at), `frames/` (video frame grabs), `uploads/` (working
material), `envex-standalone-src.html` and `.image-slots.state.json`.

### The two HTML files

`src/index.html` is the source. `Envex Energy Landing.dc.html` is generated
from it and is what actually boots — identical to the source minus the
bundler-thumbnail `<template>`.

They drifted silently once before, one two commits behind the other while both
looked current. `sync-dc.py` exists so that cannot happen again.

## Local development

No install step. Serve the repository root over HTTP — opening the file
directly with `file://` will not work, because the runtime fetches
`./support.js`.

```
python -m http.server 8080 --bind 127.0.0.1
```

Then open:

```
http://127.0.0.1:8080/Envex%20Energy%20Landing.dc.html
```

Edit `src/index.html`, then **run the sync after every edit**:

```
python sync-dc.py
```

Serving `src/index.html` directly also works, which is why `src/` carries its
own copies of the two runtime scripts.

## Production build

There is no build. `Envex Energy Landing.dc.html` is the deliverable; keeping
it in sync with the source is the whole build process.

A standalone single-file export (`Envex Energy Landing.html`, roughly 15 MB
with media inlined) can be regenerated through Claude Design when a shareable
offline copy is needed. It is an artifact, not source, and is not tracked.

## Environment variables

None. The site holds no keys, no tokens and no backend configuration.

The enquiry forms compose a `mailto:` message rather than posting anywhere, so
there is no endpoint to configure. Both submit handlers are written so a single
line can be swapped for a real `POST` when an endpoint exists:
`_submitEnquiry` and `_bSubmit` in `src/index.html`.

## Asset guidelines

Everything in `media/` is referenced by the site. Anything not referenced
belongs in `uploads/`, not here.

- lowercase, kebab-case, no spaces, no dates, no generator filenames
- named for what the image shows or where it is used, not for where it came
  from — `rooftop-consultation.jpeg`, not `why-consultation.jpeg`
- prefer WebP for photographs added from now on; existing JPEG and PNG assets
  are left as they are rather than re-encoded
- when renaming, update every reference in `src/index.html` and re-run
  `sync-dc.py`

## Content rules

The site states only what can be verified from company records. It carries no
project counts, installed capacity, customer numbers, years of experience,
certifications, awards, testimonials, performance percentages or coverage
claims. Please keep it that way — an honest page is worth more here than an
impressive one.

Registered company identifiers live in the `REGISTRY` constant in
`src/index.html`. CIN and GSTIN appear in the footer legal row.

## Git workflow

`main` is the trunk. Work happens on short-lived branches merged by pull
request:

- `feature/<name>` for site changes
- `chore/<name>` for repository and tooling work

Every commit that touches `src/index.html` must include the regenerated
`Envex Energy Landing.dc.html` produced by `sync-dc.py`. A commit with one but
not the other is the drift this repository has already seen once.

## Deployment

Not yet documented. The site is a static directory: the generated HTML,
`support.js`, `image-slot.js` and `media/` served from one root over HTTP.
Any static host will do. Update this section once the target is chosen.

## Known gaps

- The enquiry forms have no backend; they open the visitor's mail client.
- `media/hero-still.jpeg` is 6.2 MB and is the largest thing on the home
  page's critical path.
- No meta description, Open Graph tags or favicon.
