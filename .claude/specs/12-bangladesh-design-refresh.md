# Spec: Bangladesh Design Refresh

## Overview
This step replaces Spendly's **primary** color palette with a Bangladesh-rooted
one, anchored on the national flag's bottle green (`#006A4E`) and red
(`#F42A41`). This supersedes an earlier, narrower draft of this same spec that
added the flag colors only as a small footer accent while keeping the existing
forest-green/ochre palette as primary — that decision is reversed here. The
current palette (`--paper #f7f6f3`, `--accent #1a472a` forest green, `--accent-2
#c17f24` ochre, DM Serif Display + DM Sans) is being *replaced*, not
supplemented. Bottle green sits close enough to the existing forest green that
the shift reads as a refinement of the same editorial language, not a jarring
rebrand; flag red becomes the secondary accent in place of ochre.

Because the app already uses CSS custom properties consistently for `--accent`/
`--accent-2` across `profile.css`, `landing.css`, and `analytics.css`, changing
their **values** in one place (`style.css`'s `:root`) cascades everywhere those
tokens are referenced — this is a small, contained token edit, not a
1,592-line rewrite. Pre-existing hardcoded-hex colors that are *not* derived
from `--accent`/`--accent-2` (category colors in `profile.css`, decorative mock
UI in `landing.css`) are untouched by this step, same as before.

**This spec proposes three palette options with swatches below. Implementation
does not begin until one is chosen** — see "Decision needed," which resolves
this before the spec is finalized.

## Palette options

### Option A — Direct flag swap (closest to the flag, safest shift)
<table><tr>
<td><div style="width:60px;height:30px;background:#006A4E;border:1px solid #ccc"></div><code>#006A4E</code><br>accent</td>
<td><div style="width:60px;height:30px;background:#E3F3EC;border:1px solid #ccc"></div><code>#E3F3EC</code><br>accent-light</td>
<td><div style="width:60px;height:30px;background:#F42A41;border:1px solid #ccc"></div><code>#F42A41</code><br>accent-2</td>
<td><div style="width:60px;height:30px;background:#FDE6E8;border:1px solid #ccc"></div><code>#FDE6E8</code><br>accent-2-light</td>
</tr></table>

`--paper`/`--ink` unchanged. Bottle green stays primary (same role forest green
plays today), flag red replaces ochre as secondary. The most literal reading of
"bottle green close to #1a472a, red as accent" — minimal risk, easiest to
verify as coherent rather than jarring.

### Option B — Red-forward (flag red leads, green supports)
<table><tr>
<td><div style="width:60px;height:30px;background:#F42A41;border:1px solid #ccc"></div><code>#F42A41</code><br>accent</td>
<td><div style="width:60px;height:30px;background:#FDE6E8;border:1px solid #ccc"></div><code>#FDE6E8</code><br>accent-light</td>
<td><div style="width:60px;height:30px;background:#006A4E;border:1px solid #ccc"></div><code>#006A4E</code><br>accent-2</td>
<td><div style="width:60px;height:30px;background:#E3F3EC;border:1px solid #ccc"></div><code>#E3F3EC</code><br>accent-2-light</td>
</tr></table>

Swaps which color leads: red becomes the primary accent (buttons, links, active
states), green secondary. Punchier and more visually assertive — red draws the
eye first, which is a common flag-forward branding move — but a bigger
departure from the current calm, forest-green-led feel. Still only the two flag
colors, no new hues.

### Option C — Considered redesign (softened tones, paper shifts too)
<table><tr>
<td><div style="width:60px;height:30px;background:#f8f4ec;border:1px solid #ccc"></div><code>#f8f4ec</code><br>paper</td>
<td><div style="width:60px;height:30px;background:#00614a;border:1px solid #ccc"></div><code>#00614a</code><br>accent</td>
<td><div style="width:60px;height:30px;background:#e2f0ea;border:1px solid #ccc"></div><code>#e2f0ea</code><br>accent-light</td>
<td><div style="width:60px;height:30px;background:#d63447;border:1px solid #ccc"></div><code>#d63447</code><br>accent-2</td>
<td><div style="width:60px;height:30px;background:#fbe6e8;border:1px solid #ccc"></div><code>#fbe6e8</code><br>accent-2-light</td>
</tr></table>

Softens both flag colors slightly (deeper green, warmer red) so they sit more
comfortably against a slightly warmer, more jute/khadi-toned paper (`#f8f4ec`
vs today's `#f7f6f3`). The most cohesive-feeling option and arguably the least
jarring in practice, but touches one more token (`--paper`) than A or B, and is
the hardest of the three to eyeball-verify against "still coherent" without
actually rendering it.

**Decision: Option A is chosen.** `--accent: #006A4E`, `--accent-light: #E3F3EC`,
`--accent-2: #F42A41`, `--accent-2-light: #FDE6E8`. `--paper`/`--ink` are
unchanged. Every value below reflects this choice.

## Depends on
- Step 11 (Bangladesh localization) — content-only; this step is the visual
  counterpart
- The existing CSS variable system in `static/css/style.css` (`:root` tokens)
  and its documentation in `.claude/skills/spendly-ui-designer/SKILL.md`

## Routes
No new routes.

## Database changes
No database changes.

## Templates
- **Create:** none
- **Modify:** `templates/base.html`
  - Footer tagline (line 53): `"Track every rupee. Own your finances."` →
    `"Track every taka. Own your finances."` — a leftover from step 11's sweep
  - Add a favicon link in `<head>` (before `{% block head %}{% endblock %}`):
    `<link rel="icon" type="image/svg+xml" href="{{ url_for('static', filename='favicon.svg') }}">`
  - **Fonts are not changing.** DM Serif Display + DM Sans stay exactly as
    loaded today. No option above calls for a different typeface, so the
    Google Fonts `<link>` in `base.html` is untouched. Flagging this
    explicitly because it's the one site-wide external dependency and the
    hard requirements call out that it *would* need to change if fonts did.

## Files to change
- `static/css/style.css`
  - Redefine the existing tokens in `:root` (Option A, chosen above):
    `--accent: #006A4E`, `--accent-light: #E3F3EC`, `--accent-2: #F42A41`,
    `--accent-2-light: #FDE6E8`. `--paper`/`--ink` stay unchanged. This is a
    **value change on existing tokens**, not new tokens — the earlier draft's
    separate `--bd-green`/`--bd-red` tokens are dropped; they're redundant
    once the flag colors are the primary accent itself.
  - Add `.footer { border-top: 3px solid var(--accent); }` — uses the
    (now flag-colored) primary accent directly, no separate token needed.
  - Fix two pre-existing hardcoded-hex lines unrelated to the accent swap but
    adjacent to it (lines 274-275): `.mock-bar-3 { background: #5b7fa6; }` and
    `.mock-bar-4 { background: #8b5e83; }` → new tokens `--mock-blue: #5b7fa6`,
    `--mock-purple: #8b5e83`, referenced via `var(...)`.
  - `--danger` (`#c0392b`, error/delete-confirmation red) is **unchanged** —
    it's a semantic status color, not a brand color, and is a visibly
    different shade from the new flag red, so the two won't be confused.
- `templates/base.html` — tagline fix and favicon link, both above.
- `.claude/skills/spendly-ui-designer/SKILL.md` — **required in the same
  change**, per the hard requirement: it hardcodes today's palette
  (`--paper`/`--accent`/`--accent-2` values and the "forest green, ochre"
  description), and `spendly-quality-reviewer` reads it as ground truth before
  judging CSS. Update the documented hex values to the chosen option, and
  reword the palette description away from "forest green, ochre."

**Still out of scope, untouched:** `landing.css`, `profile.css`, and
`analytics.css`'s own pre-existing hardcoded-hex violations (category colors,
decorative mock UI, gradients) — none of them are `--accent`/`--accent-2`
references, so they don't cascade from this token change, and fixing them
outright is a separate, larger cleanup this spec does not attempt.

## Files to create
- `static/favicon.svg` — a small diamond shape (matching the existing `◈`
  brand mark) filled with the literal hex of the chosen option's `--accent`
  value. SVG files can't reference a CSS custom property from a separate
  stylesheet, so this is the one legitimate hardcoded-hex exception, same as
  the earlier draft.

## New dependencies
No new dependencies.

## Rules for implementation — hard requirements
- **Redefine tokens on `:root` in `style.css` ONLY.** Never hardcode a hex
  value in a page stylesheet (`profile.css`, `landing.css`, `analytics.css`,
  `add_expense.css`). If a new color is needed anywhere, it becomes a token
  in `style.css`'s `:root` first, then gets referenced via `var(...)`.
- `.claude/skills/spendly-ui-designer/SKILL.md` **must** be updated in the
  same change — it hardcodes the current palette and is read by
  `spendly-quality-reviewer` before judging CSS; leaving it stale makes the
  new design read as a rule violation to that reviewer.
- **Fonts are unchanged** (DM Serif Display + DM Sans). If a future option
  ever changes them, `templates/base.html`'s Google Fonts `<link>` — the only
  external dependency loaded on every page — must change in the same commit.
  Not applicable to this spec as scoped, but stated so it isn't missed later.
- **Stay responsive.** Verified during spec research: `profile.css` already
  has `overflow-x: auto` on the transactions table (line 189) and breakpoints
  at 900px/640px; `style.css` has 900px/600px breakpoints; `landing.css` has a
  600px breakpoint. These already satisfy "cards stack, tables scroll below
  768px" — a pure color/token change does not touch layout or breakpoint
  rules, so this is a **verify-don't-break** requirement, not new work. Take
  a screenshot at a narrow viewport as part of verification to confirm the
  token change didn't accidentally affect layout.
- No JS frameworks, no CSS preprocessors, no Tailwind — unchanged project
  constraint, restated because this is frontend-only work.
- No SQLAlchemy/ORM, parameterised queries, werkzeug password hashing, `url_for()`
  for links, DB logic placement, ownership checks — not applicable, no
  backend or DB work in this step.

## Verification — required before `/ship-feature`
- Take **before/after screenshots** of `/` (landing, logged out), `/profile`
  (logged in, with seeded data), and `/expenses/add`. "Before" = current
  `main`; "after" = this branch with the chosen palette applied.
- Confirm responsiveness at a viewport below 768px on the same three pages —
  cards stack, the transactions table scrolls rather than overflowing.

## Definition of done
- [ ] `style.css`'s `:root` has `--accent: #006A4E`, `--accent-light: #E3F3EC`,
      `--accent-2: #F42A41`, `--accent-2-light: #FDE6E8` (Option A) — no drift
      from these exact values
- [ ] `--paper`/`--ink` are unchanged (Option A does not touch them)
- [ ] `--danger` is unchanged
- [ ] `.footer` has a 3px top border in `var(--accent)`
- [ ] `templates/base.html`'s footer tagline reads "Track every taka."
- [ ] Browser tab shows the new favicon
- [ ] `.mock-bar-3`/`.mock-bar-4` reference `var(--mock-blue)`/`var(--mock-purple)`,
      not raw hex
- [ ] `git diff` confirms `landing.css`, `profile.css`, `analytics.css` are
      untouched, and `templates/base.html`'s Google Fonts `<link>` is
      unchanged
- [ ] `.claude/skills/spendly-ui-designer/SKILL.md` reflects the new palette
      values and description — no stale "forest green, ochre" references
      remain
- [ ] Before/after screenshots taken of `/`, `/profile`, `/expenses/add`
- [ ] Responsive check at <768px confirms no layout regression on the same
      three pages
- [ ] Full suite passes: `pytest`
- [ ] `python .claude/verify_setup.py` still passes
