# Spec: Bangladesh Design Refresh

## Overview
Step 11 swapped Spendly's currency symbol, name placeholders, and seed-data
descriptions to Bangladeshi context but was explicitly a content-only change,
not visual. This step adds a small, deliberate Bangladesh-flag-inspired visual
accent on top of the existing "warm, editorial, print-leaning" design system
documented in `.claude/skills/spendly-ui-designer/SKILL.md` — it does **not**
replace that system. It also fixes two loose ends the codebase audit for this
step turned up: a "rupee" string in the footer tagline that step 11's sweep
missed, and two pre-existing hardcoded-hex CSS violations directly adjacent to
the new work. No Bengali-script font is added — no Bengali text exists
anywhere in the app today, so that would be speculative scope.

## Depends on
- Step 11 (Bangladesh localization) — this step both extends it (new accent
  tokens) and fixes something it missed (the footer tagline)
- The existing CSS variable system in `static/css/style.css` (`:root` tokens,
  currently 14+ covering ink/paper/accent/danger/border/font/radius) and the
  design language it documents in `.claude/skills/spendly-ui-designer/SKILL.md`

## Routes
No new routes.

## Database changes
No database changes.

## Templates
- **Create:** none — the favicon is a static asset, not a template
- **Modify:** `templates/base.html`
  - Line 53: `<p class="footer-copy">Track every rupee. Own your finances.</p>`
    → `<p class="footer-copy">Track every taka. Own your finances.</p>`
  - Add one line inside `<head>` (before `{% block head %}{% endblock %}` at
    line 11): `<link rel="icon" type="image/svg+xml" href="{{ url_for('static', filename='favicon.svg') }}">`
    — this applies site-wide from the shared layout, no per-page changes needed

## Files to change
- `static/css/style.css`
  - Add four new tokens to the existing `:root` block, following the
    `--accent`/`--accent-light` pairing convention already used there:
    `--bd-green: #006a4e`, `--bd-green-light: #e5f5f0`,
    `--bd-red: #f42a41`, `--bd-red-light: #fde8ea`
  - Modify the existing `.footer` rule (line 528) to add
    `border-top: 3px solid var(--bd-green);` — this is the **only** place the
    new accent tokens are used in this step. `.footer` already has a dark
    background (`background: var(--ink)`), so the green top border reads as a
    clean accent line, not a palette change.
  - Fix two pre-existing hardcoded-hex lines directly adjacent to this change
    (lines 274-275): `.mock-bar-3 { background: #5b7fa6; }` and
    `.mock-bar-4 { background: #8b5e83; }` have no existing token to reference,
    so add two small new tokens for them — `--mock-blue: #5b7fa6`,
    `--mock-purple: #8b5e83` — and point both rules at `var(...)` instead of
    the raw hex.
- `templates/base.html` — tagline fix and favicon link, both above.
- `.claude/skills/spendly-ui-designer/SKILL.md` — add the four new tokens to
  its documented token list, and add a short note recording that the flag
  accent is used in exactly one place (the footer top border) — deliberately,
  not scattered — so a future change doesn't read the tokens' existence as
  license to apply them elsewhere without a new decision.

**Explicitly out of scope, left untouched:** `static/css/landing.css`,
`static/css/profile.css`, and `static/css/analytics.css` all have their own
pre-existing hardcoded-hex violations (mock traffic-light dots, category
colors, gradient stops) found during this step's codebase audit. None of them
are touched by this step's actual changes, so per the "only fix hex in files
this step already touches" decision, they are a known, separately-tracked gap
for a future cleanup — not silently forgotten, explicitly deferred. Likewise,
`style.css`'s own flash-message color blocks (two near-duplicate sets) and
`.auth-error`'s hex are pre-existing and unrelated to this step's actual
edits; only the two `.mock-bar` lines immediately next to this step's other
`style.css` changes are fixed here.

## Files to create
- `static/favicon.svg` — a minimal inline SVG: a rotated square (diamond)
  matching the silhouette of the existing `◈` brand mark used in the nav and
  footer (`templates/base.html`), filled with the literal hex `#006a4e` (the
  same value as `--bd-green`). SVG files are static assets, not page
  stylesheets, and cannot reference a CSS custom property defined in a
  separate `.css` file — this is the one legitimate exception to "never
  hardcode hex," and it is called out explicitly below so it isn't mistaken
  for a missed violation.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — not applicable, no DB work in this step
- Parameterised queries only — not applicable
- Passwords hashed with werkzeug — not applicable
- Use CSS variables — never hardcode hex values, **except** inside
  `static/favicon.svg` itself, per the explicit exception above
- All templates extend `base.html` — not applicable, no new templates
- DB logic goes in `database/queries.py`/`database/db.py` — not applicable
- Per-resource routes must enforce ownership — not applicable, no routes
- The new `--bd-green`/`--bd-red` tokens (and their `-light` pairs) are used
  in **exactly one place** in this step: the `.footer` top border. Do not
  apply them anywhere else (landing hero, buttons, badges) — if a future step
  wants a broader flag-color treatment, that is a new, explicitly-scoped
  decision, not a silent extension of this one.
- Do **not** touch `landing.css`, `profile.css`, or `analytics.css` — their
  pre-existing hex violations are explicitly deferred, per above.
- Do **not** add a Bengali-script font (e.g. Noto Sans Bengali) — no Bengali
  text exists in the app to render; this was explicitly decided out of scope.
- Do **not** modify `--accent`, `--accent-2`, or any other existing
  primary-palette token's value — the forest-green/cream editorial theme
  stays the primary look, unchanged.
- `.claude/skills/spendly-ui-designer/SKILL.md` must be updated in the same
  change to document the four new tokens and the footer-only usage decision —
  otherwise the skill's own "every colour is a `var(--token)`" checklist
  would silently go out of date the moment these tokens exist.

## Definition of done
- [ ] `static/css/style.css`'s `:root` includes `--bd-green`, `--bd-green-light`,
      `--bd-red`, `--bd-red-light`, `--mock-blue`, `--mock-purple`
- [ ] `.footer` (visible on every page, via `base.html`) has a 3px top border
      in `var(--bd-green)`
- [ ] `templates/base.html`'s footer tagline reads "Track every taka." not
      "Track every rupee."
- [ ] Browser tab shows the new diamond favicon in flag green, not a generic
      icon
- [ ] `.mock-bar-3` and `.mock-bar-4` reference `var(--mock-blue)` /
      `var(--mock-purple)`, not raw hex
- [ ] `git diff` confirms `landing.css`, `profile.css`, and `analytics.css`
      are untouched
- [ ] `git diff` confirms `--accent`, `--accent-2`, and every other
      pre-existing token's *value* is unchanged (only new tokens were added)
- [ ] `.claude/skills/spendly-ui-designer/SKILL.md` documents the four new
      tokens and the "footer-only" usage decision
- [ ] Full suite passes: `pytest` (no existing test asserts on footer/favicon
      content — this is a pure regression check, not new coverage)
- [ ] `python .claude/verify_setup.py` still passes
- [ ] Manual check: `/` (logged out) and `/profile` (logged in) both render
      the footer's green top border and the corrected tagline; the favicon
      renders correctly in a browser tab
