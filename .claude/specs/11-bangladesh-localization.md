# Spec: Bangladesh Localization

## Overview
Spendly's UI, demo data, and Claude Code setup files carry Indian-context
defaults left over from the original template: a hardcoded ₹ (rupee) symbol
across six templates and a test file, "Nitish" name/email placeholders on
login and registration, Indian merchant/context descriptions in the seeded
demo expenses, and Indian-context instructions baked into the `.claude/`
command and skill files that drive future `/seed-user` and `/seed-expense`
runs. This step replaces all of it with Bangladeshi equivalents. It is a
**content and display swap only** — no schema change, no new route, no
per-user preference, and (per an explicit decision) **no change to number
formatting**: `"{:,.2f}"` Western digit grouping is kept exactly as-is. An
earlier draft of this spec proposed switching to lakh/crore grouping; that
decision is reversed here and superseded by this version.

## Depends on
- Step 01 (database setup) — `expenses` schema and `seed_db()`, whose
  description strings this step edits
- Step 02 (registration), Step 03 (login) — the templates whose placeholder
  text this step edits
- Step 05 (backend routes for profile page) — the query functions that
  produce the amount strings this step's currency symbol wraps (unchanged
  logic, only the template-side symbol changes)
- Step 06 (date filter) — `tests/test_06_date_filter_profile.py`, whose `₹`
  assertions this step must update in place

## Routes
No new routes.

## Database changes
No schema changes. `database/db.py`'s `seed_db()` gets a **content-only**
edit: the free-text `description` field of its 8 hardcoded demo rows is
rewritten from Indian to Bangladeshi context. `amount`, `category`, `date`,
and the row count are all unchanged, so every existing test that keys off
those values keeps passing.

## Templates
- **Create:** none
- **Modify:**
  - `templates/add_expense.html:22` — label `"Amount (₹)"` → `"Amount (৳)"`
  - `templates/edit_expense.html:22` — label `"Amount (₹)"` → `"Amount (৳)"`
  - `templates/landing.html:43` — mock stat `"₹18,240"` → `"৳18,240"`
  - `templates/landing.html:48` — mock stat `"₹6,760"` → `"৳6,760"`
  - `templates/landing.html:87` — feature-icon glyph `"₹"` → `"৳"`
  - `templates/profile.html:62,103,132` — stats total, transaction amount,
    category amount: `₹` → `৳`
  - `templates/login.html:22` — placeholder `"nitish@example.com"` →
    `"faizul@example.com"`
  - `templates/register.html:22` — placeholder `"Nitish Kumar"` →
    `"Faizul Rahman"`
  - `templates/register.html:28` — placeholder `"nitish@example.com"` →
    `"faizul@example.com"`

## Files to change
- `templates/add_expense.html`, `templates/edit_expense.html`,
  `templates/landing.html`, `templates/profile.html`, `templates/login.html`,
  `templates/register.html` — currency symbol and/or name placeholder edits,
  exact locations above
- `tests/test_06_date_filter_profile.py` — 8 occurrences of `₹` (4 assertions
  at the lines currently reading `assert "₹" in body`, plus their 4 paired
  comments) → `৳`. Pre-existing test file from step 06, not new coverage for
  this step — call this out explicitly during `/test-feature` the same way
  the original draft of this spec did
- `database/db.py:95-102` — `seed_db()` description strings only:
  - `"Groceries from D-Mart"` → a real Bangladeshi retail chain (Shwapno,
    Meena Bazar, or Agora)
  - `"Metro card recharge"` → a Dhaka transport context (CNG, rickshaw, bus
    fare, or Pathao)
  - `"Electricity bill"` → `DESCO` or `DPDC` (Dhaka's actual electricity
    distributors)
  - Every other row, and every `amount`/`category`/`date` value on the three
    rows above, stays byte-for-byte unchanged
- `.claude/commands/seed-user.md` — currently instructs the agent to
  generate "realistic Indian names"; update to Bangladeshi names
- `.claude/commands/seed-expense.md` — currently instructs "realistic Indian
  descriptions" and gives amount ranges labeled with `₹`; update the context
  to Bangladeshi and the symbol to `৳`
- `.claude/skills/spendly-ui-designer/SKILL.md:103-104,234` — documents
  `"Currency is the rupee (₹)"` and a checklist line `"Amounts render as
  ₹{{ value }}"`; update both to `৳` so this skill doesn't contradict the
  live app
- `CLAUDE.md` — add a short, clearly-labeled currency note recording that the
  live symbol is `৳` with `{:,.2f}` grouping kept, so this file (read as
  ground truth by other subagents) supersedes the historical specs below
  without editing them

## Files NOT to change
- `.claude/specs/05-09*.md` — historical records of what was true when they
  were written. Do not edit them to reflect the new currency; the new
  `CLAUDE.md` note is what supersedes them going forward.

## Files to create
None.

## New dependencies
None.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic goes in `database/queries.py` for anything touching `expenses`, or
  `database/db.py` for connection, schema, and `users` work — never inline in
  a route (this step touches neither route logic nor query logic — see next
  bullet)
- **Do not touch `database/queries.py` at all.** Number formatting
  (`"{:,.2f}"`) is an explicit, already-made decision to keep as-is. This
  reverses the earlier draft of this spec, which added a lakh/crore grouping
  helper — that helper must not be introduced
- **Do not change `demo@spendly.com` / `demo123`.** Login credentials are
  unchanged — only the *seed row descriptions* change, not the user account
- Edit only the exact literal strings cited above, at the cited file:line —
  do not touch unrelated text, styling, or structure in any of these files
- `.claude/specs/05-09*.md` are read-only for this step — do not edit them
  even though they still describe `₹`

## Definition of done
- [ ] Every cited currency touchpoint renders `৳` instead of `₹`: both amount
      labels (add/edit expense), both landing-page mock stats and the
      feature icon, and all three profile displays (stat, transaction row,
      category row)
- [ ] `database/queries.py` has zero diff — confirm with `git diff` before
      shipping
- [ ] Amount formatting output is byte-for-byte identical to before this
      change for the same input (e.g. `2450.0` still renders `"2,450.00"`)
- [ ] `tests/test_06_date_filter_profile.py`'s 4 assertions and 4 comments
      are updated to `৳` and the file passes
- [ ] `/login` and `/register` show `faizul@example.com` / `"Faizul Rahman"`
      placeholders instead of the Nitish-based ones
- [ ] A fresh seed (`seed_db()` on an empty DB) produces the same 8 rows with
      the same `amount`/`category`/`date` values, but Bangladeshi-context
      `description` text for the three cited rows
- [ ] `demo@spendly.com` / `demo123` still logs in successfully — unchanged
- [ ] `.claude/commands/seed-user.md` and `.claude/commands/seed-expense.md`
      no longer mention Indian names/descriptions or `₹`
- [ ] `.claude/skills/spendly-ui-designer/SKILL.md` documents `৳`, not `₹`
- [ ] `git diff` confirms `.claude/specs/05-09*.md` are untouched
- [ ] `CLAUDE.md` has a new currency note superseding the historical specs
- [ ] Full suite passes: `pytest`
- [ ] `python .claude/verify_setup.py` still passes
