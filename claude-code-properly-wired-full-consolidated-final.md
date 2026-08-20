# Claude Code, Properly Wired: A One-Stop Guide to Spec-Driven Development on a Real Project

*Everything in this guide was executed on one repository — a Flask + SQLite expense
tracker called **Spendly** — from empty `.claude/` directory to a live app on AWS EC2
behind HTTPS. Every number, screenshot, and command is from that run. Nothing is
illustrative.*


> **Expanded edition note.** This edition preserves the original guide and its
> Spendly evidence, commands, numbers, screenshots, and conclusions, then adds
> explanatory sections that make the underlying ideas easier to learn and reuse.
> The added material is marked with headings such as **Expanded theory**,
> **Mental model**, or **Decision framework**. Product-specific details remain as
> stated in the original run; the new material focuses on concepts, reasoning,
> trade-offs, and reusable engineering principles rather than independently
> re-running or re-verifying the original experiment.

---

## Table of contents

1. [What we built, and the project structure](#1-what-we-built-and-the-project-structure)
2. [`CLAUDE.md`: home vs project, and how to write one that earns its tokens](#2-claudemd-home-vs-project)
3. [Slash commands: the basics](#3-slash-commands-the-basics)
4. [The context window: what it costs and how to manage it](#4-the-context-window)
5. [Spec-Driven Development: the cycle, walked three times](#5-spec-driven-development)
6. [Modes: plan, accept-edits, YOLO, and effort tiers](#6-modes)
7. [Building the chain: command → agent → skill](#7-building-the-chain)
8. [Built-in subagents](#8-built-in-subagents)
9. [MCP servers: theory, diagram, and a Python implementation](#9-mcp-servers)
10. [Hooks and guardrails](#10-hooks-and-guardrails)
11. [Plugins](#11-plugins)
12. [`agents-observe`: watching agents work in a browser](#12-agents-observe)
13. [Deploying with the agent/skill/command chain: Docker and AWS EC2](#13-deploying-to-docker-and-aws)
14. [AI-Assisted Observability: Prometheus, Grafana, Loki, Alloy, and Claude](#14-ai-assisted-observability)
- [Appendix A: final metrics](#appendix-a-final-metrics)
- [Appendix B: eleven things that went wrong](#appendix-b-eleven-things-that-went-wrong)
- [Appendix C: conceptual glossary](#appendix-c-conceptual-glossary)
- [Appendix D: choosing the right Claude Code primitive](#appendix-d-choosing-the-right-claude-code-primitive)

---

## The one-paragraph version

Claude Code becomes reliable when you stop prompting it and start **wiring** it. A
slash command orchestrates subagents; subagents load skills for domain knowledge;
hooks enforce invariants deterministically outside the model's judgment; and a
`CLAUDE.md` holds the facts every session needs. The discipline that makes this work
is **Spec-Driven Development** — write the contract first, review it, then build
against it, because a spec is the only artifact that both you and the model can hold
each other to. On Spendly this produced 14 merged PRs, 252 tests, 56 automated wiring
checks, and a deployed app — with a real security finding caught before merge.

---

## 1. What we built, and the project structure

**Spendly** is deliberately boring: a personal expense tracker, Flask, SQLite,
Jinja2 templates, vanilla JS, no build step. The app is the *vehicle*. The
`.claude/` directory is the *deliverable*.

That inversion matters. In a normal project, stale documentation is annoying. Here,
`CLAUDE.md` is read as ground truth by six subagents, so a stale fact is a *defect
that propagates*. More on this in [Appendix B](#appendix-b-eleven-things-that-went-wrong)
— it is the single most recurring bug class in the whole project.

### The application

```
spendly/
├── app.py                    # every route, single file, no blueprints
├── database/
│   ├── db.py                 # connection + schema + users
│   └── queries.py            # expense + profile reads/writes
├── templates/                # base.html + one file per page
├── static/css/               # style.css global; one file per page otherwise
├── tests/                    # pytest — 252 tests
├── requirements.txt          # dev + test
├── requirements-prod.txt     # -r requirements.txt + gunicorn
├── Dockerfile                # phase 1
├── .dockerignore
├── compose.yaml
└── deploy/vm/                # phase 2 — nginx, systemd, bootstrap, RUNBOOK
```

### The Claude Code setup

```
.claude/
├── CLAUDE.md  (project root, actually)   # always-on project facts
├── agents/          6 subagents
│   ├── spendly-test-writer.md            spec → tests
│   ├── spendly-test-runner.md            run + diagnose
│   ├── spendly-security-reviewer.md      auth, injection, exposure
│   ├── spendly-quality-reviewer.md       naming, placement, idiom
│   ├── spendly-devops-engineer.md        builds deploy artifacts
│   └── spendly-devops-reviewer.md        audits them, read-only
├── commands/        7 slash commands
│   ├── create-spec.md            spec + branch
│   ├── test-feature.md           writer → runner
│   ├── code-review-feature.md    security ∥ quality
│   ├── deploy-phase.md           engineer → reviewer
│   ├── ship-feature.md           commit → PR → merge → cleanup
│   ├── seed-user.md
│   └── seed-expense.md
├── skills/          2 skills
│   ├── spendly-devops/
│   │   ├── SKILL.md              router + phase 0 + invariants
│   │   └── references/           phase-1-docker, phase-2-cloud-vm,
│   │                             phase-3-kubernetes, cicd
│   └── spendly-ui-designer/SKILL.md
├── hooks/           3 Python hooks
│   ├── devops_router.py          UserPromptSubmit
│   ├── format_python.py          PostToolUse
│   └── protect_paths.py          PreToolUse — blocking
├── specs/           12 specs, one per feature step
├── settings.json                 hooks + permission allowlist (shared)
├── settings.local.json           personal overrides (untracked)
└── verify_setup.py               56 checks that the wiring is intact
```

**The load-bearing idea:** none of these components know about each other by magic.
Every reference is a string in a file, and strings rot. That is why
`verify_setup.py` exists — see [§7](#7-building-the-chain).


### Current repository verification note

Before preparing this consolidated edition, the two article drafts were checked
against the current `main` codebase rather than treated as authoritative by
themselves.

The current repository adds an observability chain that did not exist in the older
snapshot above:

```text
.claude/
├── commands/
│   └── observe-local.md
├── agents/
│   └── spendly-observability-analyst.md
└── skills/
    └── spendly-observability/
        └── SKILL.md
```

The current application also contains opt-in Prometheus instrumentation in `app.py`:

- `spendly_http_requests_total`
- `spendly_http_request_duration_seconds`
- `spendly_http_requests_in_progress`
- standard Prometheus Python process metrics
- `/metrics` mounted through `DispatcherMiddleware`
- `/metrics`, `/healthz`, and `/readyz` excluded from the custom business-request
  RED metrics so probe traffic does not masquerade as user traffic

The current test directory contains dedicated feature files for steps 07, 09, 10
and 12, plus the older step-06 tests and hook tests. There is **no dedicated
`test_11_bangladesh_localization.py` on current `main`**; step 11 deliberately
updated existing assertions and was validated as a content/configuration change.
That distinction is called out in the worked examples below instead of pretending
every feature followed an identical test-file pattern.

This note is important because the original article intentionally preserves
historical counts and snapshots. The sections below distinguish **what happened in
that run** from **what the repository contains now**.

---


### Expanded theory: treat `.claude/` as an engineering control plane

A useful way to understand the repository is to separate the **product plane** from
an **agent control plane**.

- The product plane is the Flask application, database, templates, tests, Docker
  image, VM configuration, and everything customers ultimately depend on.
- The agent control plane is the set of instructions and mechanisms that shape how
  Claude is allowed to reason and act: `CLAUDE.md`, commands, agents, skills,
  hooks, settings, specs, and verification scripts.

The product plane says **what the software is**. The control plane says **how an AI
worker is expected to interact with that software**. This is why the `.claude/`
configuration deserves the same engineering attention as CI configuration or
infrastructure code. A malformed command can route work incorrectly; a stale skill
can produce a bad design; a broken hook can silently stop enforcing a safety rule.

This also explains why the guide calls the application the *vehicle* and the Claude
setup the *deliverable*. The interesting artifact is not a Flask expense tracker;
it is a repeatable operating model for an AI-assisted repository.

#### Configuration as executable policy

Although most files are Markdown, they are not merely documentation. Their content
changes runtime behaviour:

```text
Human request
   ↓
Claude loads project facts and routing descriptions
   ↓
Commands/agents/skills shape the task
   ↓
Hooks may allow, modify, warn, or block actions
   ↓
Repository or external system changes
```

That makes these files closer to **policy-as-code** than to a wiki page. The syntax
is prose, but the operational effect is real.

#### Why verification is necessary

A conventional compiler catches a renamed function referenced by code. It cannot
catch a Markdown command that still names an agent that was renamed yesterday.
These are **soft references**: the system is wired through strings rather than a
statically typed dependency graph.

`verify_setup.py` therefore plays the role of a lightweight type checker for the
agent control plane. It turns hidden coupling into explicit tests. The broader
lesson is reusable: whenever an AI workflow depends on filenames, skill names,
frontmatter fields, documented routes, or expected tool availability, add a small
machine check for those assumptions.

#### A practical design rule

Keep the control plane **small, layered, and testable**:

1. Put universal project facts in `CLAUDE.md`.
2. Put domain procedures in skills.
3. Put sequencing in commands.
4. Put isolation and tool boundaries in agents.
5. Put deterministic invariants in hooks or CI.
6. Put consistency checks in ordinary tests/scripts.

That separation reduces prompt duplication and makes failures easier to diagnose.

## 2. `CLAUDE.md`: home vs project

There are two, and they do different jobs.

| | Home / global | Project |
|---|---|---|
| Path | `~/.claude/CLAUDE.md` | `<repo>/CLAUDE.md` |
| Scope | every project you open | this repository |
| Tracked in git | no | **yes** — teammates inherit it |
| Contains | *how you like to work* | *facts about this codebase* |

### The home one is about you

Ours is short — a working-style preamble:

```markdown
# Faizul User Workflow

Default working style:
- Prefer actionable engineering outputs
- Use markdown tables when comparing
- For architecture: include tradeoffs
- For troubleshooting: root cause -> fix -> validation

When coding:
- prefer production-grade patterns
- secure defaults
- readable structure
- explain changed files

When uncertain:
- say assumptions clearly
- suggest verification
```

That is the right content for a global file: **preferences, not facts.** It applies
whether you are in a Flask repo or a Terraform one.

### The project one is about the code

Ours is 402 lines and ~5,100 tokens, loaded into **every** session. It carries:

| Section | Why it is there |
|---|---|
| Architecture tree | so nobody has to `ls -R` to orient |
| Code style | PEP 8, `url_for()` always, parameterised SQL always |
| Tech constraints | Flask only, SQLite only, vanilla JS, no new pip packages |
| Subagent Policy | when to delegate, and the DevOps auto-routing rule |
| Claude Code setup | the wiring map — command → agents → skill |
| Route table | all 12 routes with methods and access level |
| Testing | the 252 baseline and the DB-isolation pattern |
| Warnings | the sharp edges: no CSRF, no migrations, `debug=True` |

### Five principles that actually held up

**1. Write facts, not aspirations.** "All nine roadmap steps are implemented, there
are no stub routes left" is a fact. "We should add CSRF" is an aspiration, and it
belongs in an issue.

**2. State the *why*, briefly.** Compare:

> ❌ Never put DB logic in routes.
> ✅ Never put DB logic in routes — it belongs in `database/db.py` (connection,
> schema, users) or `database/queries.py` (anything touching `expenses`).

The second version tells an agent *which* file, which is the part it actually needs.

**3. Document the traps, not just the rules.** The highest-value lines in our
`CLAUDE.md` are the warnings:

```markdown
- **`app.secret_key` is hardcoded** and `debug=True` is hardcoded in `__main__`.
  Fine for local dev, unsafe anywhere else.
- **`seed_db()` runs at import time** and creates demo@spendly.com / demo123.
  Harmless locally; a working backdoor on any public host.
- **There is no CSRF protection.** Known gap — raise it, don't silently add a
  dependency for it.
- **There is no migration system.** A schema change means hand-editing a live
  SQLite file — back it up with VACUUM INTO, never cp.
```

Each of those saved an agent from a confident wrong move.

**4. Every rule needs an escape hatch, stated.** We say "no new pip packages" — and
then:

```markdown
**The one sanctioned exception — approved and landed.** Deployment needs a WSGI
server, because app.run(debug=True) exposes the Werkzeug debugger (remote code
execution). gunicorn==23.0.0 therefore lives in requirements-prod.txt.
```

Without that, an agent facing phase 1 has to either break a rule or fail. With it,
the decision is already made.

**5. Sync it in the same change, always.** If a PR adds a route, it updates the route
table. Not "later". We enforce this mechanically — `verify_setup.py` compares
`CLAUDE.md`'s route table against `app.py` **in both directions**, so a route in the
code but missing from the docs fails the check, and vice versa.

---


### Expanded theory: `CLAUDE.md` is persistent context, not a dumping ground

The project `CLAUDE.md` behaves like a **persistent working-memory preamble**. The
important design question is therefore not "what documentation would be nice to
have?" but:

> What information is so frequently necessary, and so costly to rediscover or get
> wrong, that it deserves to consume context in every relevant session?

That framing produces three categories.

**Stable facts** belong there: architecture, repository conventions, safety rules,
known constraints, route ownership, test commands, and the location of important
components.

**Procedures** often do not. A long step-by-step deployment procedure is usually
better as a skill or reference file that loads only when deployment work begins.

**Transient state** belongs elsewhere. Current issue status, temporary debugging
notes, one-off hypotheses, or an unfinished migration checklist should normally be
tracked in a task/spec/issue rather than being injected into every future session.

#### Context has opportunity cost

Every always-loaded paragraph competes with source code, tool results, the current
specification, and the conversation. This is why concise, accurate project facts are
more valuable than encyclopedic documentation. A 20-line warning section containing
repo-specific traps can outperform 200 lines of generic best practices because it
changes decisions at the exact points where mistakes are likely.

Think of context as a cache:

```text
high reuse + high consequence if wrong  → keep warm in CLAUDE.md
low reuse or large detail               → load on demand
short-lived state                       → keep outside persistent context
```

#### Instruction drift is a production defect

If six agents trust one stale statement, the error is multiplied. This is a form of
**configuration drift**: the code and the agent's declared model of the code no
longer match. The same idea exists in infrastructure management—desired state and
actual state diverge—but here the desired state is natural-language knowledge.

The strongest mitigation is not "remind people to update docs." It is to make drift
observable:

- compare documented routes to real routes;
- compare documented test counts to actual tests where practical;
- ensure named files/functions exist;
- keep ownership rules close to the code they govern;
- update agent knowledge in the same PR as the implementation change.

That is why "sync it in the same change" is more than style. It is a consistency
transaction across code and agent knowledge.

## 3. Slash commands: the basics

A slash command is a **markdown file** in `.claude/commands/`. The filename becomes
the command. `create-spec.md` → `/create-spec`.

Frontmatter configures it:

```markdown
---
description: Create a spec file and feature branch for the next Spendly step
argument-hint: "Step number and feature name e.g. 2 registration"
allowed-tools: Read, Write, Glob, Grep, Agent, Bash(git:*)
---

You are a senior developer spinning up a new feature...
User input: $ARGUMENTS
```

| Field | Purpose |
|---|---|
| `description` | shown in the `/` menu — this is also the *routing signal* |
| `argument-hint` | inline hint for expected args |
| `allowed-tools` | least privilege. `Bash(git:*)` allows git, nothing else |
| `$ARGUMENTS` | substituted with whatever follows the command |

**The body is a prompt, not a script.** It is instructions to the model, so it can
contain conditionals, gates, and refusals in plain English:

```markdown
If no argument is provided, stop immediately and say:
"Please provide a phase. Usage: /deploy-phase <0|1|2|3|cicd>"
```

**`allowed-tools` is the security boundary.** `/code-review-feature` is scoped to
`Bash(git diff), Bash(git status), Read, Glob` — it structurally *cannot* edit a
file, no matter what the diff tempts it to do.

---


### Expanded theory: a slash command is a declarative workflow contract

A slash command is useful because it converts a vague natural-language request into
a **named, repeatable procedure**. It is not just a shortcut for a long prompt. It
can encode gates, actor selection, allowed tools, preconditions, and the expected
shape of the final handoff.

A good command answers five questions:

1. **Trigger** — when should this workflow be used?
2. **Inputs** — what arguments are required?
3. **Preconditions** — what must be true before work begins?
4. **Orchestration** — which agent or tool acts, and in what order?
5. **Exit criteria** — what counts as complete, blocked, or failed?

This makes a command similar to a lightweight runbook or CI job, except its steps can
contain model reasoning.

#### Least privilege belongs at the orchestration boundary

The `allowed-tools` field is powerful because it constrains the *capability surface*
of the command. If a code-review workflow only needs to read diffs, it should not
have generic Bash or Edit access. This follows the same security principle used for
IAM roles and service accounts: grant the minimum capability necessary for the job.

The benefit is not only security. Narrow tools improve reasoning quality because the
agent has fewer irrelevant actions available. A read-only reviewer is naturally
more likely to report findings than to "helpfully" rewrite the code it is supposed
to assess.

#### Commands should be idempotent where possible

An idempotent workflow can be run twice without creating uncontrolled side effects.
For example, a command can:

- check whether a branch already exists before creating it;
- stop if the working tree is dirty;
- detect an existing spec instead of overwriting it;
- print cloud mutation commands rather than running them;
- refuse to merge when validation output is incomplete.

Not every command can be perfectly idempotent, but designing for safe re-entry is
important because agent sessions can fail, hit limits, or be interrupted halfway
through a multi-step workflow.

#### Natural language is still code-like

The body is prose, but operationally it has control flow:

```text
IF no phase argument
    STOP with usage
ELSE IF prerequisite failed
    REPORT blocker
ELSE
    SPAWN engineer
    WAIT
    SPAWN reviewer
    REPORT handover
```

Writing commands with explicit conditions, stop rules, and expected outputs reduces
ambiguity. Treat important prompt workflows with the same care you would give a
shell script: clear inputs, predictable branches, and observable failures.

## 4. The context window

Every session starts with a fixed budget. Understanding what consumes it before you
type anything is the difference between a setup that scales and one that chokes.

### What loads automatically, and what does not

| Layer | Auto-loaded? | Cost |
|---|---|---|
| Project `CLAUDE.md` | **yes, every session** | ours: ~5,100 tokens |
| Home `CLAUDE.md` | **yes** | ours: ~150 tokens |
| Hooks | yes, but they run *outside* the model | **0 context** |
| Agent / skill **descriptions** | yes — needed for routing | 1 line each |
| Agent / skill / command **bodies** | **no** — only when invoked | 0 until used |
| `references/*.md` | **no** — only when `Read` | 0 until used |
| Memory (`MEMORY.md`) | yes | ~3 lines |

That table is the whole game. **Descriptions are always-on; bodies are on-demand.**

### The mistake we made, and the fix

We first wrote **five sibling skills** — `spendly-devops`, `spendly-docker`,
`spendly-cloud-vm`, `spendly-kubernetes`, `spendly-cicd`. Measured cost:

```
spendly-cicd          desc = 711 chars
spendly-cloud-vm      desc = 770
spendly-devops        desc = 759
spendly-docker        desc = 664
spendly-kubernetes    desc = 827
-------------------------------------
TOTAL   3,731 chars ≈ 932 tokens, in EVERY session
```

Nearly a thousand tokens spent in sessions that never touch deployment. Worse, the
descriptions were long *because they had to disambiguate from each other* —
`spendly-kubernetes` needed 827 characters listing "PVC, StorageClass,
CrashLoopBackOff, HPA" purely so it would not collide with `spendly-docker`.

The tell that it was wrong: **every one of those skills opened with "load
`spendly-devops` first."** A skill that is not usable until you load a sibling is a
*chapter*, not a skill.

**The fix — progressive disclosure.** One skill, four reference files:

```
.claude/skills/spendly-devops/
├── SKILL.md                        # router + phase 0 + invariants (281 lines)
└── references/
    ├── phase-1-docker.md           # 273 lines, loaded only for phase 1
    ├── phase-2-cloud-vm.md         # 393
    ├── phase-3-kubernetes.md       # 430
    └── cicd.md                     # 311
```

```
Always-on cost:  932 tokens  →  146 tokens      (-786)
On-demand body:  unchanged — 1,407 lines still available when needed
```

The router's description no longer disambiguates anything; it only has to recognise
"this is infrastructure-shaped."

### Practical levers

- **`/context`** — inspect what is consuming the window right now.
- **`claude plugin details <name>`** — a plugin's projected token cost *before* you
  commit to it. Ours reported `Always-on: ~27 tok` for `agents-observe`, which turned
  a vague worry into a non-issue.
- **Put detail in `references/`, keep `SKILL.md` a router.**
- **Prefer one skill with references over many sibling skills.**
- **Auto-compaction** handles long conversations, but do not rely on it — a 5,000
  token `CLAUDE.md` is paid on every turn regardless.

> **Watch item:** our `CLAUDE.md` grew from ~150 lines to 402 (~5,100 tokens) over the
> project. That is the next thing worth trimming — probably by moving the "Adding a
> new feature" walkthrough into a skill.

---


### Expanded theory: context engineering is resource allocation

The context window is not merely a technical limit; it is the agent's **active
information budget**. The more irrelevant or redundant material occupies it, the
less room remains for the actual problem.

There are three common forms of context waste:

1. **Always-on duplication** — multiple skills repeat the same routing and policy.
2. **Premature detail** — Kubernetes procedures load during a CSS change.
3. **Search debris** — the main session reads dozens of files merely to locate the
   five lines that matter.

Progressive disclosure is the antidote. Keep routing metadata small, then load detail
only after the task has been classified.

```text
Always loaded
   └── enough information to choose the right path
          ↓
On-demand skill
   └── enough information to perform the domain workflow
          ↓
Reference file
   └── detailed phase-specific facts and commands
```

This is analogous to memory hierarchy in computer systems: keep small, frequently
used information close; move bulky, rarely used information behind a lookup.

#### Context quality matters as much as context size

A short context can still be bad if it contains contradictions. The model must then
spend reasoning effort deciding which instruction is authoritative, and may choose
the wrong one. Context engineering therefore has two goals:

- **compression** — remove unnecessary tokens;
- **coherence** — remove ambiguity and stale contradictions.

A useful review question is: *If an agent saw only this paragraph and the code it is
about, could it make the intended decision?* If not, the paragraph may be too vague,
too stale, or stored at the wrong layer.

#### Delegation is also context management

A subagent acts as a temporary private scratch space. It can read many files, perform
searches, and return a compact result. This is not free—the subagent still consumes
compute and tokens—but it keeps the main session from becoming polluted with every
intermediate observation.

The architecture is therefore a **fan-out / summarize / fan-in** pattern:

```text
Main context
   ↓ delegate search
Explore context reads broadly
   ↓ summarize
Main context receives conclusions
```

This is most useful when exploration is broad but the final decision depends on a
small number of findings.

## 5. Spec-Driven Development

### The theory

![Spec-Driven Development cycle](docs/images/sdd-cycle.png)

```
Spec → Review → Design → Review → Tasks → Build → Validate
```

The two `Review` gates are the point. Anyone can get a model to write code; the
difficulty is knowing whether the code is *the right code*. A spec makes that
answerable, because it converts "does this look good?" into "does this satisfy the
Definition of Done?"

**Why this matters more with an agent than with a human.** A human developer who
misunderstands a requirement usually produces something visibly odd. An agent that
misunderstands produces something *confidently plausible* — correct-looking code
solving the wrong problem. The spec is the artifact that makes that detectable,
because tests get written from the spec, not from the implementation.

That last clause is the mechanism. Our `spendly-test-writer` agent is explicitly
forbidden from reading the implementation for test logic:

```markdown
## Core Principle
You write tests based on **feature specifications and expected behavior**, never by
reading or reverse-engineering the implementation. Your tests define what the
feature *should* do, serving as a correctness contract.
```

If tests are derived from the code, they assert that the code does what it does —
which is always true and tells you nothing.

### Our flow, with git wrapped around it

![Our SDD flow with git](docs/images/sdd-flow-with-git.png)

```
git pull origin main  →  git checkout -b feature/x  →  git switch feature/x
                                    ↓
       Spec → Review → Design → Review → Tasks → Build → Validate
                                    ↓
git commit -m  →  git push origin  →  create+merge PR  →  git branch -d  →  switch
```

Each stage maps to a command:

| SDD stage | Our command | Actor |
|---|---|---|
| Spec | `/create-spec 10 export expenses csv` | `Explore` subagent researches |
| Review | *human reads the spec* | you |
| Design | Plan mode, Shift+Tab ×2 | `Plan` subagent |
| Review | *human approves the plan* | you |
| Tasks + Build | plain prompting | main agent |
| Validate | `/test-feature`, `/code-review-feature` | 4 subagents |
| Ship | `/ship-feature` | main agent + GitHub |


### Additional worked example: Step 7, Add Expense — the complete SDD loop

Step 7 is a useful first end-to-end example because it crosses the route, template,
validation, and database layers without adding a new schema.

The real spec at `.claude/specs/07-add-expense.md` says the existing
`GET /expenses/add` placeholder must become a logged-in `GET + POST` flow, backed by
`insert_expense()` in `database/queries.py`. Its validation contract includes a
positive numeric amount, one of seven fixed categories, an ISO date, and an optional
description. The current implementation in `app.py` follows that shape: it checks
the session, validates each field, calls `insert_expense(...)`, flashes success, and
redirects to `profile`.

#### Step 1 — create the spec and feature branch

Run:

```text
/create-spec 7 add expense
```

`/create-spec` does more than create a Markdown file. Its current command definition
requires this sequence:

```text
git status
   ↓
parse step/title/slug
   ↓
ensure branch name is free
   ↓
checkout main + pull
   ↓
create feature branch
   ↓
delegate repository research to Explore
   ↓
write .claude/specs/07-add-expense.md
   ↓
report branch + spec path
```

For this feature, the spec's most important contract can be summarized as:

```markdown
Routes
- GET /expenses/add  — logged-in only
- POST /expenses/add — logged-in only

Rules
- amount > 0
- category ∈ seven fixed categories
- date must be YYYY-MM-DD
- description is optional
- DB writes live in database/queries.py
- parameterised SQL only
- success redirects to /profile

Definition of done
- logged-out users redirect to /login
- valid submission creates a row
- invalid amount/category/date re-renders with an error
- optional description works
- Add Expense navigation is visible
```

That is what "configure the spec" means in practice: define behavior, boundaries,
files, and a testable finish line **before** asking Claude to implement.

#### Step 2 — human review of the spec

Read:

```text
.claude/specs/07-add-expense.md
```

Check especially:

- Does it accidentally add schema work?
- Are auth and ownership rules explicit?
- Are validation failures observable?
- Is the database write kept out of the route?
- Is the Definition of Done testable?

If any answer is wrong, edit the specification now. This is cheaper than correcting
the same misunderstanding after code and tests exist.

#### Step 3 — enter Plan mode

Use **Shift+Tab twice** to enter Plan mode.

A good implementation-planning prompt is:

```text
Read .claude/specs/07-add-expense.md and CLAUDE.md.
Use the built-in Plan/Explore workflow required by the project.
Do not edit files yet.

Produce an implementation plan that maps every Definition-of-Done item to the
exact files/functions/templates that need to change. Call out validation and
database-isolation risks before implementation.
```

Review the plan and approve it only when it matches the spec.

#### Step 4 — implement the approved plan

After leaving Plan mode:

```text
Implement the approved Step 7 plan exactly against
.claude/specs/07-add-expense.md.

Keep scope inside the spec. Reuse existing Flask and database patterns.
Do not add dependencies or schema changes. When done, summarize changed files
and map them back to the spec.
```

The current codebase confirms the implementation landed in the expected places:
`app.py`, `database/queries.py`, `templates/add_expense.html`, profile/navigation
templates, and CSS.

#### Step 5 — write tests from the spec, then run them

Run:

```text
/test-feature 07-add-expense
```

The command is intentionally two-stage:

```text
spendly-test-writer
   ↓  derives tests from the spec, not implementation
writes tests/test_07_add_expense.py
   ↓
spendly-test-runner
   ↓
runs only that feature test file and diagnoses failures
```

The current repository contains `tests/test_07_add_expense.py`, which confirms this
feature ended with dedicated executable coverage.

If tests fail, fix the implementation against the **spec**, not by weakening the
test to match the code. Then rerun `/test-feature 07-add-expense`.

#### Step 6 — security + quality review

Run:

```text
/code-review-feature 07-add-expense
```

The command first collects tracked and untracked changes, then starts the security
and quality reviewers **in parallel**. If the verdict is `CHANGES REQUESTED`, approve
the action plan explicitly, apply it, then rerun the feature tests and review.

#### Step 7 — ship only after the gates are green

Run:

```text
/ship-feature
```

The shipping command:

```text
identify feature branch
   ↓
generate conventional commit message
   ↓
commit
   ↓
push
   ↓
create PR
   ↓
wait for CI checks
   ↓
squash merge
   ↓
delete remote branch
   ↓
pull main
   ↓
delete local branch
```

That is the full SDD loop in executable form:

```text
/create-spec
   → human spec review
   → Plan mode
   → human plan review
   → implement
   → /test-feature
   → /code-review-feature
   → fix/retest if necessary
   → /ship-feature
```

---

### Walkthrough 1: Step 10, CSV export (the reference run)

This is the one we captured end to end.

#### The exact Step 10 operating sequence

This case is the cleanest reference because both the article and the current
repository retain the spec, dedicated tests, security finding, review evidence, and
merged-PR screenshots.

**1. Create the branch and spec**

```text
/create-spec 10 export expenses csv
```

The generated `.claude/specs/10-export-expenses-csv.md` is unusually valuable
because it records decisions that a generic implementation prompt would likely miss:

```markdown
Route
- GET /expenses/export — logged-in CSV attachment

Key rules
- user_id is required by the query helper and enforced in SQL
- never accept user_id from the request
- reuse the existing date-filter behavior
- return raw amount/date values, not formatted display strings
- do not reuse get_recent_transactions() because it formats values and has limit=10
- order by date DESC, id DESC
- write CSV in memory with csv.writer + io.StringIO
- no temporary file
```

Selected Definition-of-Done items make the contract concrete:

```text
logged out → 302 /login
logged in → 200 text/csv attachment
header row present
raw numeric amount + ISO date
more than 10 expenses → all exported
User A never sees User B's rows
two-sided date filter matches profile
invalid/one-sided dates follow existing profile behavior
empty description → empty field
zero rows → header-only CSV
verify_setup.py passes
```

**2. Review the spec before code**

Do not skip the subtle decisions:

- export is a file response, not another template route;
- user isolation belongs in SQL;
- one-sided date behavior intentionally matches the existing profile behavior;
- `get_recent_transactions()` is the wrong abstraction for export.

**3. Plan in read-only mode**

Use Shift+Tab twice, then:

```text
Read .claude/specs/10-export-expenses-csv.md and CLAUDE.md.
Use the built-in Plan agent and delegated repository research.

Plan the smallest implementation that satisfies every DoD item.
Pay special attention to:
- raw vs display-formatted values,
- date-filter parity with /profile,
- user ownership scoping,
- CSV response headers,
- testability.

Do not edit files yet.
```

**4. Implement only after plan approval**

```text
Implement the approved Step 10 plan.
Treat .claude/specs/10-export-expenses-csv.md as the contract.
Do not widen scope.

Use the project UI skill for the profile link styling and preserve existing
database-layer boundaries. Summarize changed files when complete.
```

**5. Generate and run spec-derived tests**

```text
/test-feature 10-export-expenses-csv
```

The repository retains `tests/test_10_export_expenses_csv.py`. In the captured run,
the writer produced 25 test functions / 29 cases and the runner mapped them back to
the DoD.

**6. Run parallel review**

```text
/code-review-feature 10-export-expenses-csv
```

This is where the security reviewer found the issue that a purely functional test
suite could miss: spreadsheet formula injection in CSV free-text cells.

The fix added `_csv_safe()` in `app.py`. The current code confirms the mitigation:
leading `=`, `+`, `-`, or `@` after left-trimming is prefixed with an apostrophe
before CSV serialization.

After applying a review fix:

```text
/test-feature 10-export-expenses-csv
/code-review-feature 10-export-expenses-csv
```

Do not ship from a stale pre-fix review.

**7. Ship**

```text
/ship-feature
```

The captured run produced PR #3, squash-merged it, and removed both feature branches.


**Spec.** `/create-spec 10 export expenses csv` checked the tree was clean, branched
to `feature/export-expenses-csv`, delegated research to the `Explore` subagent, and
wrote `.claude/specs/10-export-expenses-csv.md` with a fixed shape: Overview,
Depends on, Routes, Database changes, Templates, Files to change, Files to create,
New dependencies, Rules for implementation, **Definition of done**.

**Build.** The implementation subagent read the spec, then `CLAUDE.md`,
`queries.py`, `app.py`, `profile.html`, `profile.css` — and then grepped
`style.css` for `--token:` declarations:

![Implementation subagent grepping for design tokens](docs/images/agents-observe-dashboard.png)

That grep is the `spendly-ui-designer` skill's rule *"use the tokens, never hardcode
a hex"* being obeyed without anyone restating it. This is what a correctly wired
setup looks like from the outside.

The interesting technical decision was a trap the spec caught. The obvious move is to
reuse `get_recent_transactions()`. But it formats for *display* — `"1,200.00"` and
`"03 Apr 2026"` — and carries `limit=10`. A CSV needs `1200.0`, `2026-04-03`, and no
limit. So a new helper, `get_expenses_for_export()`, was correct.

**Test.** `/test-feature 10-export-expenses-csv` ran writer → runner, sequentially:

![test-feature pipeline](docs/images/test-feature-terminal.png)

25 test functions, 29 cases, each traceable to a Definition-of-Done item:

![Test report with DoD traceability](docs/images/test-report-dod-table.png)

**Review.** `/code-review-feature 10-export-expenses-csv` forked both reviewers in
**parallel**:

![Parallel code review](docs/images/code-review-parallel-terminal.png)

Visible in the dashboard as two `Agent` spawns from one `Main`:

![Two agents forking from Main](docs/images/observe-code-review-fork.png)

**The finding that justified the whole pipeline:** security cleared the auth guard,
SQL-level `user_id` scoping, and the parameterised date filter — then flagged
**CSV formula injection** via free-text `description` and `category`. A cell
beginning `=`, `+`, `-`, or `@` executes as a formula when the file opens in Excel.
Fixed in the same PR with a `_csv_safe()` helper. Severity: Medium. Caught
pre-merge.

**Ship.** `/ship-feature` → PR #3, squash-merged, both branches deleted:

![PR #3 merged](docs/images/github-pr-3-merged.png)

With the audit trail written into the PR body:

![PR review notes](docs/images/github-pr-3-review-notes.png)

**Result:** feature live, 186 → 215 tests.

![Export CSV live](docs/images/spendly-profile-export-csv.png)

### Walkthrough 2: Steps 11 and 12, localization then redesign

The request arrived as one sentence: *"change the currency from Rs to BDT, change the
default name, make it feel Bangladeshi, and change the design."*

#### Case 3: Step 11 — Bangladesh localization

This is a good example of why the spec can decide **not** to generalize a change.

Start with:

```text
/create-spec 11 bangladesh localization
```

The real `.claude/specs/11-bangladesh-localization.md` explicitly records two
decisions before implementation:

```text
Decision 1:
Keep Western "{:,.2f}" digit grouping.
Do not introduce lakh/crore formatting.

Decision 2:
Keep demo@spendly.com / demo123.
Change display/context data, not the documented demo login.
```

The spec also says:

- no new route;
- no schema change;
- do not touch `database/queries.py`;
- update the live UI symbol from `₹` to `৳`;
- change placeholder and seeded-description context;
- update `seed-user.md`, `seed-expense.md`, the UI skill, and `CLAUDE.md`;
- keep historical specs 05-09 unchanged.

That last point is subtle and important: historical specs are records of their time;
the current `CLAUDE.md` becomes the forward-looking source of truth.

**Plan prompt**

```text
Read .claude/specs/11-bangladesh-localization.md and CLAUDE.md.

Plan a content/configuration-only change. Identify every exact literal that changes
and every file that must remain untouched. Pay special attention to:
- database/queries.py must have zero diff,
- demo login credentials must not change,
- historical specs 05-09 stay unchanged,
- the UI skill and seed commands must not retain Indian-context instructions.

Do not edit yet.
```

**Implementation prompt**

```text
Implement the approved Step 11 localization plan exactly.
Make only the literal/content/configuration changes named in the spec.
Do not refactor number formatting or database queries.
```

**Testing is intentionally different in this case**

Current `main` has no `tests/test_11_bangladesh_localization.py`. The spec itself
requires updating the existing `tests/test_06_date_filter_profile.py` currency
assertions and then running the full suite plus `verify_setup.py`.

So the honest validation sequence for this historical case is:

```bash
python -m pytest tests/test_06_date_filter_profile.py -v
python -m pytest -q
python .claude/verify_setup.py
git diff -- database/queries.py
git diff -- .claude/specs/
```

This is an important exception to avoid papering over: the current generic
`/test-feature` command expects a feature-specific test file, while Step 11's
final repository state used existing coverage. A reusable team workflow should
either add a dedicated Step-11 test file or teach `/test-feature` to honor a spec's
explicit "modify existing tests" strategy.

**Review and ship**

```text
/code-review-feature 11-bangladesh-localization
```

Check especially for scope creep and stale instruction files. After an approved
review and a green full suite:

```text
/ship-feature
```

#### Case 4: Step 12 — Bangladesh design refresh

Start with:

```text
/create-spec 12 bangladesh design refresh
```

The real spec demonstrates a design decision captured **inside the specification**.
It proposed three palettes, then recorded:

```text
Decision: Option A
--accent:         #006A4E
--accent-light:   #E3F3EC
--accent-2:       #F42A41
--accent-2-light: #FDE6E8
--paper / --ink:  unchanged
```

The spec then deliberately narrowed the implementation:

- redefine existing root tokens in `static/css/style.css`;
- do not rewrite page stylesheets;
- preserve fonts;
- update `spendly-ui-designer/SKILL.md` in the same change;
- add a favicon;
- verify responsiveness rather than redesign layout;
- capture before/after screenshots.

**Plan prompt**

```text
Read .claude/specs/12-bangladesh-design-refresh.md and the
spendly-ui-designer skill.

Plan Option A exactly as selected by the spec.
Keep the change token-driven: do not rewrite landing.css, profile.css or
analytics.css. Include the skill-documentation update and visual verification
steps. Do not edit yet.
```

**Implementation prompt**

```text
Implement the approved Step 12 plan.
Use only the chosen Option A token values.
Do not introduce new palette choices or layout changes.
Update the UI skill in the same change so the reviewer reads the new palette as
ground truth.
```

**Test**

```text
/test-feature 12-bangladesh-design-refresh
```

The current repository contains `tests/test_12_bangladesh_design_refresh.py`, so
this case follows the dedicated feature-test pipeline cleanly.

Then perform the spec's visual checks:

```text
/              before + after
/profile       before + after
/expenses/add  before + after
<768px         responsive verification
```

**Review**

```text
/code-review-feature 12-bangladesh-design-refresh
```

The quality reviewer reading the UI skill is part of the design: if the skill were
left stale, correct CSS could be reported as a violation.

**Ship**

```text
/ship-feature
```

The final repository test file and current palette confirm this became executable,
reviewable project state rather than a one-off styling prompt.


**That is two features, and splitting them was the highest-value decision.**

| | Scope | Risk |
|---|---|---|
| Step 11 — localization | 8 files, find-and-replace + seed data + 4 test assertions | low |
| Step 12 — design refresh | 1,592 lines of CSS + every template | high |

Mixed into one PR you cannot tell a broken layout from a broken currency render, and
if the design is wrong you lose the localization on rollback.

**Step 11** — every `₹` → `৳`, placeholders to `Faizul Rahman` /
`faizul@example.com`, and seed data rewritten to Bangladeshi context:
`Groceries from Meena Bazar`, `CNG fare to office`, `DESCO electricity bill`.

Two decisions were settled *in the spec*, before any code:

- **Number grouping stays Western** `"{:,.2f}"`. South Asian convention is
  `1,40,000`, but changing it touches `get_expenses_for_export()` and the CSV tests
  assert comma-free raw amounts. Bigger than it looks.
- **`demo@spendly.com` / `demo123` stays.** It is cited in `CLAUDE.md` and in every
  PR's "How to test". Rename the display name, not the login.

![Taka live](docs/images/spendly-profile-taka-currency.png)

**Step 12** — `--accent: #1a472a → #006A4E` (Bangladesh bottle green),
`--accent-2: #c17f24 → #F42A41` (flag red), new `favicon.svg`, +37 tests.

The critical instruction: **update `spendly-ui-designer/SKILL.md` in the same
change.** It hardcodes the palette, and the quality reviewer reads it as ground truth
— leave it stale and the reviewer flags your *correct* new code as a violation. You
can watch it happen:

![Quality reviewer reading the UI skill](docs/images/observe-quality-reviewer-reads-ui-skill.png)

### Walkthrough 3: Phase 0, making the app deployable

Not a feature: a **prerequisite**. The app as written could not run outside a dev
checkout, for four independent reasons.

#### Why Phase 0 is not run through `/create-spec`

This is the useful counter-example to the four feature cases above. Phase 0 is a
deployment prerequisite owned by the DevOps command/agent/skill chain, so forcing it
through the normal feature-spec command would duplicate the deployment knowledge
already encoded in `spendly-devops`.

The workflow is:

```text
/deploy-phase 0
   ↓
spendly-devops-engineer
   ↓
Skill(spendly-devops)
   ↓
phase-0 rules/invariants
   ↓
implementation artifacts/code changes
   ↓
spendly-devops-reviewer
   ↓
handover
```

A good user prompt is simply:

```text
/deploy-phase 0
```

or, when coming from a natural-language request:

```text
Prepare Spendly for deployment. Start with Phase 0 only.
Do not move to Docker/cloud yet.
```

The DevOps router/skill is responsible for recognizing that the application first
needs secret handling, persistent state, safe seeding, and health/readiness semantics.

After implementation, verify the application tests and wiring checks, then use the
deployment reviewer. Only after Phase 0 is green should `/deploy-phase 1` create the
Docker artifacts.

This distinction is deliberate:

```text
product feature
   → /create-spec → Plan → build → /test-feature → /code-review-feature → /ship-feature

deployment prerequisite
   → /deploy-phase → engineer → DevOps skill → DevOps reviewer → controlled ship
```


| # | Problem | Consequence |
|---|---|---|
| 0.1 | `DB_PATH` pinned to repo root | in a container that is `/app/spendly.db` — inside the image layer, so every restart wipes data and no volume can hold it |
| 0.2 | `app.secret_key = "dev-secret-key"` | a known signing key means anyone forges a session cookie and logs in as any user |
| 0.3 | `seed_db()` at import time | creates `demo@spendly.com` / `demo123` — a working backdoor on a public host |
| 0.4 | no health endpoint | nothing a load balancer, `HEALTHCHECK`, or k8s probe can call |

Run via `/deploy-phase 0`. Its pre-flight:

![Phase 0 pre-flight](docs/images/deploy-phase0-preflight.png)

Then engineer → reviewer:

![Phase 0 reviewer audit](docs/images/deploy-phase0-reviewer-audit.png)

**A design detail worth stealing:** `/healthz` and `/readyz` are deliberately
different.

```python
@app.route("/healthz")
def healthz():
    """Liveness — the process is up. Deliberately does NOT touch the DB."""
    return {"status": "ok"}, 200


@app.route("/readyz")
def readyz():
    """Readiness — the DB is reachable and writable."""
    if not db_is_healthy():
        abort(503)
    return {"status": "ready"}, 200
```

A liveness probe that touches the database turns a *locked* database into a *restart
loop*, which makes the lock worse. Liveness asks "is the process wedged"; readiness
asks "should traffic come here". Conflating them is a classic self-inflicted outage.

**A repo-specific trap this surfaced:** `verify_setup.py` hardcodes the route list
**twice** — forward ("claimed routes exist in `app.py`") and reverse ("no
undocumented routes"). Adding two routes fails *both* until `CLAUDE.md`'s table and
both literals are updated. The duplication is intentional; a comment now says so, so
nobody "fixes" the failure by deleting a list.

![PR #5](docs/images/github-pr-5-phase0.png)

And its non-blocking follow-up, honestly recorded rather than quietly dropped:

![PR #5 known follow-up](docs/images/github-pr-5-dod-and-followup.png)

---


### Expanded theory: what makes Spec-Driven Development different

Spec-Driven Development (SDD) is easiest to understand as a **contract-first control
loop**. The specification defines observable behaviour before implementation. Code,
tests, and review are then evaluated against that contract.

It is related to, but not identical with, several familiar practices:

| Practice | Primary artifact | Main question |
|---|---|---|
| Requirements engineering | requirement/spec | What must the system do? |
| TDD | executable test | What behaviour should the next code satisfy? |
| BDD | behaviour scenario | How should the system behave from a user's perspective? |
| ADRs | decision record | Why did we choose this architecture? |
| SDD | reviewed specification + validation chain | Are we building exactly the agreed change? |

SDD can include TDD or BDD. The important difference is that the **specification is
an explicit first-class artifact and review gate**, rather than an assumption that
lives only in a prompt or developer's head.

#### Four levels of a useful specification

A strong feature spec usually separates:

1. **Intent** — the user or business outcome.
2. **Behaviour** — routes, inputs, outputs, permissions, edge cases.
3. **Change surface** — files, data model, dependencies, interfaces.
4. **Acceptance contract** — a Definition of Done that can be tested or observed.

This prevents the common failure where a spec is merely an implementation plan. A
plan says *how we think we will build it*; a spec says *what must be true when we are
done*. The plan may change while the contract remains stable.

#### Why test derivation matters

If the test writer studies implementation details first, it can accidentally mirror
bugs. This is called **implementation-coupled testing**: the test asks whether the
code behaves like itself rather than whether it behaves like the requirement.

A cleaner chain is:

```text
Specification
   ├──→ implementation
   └──→ independent tests
             ↓
       compare at runtime
```

Both code and tests derive from the same contract but are produced independently.
That creates useful disagreement. If they conflict, the spec becomes the arbitration
point.

#### Traceability closes the loop

The DoD-to-test table shown in the Spendly run is a lightweight requirements
traceability matrix. In regulated systems this idea is formal; here it is pragmatic:
every important acceptance statement should have an observable validation path.

A simple structure is enough:

```text
DoD item → test(s) → result → reviewer finding → PR evidence
```

This provides three benefits:

- missing coverage becomes visible;
- reviewers know what evidence supports completion;
- future changes can identify which tests encode which contract.

#### The human review gates are not ceremony

The two review points before implementation are where humans have the highest
leverage. Fixing a misunderstood requirement in a 30-line spec is cheaper than
fixing it after code, tests, documentation, and deployment artifacts have all been
created from the wrong assumption.

That is the economic reason for SDD: **move disagreement earlier, when change is
cheap**.

## 6. Modes

### Permission modes

Four, cycled with **Shift+Tab**:

| Mode | Behaviour | When |
|---|---|---|
| **default** | asks before edits and commands | unfamiliar repo; anything destructive |
| **acceptEdits** | file edits auto-approved; Bash still asks | steady implementation |
| **plan** | **read-only** — cannot edit, only produce a plan | before any non-trivial change |
| **bypassPermissions** ("YOLO") | nothing asks | sandboxes, throwaway branches, long grinds |

Set a default in `settings.json`:

```json
{ "permissions": { "defaultMode": "acceptEdits" } }
```

Or launch straight into bypass:

```bash
claude --dangerously-skip-permissions
claude -c --dangerously-skip-permissions      # -c resumes the current conversation
```

If `~/.claude/settings.json` has `"skipDangerousModePermissionPrompt": true`, the
startup warning is pre-dismissed.

### Plan mode is the SDD "Design" gate

This is the most under-used mode. In plan mode the model **cannot write**, which
changes its behaviour: it reads more, and it surfaces disagreements *before* they
are baked into a diff. Our `CLAUDE.md` makes it mandatory:

```markdown
- always use a builtin plan subagent in plan mode
- When asked to plan, delegate codebase research to a subagent before presenting
```

Enter with **Shift+Tab twice**. Exit by approving the plan.

### Effort tiers, and what "ultra" means

Separate from permissions, Claude Code has **reasoning effort**: `low`, `medium`,
`high`, `xhigh`, `max`. The status line shows the active tier:

```
Sonnet 5 (1M) | medium (default, active: default) | main | $0.37
81.2k tokens | 8% | 39% (resets 4h 15m)
bypass permissions on (shift+tab to cycle)
```

Escalate for hard reasoning — an ambiguous bug, an architectural trade-off, an
adversarial review. Drop to `low` for mechanical work. Most of Spendly ran on
`medium`.

There is also a genuinely separate feature:

```bash
claude ultrareview            # cloud-hosted multi-agent review of the current branch
```

That runs a *fleet* rather than a single reviewer, which is a different tool from
raising effort on one agent.

### The two layers people conflate

`--dangerously-skip-permissions` silences the **harness**. It does not silence the
**model's judgment** — Claude will still pause before hard-to-reverse or
outward-facing actions. In this project, even in bypass mode, it stopped to ask
before untracking database files containing real password hashes.

To collapse that second layer you must say so in words: *"commit and push without
asking"*, *"merge PRs yourself"*. Two layers, two mechanisms.

### Recommended pairing

| Situation | Permissions | Effort |
|---|---|---|
| Exploring an unknown repo | plan | high |
| Designing a feature | plan | high / xhigh |
| Implementing an approved spec | acceptEdits | medium |
| Mechanical refactor, renames | acceptEdits | low |
| Long autonomous grind in a sandbox | bypass | medium |
| Adversarial review of a security fix | default | xhigh / max |

---


### Expanded theory: permissions and reasoning effort are orthogonal controls

A common conceptual mistake is to treat "YOLO" as if it makes the model more
intelligent or "plan mode" as if it makes the model more cautious by personality.
These settings operate on different axes.

**Permission mode controls what the harness will allow without human approval.**
It is an execution control.

**Reasoning effort controls how much deliberate reasoning the model spends.** It is
a cognition/compute control.

This creates a 2D decision space:

```text
                 more reasoning
                      ↑
     plan/high        │       bypass/high
   safe deep design   │   autonomous deep work
                      │
 ─────────────────────┼────────────────────→ more execution autonomy
                      │
 default/low          │       bypass/low
 quick inspection     │   mechanical automation
```

The right combination depends on **risk, reversibility, and uncertainty**.

#### Risk can be decomposed

Before choosing a mode, ask:

- **Blast radius:** can this affect one file, one repo, production data, or external
  customers?
- **Reversibility:** is there a clean rollback, or is the action destructive?
- **Observability:** will we immediately know if it went wrong?
- **Uncertainty:** do we understand the system well enough to automate the action?

High blast radius + low reversibility is a strong argument for default/plan mode,
even when the code change itself looks simple.

#### Human-in-the-loop has more than one layer

The guide correctly distinguishes harness permission from model judgment. There is
also a third layer worth naming: **organizational controls outside Claude**, such as
branch protection, required reviews, cloud IAM, CI gates, and production approval
workflows.

```text
Layer 1: Claude permission prompts
Layer 2: model instructions / judgment / hooks
Layer 3: external systems that enforce policy regardless of Claude
```

For important systems, rely on layer 3 for true enforcement. A local bypass flag
should never be able to bypass an organization's production guardrail.

#### Prefer autonomy inside a bounded sandbox

The safest place for bypass mode is an environment where the maximum possible damage
is already constrained: a disposable branch, container, test account, ephemeral VM,
or isolated development namespace. That is the security principle of **containment**:
instead of trusting every future action to be correct, design the environment so an
incorrect action has limited consequences.

## 7. Building the chain

### Anatomy of the three primitives

| | File | Job | Loads |
|---|---|---|---|
| **Command** | `.claude/commands/x.md` | *orchestration* — sequence, gates, reporting | on invoke |
| **Agent** | `.claude/agents/x.md` | *isolation* — own context, own tool allowlist | on spawn |
| **Skill** | `.claude/skills/x/SKILL.md` | *knowledge* — domain facts, traps, checklists | on invoke |

The distinction that took us longest to internalise:

> **A command decides *what happens in what order*. An agent decides *who does it,
> with which tools*. A skill supplies *what they need to know*.**

### Our chains

| Command | Subagents (order) | Skill loaded | Writes? |
|---|---|---|---|
| `/create-spec <n> <name>` | `Explore` | — | spec + branch |
| `/test-feature <spec>` | `spendly-test-writer` **→** `spendly-test-runner` | — | `tests/` only |
| `/code-review-feature <spec>` | `spendly-security-reviewer` **∥** `spendly-quality-reviewer` | — | nothing |
| `/deploy-phase <0-3\|cicd>` | `spendly-devops-engineer` **→** `spendly-devops-reviewer` | `spendly-devops` | deploy artifacts |
| `/ship-feature` | — | — | commits, PR, merge |

Note the difference between **→** and **∥**. Test-writer must finish before the
runner has a file to run. The two reviewers are independent, so they fork — visible
as two `Agent` spawns in the dashboard.

### How a subagent loads a skill

The chain only works because the agent definition says so, as its *first
instruction*:

```markdown
## Step 1 — Load the skill. Always. Before anything else.

1. Invoke the `spendly-devops` skill using the **Skill** tool.
2. If that fails, read `.claude/skills/spendly-devops/SKILL.md` with **Read**.

**Do not write a single artifact from general Docker or Kubernetes knowledge.**
The skill carries traps specific to this repo that generic knowledge will miss.
```

Belt and braces — the `Skill` tool *and* a `Read` fallback, so the chain does not
depend on one mechanism. You can watch it work:

![Engineer agent loading the skill](docs/images/observe-phase0-engineer-loads-skill.png)

That `Skill spendly-devops` line is the policy executing.

### Tool allowlists are the real safety mechanism

```markdown
# spendly-devops-engineer
tools: Read, Write, Edit, Grep, Glob, Bash, Skill

# spendly-devops-reviewer
tools: Read, Grep, Glob, Bash(git diff), Bash(git status), Skill
```

The reviewer **structurally cannot edit a file**. Not "is told not to" — cannot. That
is a much stronger guarantee than instruction-following, and it is free.

### The bug this created, and `verify_setup.py`

Every link above is a **string in a markdown file**. Rename an agent and the command
still names the old one — and it fails *silently at runtime*, because a missing
subagent looks like a subagent that had nothing to say.

We hit exactly this. So:

```bash
python .claude/verify_setup.py     # 56 checks; non-zero exit on any break
```

It verifies:

- every referenced agent, command, skill, hook, and path exists
- each skill **directory name matches its frontmatter `name`** — mismatch means the
  skill never registers at all (this bit us: `frontend-design/` declaring
  `name: spendly-ui-designer`)
- every DB helper named in docs is actually defined in `database/`
- `CLAUDE.md`'s route table matches `app.py` **both ways**
- no template hardcodes a URL instead of `url_for()`

It found real breaks every time the setup changed. **If you build a chain like this,
build the verifier too** — it is 150 lines and it is the difference between wiring
you trust and wiring you hope about.

---


### Expanded theory: command, agent, and skill are separation of concerns

The command → agent → skill architecture maps cleanly to three software-design
ideas.

**Command = orchestration.** It owns workflow state and ordering.

**Agent = execution boundary.** It owns context isolation, role, and capabilities.

**Skill = reusable domain knowledge.** It owns procedure, heuristics, traps, and
reference material.

The reason to keep them separate is the same reason application code separates
controllers, services, and libraries: each changes for a different reason.

- A deployment sequence may change without changing Docker knowledge.
- Docker knowledge may change without changing the review agent's tool permissions.
- A security reviewer may be reused by several commands.

If one large prompt contains all three concerns, every change risks unintended
side-effects elsewhere.

#### Think in interfaces between components

A robust chain has explicit contracts:

```text
Command → Agent input:
  objective, scope, constraints, expected output

Agent → Skill input:
  domain/task classification

Skill → Agent output:
  rules, references, validation procedure

Agent → Command output:
  handover block / findings / status
```

The `## Handover` convention in the guide is an example of a simple interface. It
makes outputs machine- and human-predictable.

#### Sequential versus parallel execution

Use sequential execution when there is a **data dependency**:

```text
test writer → test runner
```

The runner cannot validate tests that do not yet exist.

Use parallel execution when tasks are independent and you want diversity:

```text
security reviewer ─┐
                   ├→ combined review
quality reviewer ──┘
```

Parallel reviewers are useful not only for speed but for **independent failure
modes**. A security reviewer and a quality reviewer are primed to notice different
classes of defects.

#### The verifier turns prose wiring into testable architecture

Because the system has no compiler for its Markdown references, the verifier is a
form of **contract test** for the agent architecture. The generalizable pattern is:

> If a configuration error would otherwise fail only when a rare workflow is
> invoked, move that failure to a cheap automated check that runs frequently.

This is exactly what unit tests, schema validation, CI linting, and Terraform
validation already do in other domains.

## 8. Built-in subagents

Beyond custom agents, Claude Code ships general-purpose ones. The two we lean on:

| Agent | Tools | Use |
|---|---|---|
| **`Explore`** | read-only, no edits | broad fan-out search — "where is X handled?" Reads excerpts, not whole files, so it locates code cheaply without flooding your context |
| **`Plan`** | read-only | designs an implementation plan, identifies critical files, weighs trade-offs |
| `general-purpose` | all tools | multi-step work that does not fit a specialist |

### How we use them

`/create-spec` delegates research to `Explore` rather than reading files itself:

```markdown
## Step 6 — Research the codebase (delegate this)

`CLAUDE.md`'s Subagent Policy requires codebase research to be delegated. Do not
read these files yourself — launch the builtin **`Explore`** subagent with breadth
"medium" and ask it to report:
  - app.py — every existing route, its methods, and its auth guard
  - database/db.py and database/queries.py — the DB layer is two modules
  - .claude/specs/*.md — so the new spec does not duplicate an existing one
```

**Why delegate at all?** Context economy. `Explore` burns *its own* window reading
twelve specs and two DB modules, then hands back a summary. The main session pays for
the conclusion, not the search. On a repo this size that is the difference between
having room to implement and running out mid-feature.

Our policy, verbatim:

```markdown
## Subagent Policy
- Always use a builtin explore subagent for codebase exploration before
  implementing any new feature
- Always use a subagent to verify test results after any implementation
- When asked to plan, delegate codebase research to a subagent before presenting
- always use a builtin plan subagent in plan mode
```

---


### Expanded theory: delegation is an information-architecture decision

Subagents are most valuable when they reduce one of three pressures on the main
session:

1. **Search pressure** — many files must be inspected to answer one question.
2. **Role pressure** — you want an independent perspective with different
   instructions, such as security review.
3. **Concurrency pressure** — independent tasks can proceed in parallel.

They are less useful when the task is tiny or when every agent must repeatedly read
the same large context. Delegation has overhead: spawning, rediscovering context,
communicating results, and reconciling disagreement.

A useful threshold is:

```text
If explaining the task to a subagent costs nearly as much as doing the task,
keep it in the main session.
```

#### Isolation provides epistemic independence

A reviewer in a fresh context is less anchored to the implementation story told by
the authoring agent. This is analogous to independent code review: the reviewer may
notice an authorization flaw precisely because it did not participate in the design
choices that made the code look "obviously correct" to the implementer.

That does not make subagents objectively independent—the same model family may be
used—but separate prompts and context still reduce shared local assumptions.

#### Parallelism creates merge and coordination risks

Concurrent agents should usually operate on either:

- disjoint files;
- read-only tasks; or
- separate Git worktrees/branches.

Two writing agents in one working tree can overwrite each other's assumptions or
observe half-written files. The failure described later in the guide is a classic
shared-state race condition. Agent orchestration therefore benefits from ordinary
concurrency principles: ownership, isolation, synchronization, and clear handoff.

## 9. MCP servers

**We do not use MCP in Spendly.** This section is theory plus a working design, and
an honest account of *why* we did not need it.

### What MCP is

The **Model Context Protocol** is an open standard that lets a model call tools
hosted in a separate process. Instead of teaching the model to shell out to `psql`,
you run an MCP server that exposes `query_database` as a typed tool with a schema.

```
┌──────────────────────────────────────────────────────────┐
│                     Claude Code                          │
│                                                          │
│   ┌────────────────┐        ┌──────────────────────┐     │
│   │ Built-in tools │        │   MCP client         │     │
│   │ Read/Edit/Bash │        │                      │     │
│   └────────────────┘        └──────────┬───────────┘     │
└────────────────────────────────────────┼─────────────────┘
                                         │  JSON-RPC 2.0
                        ┌────────────────┼────────────────┐
                        │ stdio          │ HTTP/SSE       │
              ┌─────────▼──────┐  ┌──────▼───────┐  ┌─────▼────────┐
              │ spendly-db     │  │ github       │  │ docker       │
              │ MCP server     │  │ MCP server   │  │ MCP server   │
              │                │  │              │  │              │
              │ tools:         │  │ tools:       │  │ tools:       │
              │  query_expenses│  │  create_pr   │  │  ps, logs    │
              │  schema_info   │  │  merge_pr    │  │  compose_up  │
              │  row_counts    │  │  list_issues │  │  inspect     │
              └────────┬───────┘  └──────┬───────┘  └─────┬────────┘
                       │                 │                │
                  ┌────▼─────┐      ┌────▼────┐     ┌─────▼──────┐
                  │ SQLite   │      │ GitHub  │     │ Docker     │
                  │ spendly. │      │ REST v3 │     │ daemon     │
                  │ db       │      │         │     │ socket     │
                  └──────────┘      └─────────┘     └────────────┘
```

**Transports:** `stdio` (local subprocess — most common) or HTTP/SSE (remote).
**Primitives:** *tools* (model-invoked actions), *resources* (readable data),
*prompts* (reusable templates).

### Why Spendly did not need it

MCP earns its complexity when a capability is **not reachable from a shell** or when
you want a **typed, constrained** interface instead of arbitrary commands.

| Need | Spendly's answer | Would MCP help? |
|---|---|---|
| Query SQLite | `Bash` + `sqlite3` | No — one command |
| Git operations | `Bash(git *)` | No |
| Create/merge PRs | `gh` CLI | Marginal |
| Docker | `Bash` + `docker` | No |
| AWS | `aws` CLI | No |
| Read project docs | `Read` | No |

Every capability was one shell command away. Adding MCP would have meant a second
process, a schema to maintain, and tool definitions in the context window — for
nothing. **The honest engineering answer was: not here.**

### Where it *would* pay off

Concretely, for a Python web project with DB + git + Docker:

1. **Constraining a dangerous capability.** `Bash` can run anything. An MCP server
   exposing only `query_readonly(sql)` — rejecting anything but `SELECT`, with a row
   cap — is a *narrower* grant than `Bash(sqlite3 *)`. This is the strongest
   argument: MCP as a capability *reduction*.
2. **Structured returns.** A tool can return validated JSON, so the model never
   parses CLI text output.
3. **Team-shared infrastructure.** A staging-environment MCP server every developer
   points at, with auth handled once.
4. **Non-shell systems.** Jira, Datadog, Slack, an internal service with no CLI.

### A working implementation

Here is the read-only server that *would* have been defensible — `Bash` minus the
ability to write:

```python
# mcp_servers/spendly_db.py
"""Read-only MCP server over Spendly's SQLite database.

Deliberately narrower than Bash(sqlite3 *): SELECT only, capped rows, no
attach/pragma, and the DB path comes from the environment rather than the caller.

Run:  python mcp_servers/spendly_db.py
Register in .mcp.json (see below).
"""

import os
import re
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("spendly-db")

DB_PATH = os.environ.get("SPENDLY_DB_PATH", "spendly.db")
MAX_ROWS = 500

# One statement, starting with SELECT. No semicolons -> no statement chaining.
_SELECT_ONLY = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(ATTACH|DETACH|PRAGMA|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE)\b",
    re.IGNORECASE,
)


def _connect() -> sqlite3.Connection:
    # Immutable URI: the driver itself refuses writes, so a bug in our regex
    # cannot become a mutation. Defence in depth, not just validation.
    conn = sqlite3.connect(f"file:{Path(DB_PATH)}?immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@mcp.tool()
def query_readonly(sql: str) -> dict:
    """Run a single read-only SELECT and return rows as JSON.

    Rejects anything that is not one SELECT statement. Caps output at 500 rows.
    """
    if ";" in sql.rstrip().rstrip(";"):
        return {"error": "one statement only — no semicolons"}
    if not _SELECT_ONLY.match(sql):
        return {"error": "only SELECT is permitted"}
    if _FORBIDDEN.search(sql):
        return {"error": "statement contains a forbidden keyword"}

    conn = _connect()
    try:
        rows = conn.execute(sql).fetchmany(MAX_ROWS)
        return {
            "columns": [d[0] for d in conn.execute(sql).description],
            "rows": [dict(r) for r in rows],
            "row_count": len(rows),
            "truncated": len(rows) == MAX_ROWS,
        }
    except sqlite3.Error as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        conn.close()


@mcp.tool()
def schema_info() -> dict:
    """Return every table and its columns — orientation without guessing."""
    conn = _connect()
    try:
        tables = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            t: [
                {"name": c["name"], "type": c["type"], "notnull": bool(c["notnull"])}
                for c in conn.execute(f"PRAGMA table_info({t})")
            ]
            for t in tables
        }
    finally:
        conn.close()


@mcp.tool()
def row_counts() -> dict:
    """Row count per table — the cheapest sanity check after a migration."""
    conn = _connect()
    try:
        tables = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    finally:
        conn.close()


@mcp.resource("spendly://schema")
def schema_resource() -> str:
    """The schema as a readable resource, for context rather than a tool call."""
    return "\n".join(
        f"{t}: {', '.join(c['name'] for c in cols)}"
        for t, cols in schema_info().items()
    )


if __name__ == "__main__":
    mcp.run()          # stdio transport
```

Register it — project-scoped, in `.mcp.json` at the repo root:

```json
{
  "mcpServers": {
    "spendly-db": {
      "command": "python",
      "args": ["mcp_servers/spendly_db.py"],
      "env": { "SPENDLY_DB_PATH": "spendly.db" }
    }
  }
}
```

Then `/mcp` lists it, and tools appear as `mcp__spendly-db__query_readonly`.

**Note the layered defence:** a regex allowlist *and* `immutable=1` on the
connection. If the regex has a hole, the driver still refuses to write. Validation
alone is how MCP servers become the vulnerability they were meant to prevent.

### Two operational realities

**MCP servers add context.** Tool schemas are injected. Prefer few, well-scoped tools
over dozens.

**They can vanish.** Mid-project our Docker MCP server disconnected and its tools
became uncallable. Anything load-bearing needs a fallback — which is precisely why
our agents specify the `Skill` tool *and* a `Read` fallback.

**A clever pattern we found in the wild:** `agents-observe` ships an MCP server that
exposes **zero tools**. It is a *lifecycle hook* — it starts a Docker container,
heartbeats every 10s, and deregisters on `SIGTERM`. Zero context cost, real work
done. MCP as a process supervisor.

---


### Expanded theory: MCP is a capability boundary, not just an integration format

MCP is often introduced as "a way to connect Claude to external tools." That is
true, but the more important architectural idea is **capability shaping**.

With unrestricted shell access, the model receives a broad capability:

```text
Bash → potentially every executable and every permission of the current user
```

An MCP server can replace that with a narrow capability:

```text
query_readonly(sql: SELECT only, max 500 rows)
```

This is a security improvement when the MCP implementation is actually narrower than
the shell access it replaces.

#### Client/server mental model

The model does not directly "know" how to talk to SQLite, Jira, or an internal
service. Claude Code acts as an MCP client. A server publishes typed capabilities,
and the client exposes those descriptions to the model.

```text
Model reasoning
   ↓ chooses tool
Claude Code / MCP client
   ↓ protocol request
MCP server
   ↓ validates + acts
Target system
```

The server is therefore a **trust boundary**. It must validate arguments, enforce
authorization, limit output, handle credentials safely, and return errors that do
not leak secrets.

#### Tools, resources, and prompts have different semantics

- **Tools** perform an action or computation. Treat them like API operations.
- **Resources** expose readable context. Treat them like controlled data sources.
- **Prompts** package reusable interaction templates. Treat them like shared
  workflow fragments.

The distinction matters for least privilege. If the model only needs to read schema
information, a resource is conceptually safer than a generic query tool.

#### Typed interfaces reduce ambiguity, not risk by themselves

JSON schemas and structured return values help the model call a capability correctly,
but typing is not authorization. A perfectly typed `delete_database(name)` tool is
still dangerous. Security must be enforced inside the server and in the credentials
it holds.

#### Defence in depth in the SQLite example

The example combines two independent controls:

1. application-level validation of the SQL string;
2. SQLite immutable/read-only semantics at the connection layer.

This is stronger because a bug in one layer does not immediately become a write.
The general principle is:

> Prefer a safe underlying primitive plus validation, rather than relying on a
> parser/regex alone to make a dangerous primitive safe.

#### When *not* to build MCP

MCP adds operational surface area: process lifecycle, authentication, versioning,
logging, schema maintenance, context cost, and failure handling. If `git status` or
`docker ps` already solves the problem safely under a restricted command allowlist,
an MCP wrapper may be unnecessary abstraction.

Use MCP when it creates one of these concrete benefits:

- narrower permissions than the shell;
- structured access to a non-shell system;
- centrally managed credentials;
- shared organizational capability;
- stable typed integration reused across many projects.

## 10. Hooks and guardrails

### Why hooks are different

A skill is *advice*. A hook is *mechanism*. Skills persuade the model; hooks execute
regardless of what the model concludes.

This distinction has a sharp consequence:

> **Hooks still fire under `--dangerously-skip-permissions`.**

A `PreToolUse` hook returning exit code **2** blocks the tool call in any permission
mode. So even in full YOLO, `rm -f spendly.db` is stopped. You build a floor that
YOLO cannot fall through.

### Registration

`.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "python3 .claude/hooks/devops_router.py" }] }
    ],
    "PostToolUse": [
      { "matcher": "Write|Edit",
        "hooks": [{ "type": "command", "command": "python3 .claude/hooks/format_python.py" }] }
    ],
    "PreToolUse": [
      { "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "python3 .claude/hooks/protect_paths.py" }] }
    ]
  }
}
```

**Contract:** JSON payload on stdin. For `UserPromptSubmit`, anything on **stdout is
injected into the model's context**. For `PreToolUse`, **exit 2 denies the call** and
stderr is fed back to the model.

There are ~28 events available — `SessionStart`, `SubagentStart`, `SubagentStop`,
`PreCompact`, `PermissionDenied`, `TaskCompleted`, `FileChanged`, and more.

### Our three hooks

#### 1. `protect_paths.py` — the blocking guard

```python
PROTECTED = ["spendly.db", "spendly-backup.db", ".env", "migrations/",
             "/var/lib/spendly", "letsencrypt"]
DESTRUCTIVE_VERBS = [r"rm", r"unlink", r"truncate", r"shred", r"mkfs(\.\w+)?", r"dd"]
```

Destructive verb **and** protected path → exit 2, blocked.

#### 2. `format_python.py` — cosmetic

Runs `black` on any `.py` file written. No-ops with a message if black is not
installed.

#### 3. `devops_router.py` — the interesting one

**The problem it solves:** a new teammate types *"can you dockerize this?"*. They do
not know `/deploy-phase` exists. Without help, the session writes a plausible
Dockerfile from general knowledge — and bakes the SQLite database into an image
layer, because it does not know `DB_PATH` is hardcoded.

The hook matches DevOps vocabulary and injects routing instructions before the model
sees the prompt:

```
<devops-routing source=".claude/hooks/devops_router.py">
This prompt matched Spendly DevOps triggers (docker). Handle it through the
DevOps pipeline rather than ad hoc:
1. Load the `spendly-devops` skill BEFORE producing any artifact.
2. Delegate to `spendly-devops-engineer` via the Agent tool.
3. Phase 0 is a hard prerequisite for phases 1-3.
4. Relay the subagent's `## Handover` block, then stop.
5. Never commit, push, or touch live cloud state without approval.
</devops-routing>
```

**Two-tier matching** keeps it precise, which matters in a Flask repo full of
DevOps-adjacent words:

```python
STRONG = [r"docker", r"kubernetes", r"kubectl", r"pods?\b", r"ec2\b", r"nginx", ...]
WEAK   = [r"server", r"image", r"container", r"volume", r"restore", r"cloud", ...]
```

One STRONG hit routes. WEAK needs **two distinct** hits. Measured: **11/11 fire,
10/10 stay quiet.**

| Fires | Stays quiet |
|---|---|
| "dockerize this app" | "run the server and check the landing page" |
| "why is my pod stuck in Pending" | "add an image to the hero section" |
| "the container keeps losing my data" | "the container div needs more padding" |

### The lesson: guardrails need their own tests

`protect_paths.py` shipped with **five false positives**, each blocking an ordinary
command:

| Blocked | Cause |
|---|---|
| `git add -A` | `dd` matched inside **add** |
| `echo 'confirm ...'` | `rm` matched inside **confirm** |
| `->` arrows in prose | `>` read as a truncating redirect |
| `>/dev/null` | same, on a discard redirect |
| `<noreply@anthropic.com>` | closing `>` of an angle-bracketed email |

That last one blocked **every commit carrying a `Co-Authored-By` trailer**. The
docstring even claimed word boundaries prevented the `confirm` case — they did not,
because only the *trailing* boundary was present.

So `tests/test_hooks.py` — 48 tests driving each hook over its real stdin/stdout JSON
contract, pinning every false positive:

```python
@pytest.mark.parametrize("command,why", [
    ("git add -A", "'add' contains 'dd' but is not the dd command"),
    ("echo 'confirm spendly.db'", "'confirm' contains 'rm' but is not rm"),
    ("git rm --cached spendly.db", "index-only, file stays on disk"),
    ("ls spendly.db >/dev/null 2>&1", "discarding output destroys nothing"),
])
def test_safe_commands_are_allowed(self, command, why):
    code, _, _ = run_hook("protect_paths.py", {"tool_input": {"command": command}})
    assert code == ALLOW, f"false positive ({why}): {command}"
```

**A structural limitation, stated honestly:** the guard matches substrings and has no
shell parser. It cannot distinguish a command from a string mentioning one — it
blocked our own test harness for containing `rm spendly.db` as *data*. That is why
hook test cases live in a file rather than inline in a shell command. A guardrail is
protection against accidents, not a security boundary.

### One trap worth repeating

We nearly "fixed" cross-platform support like this:

```json
"command": "python3 hook.py || python hook.py"
```

**That silently disables the guard.** `protect_paths.py` signals a block with exit
2; `||` reads that as failure, reruns against already-consumed stdin, gets empty
input, exits 0 — and the destructive command proceeds. The reason is now a comment in
`settings.json` so nobody re-adds it.

---


### Expanded theory: hooks are deterministic policy points around probabilistic reasoning

Language-model reasoning is probabilistic: even with excellent instructions, the
model can interpret a situation differently on another run. Hooks exist to place
**deterministic checks at lifecycle boundaries**.

That makes the basic split:

```text
Skill / instruction:
  "Do not delete the production database."

PreToolUse hook:
  If command matches destructive operation + protected path → exit 2.
```

The first shapes judgment. The second enforces a mechanical condition.

#### Hooks are miniature policy engines

A hook has four conceptual parts:

1. **Event** — when should it run?
2. **Matcher** — which actions does it care about?
3. **Policy logic** — what is allowed, warned, transformed, or blocked?
4. **Outcome contract** — exit code/stdout/stderr that communicates the decision.

Designing these explicitly helps avoid "hook sprawl," where many overlapping scripts
run on every tool call with unclear ownership.

#### Fail-open versus fail-closed

A security control must decide what happens when the control itself crashes.

- **Fail-open:** allow the underlying action. Better availability, weaker safety.
- **Fail-closed:** block the action. Better safety, potential productivity outage.

The Python-not-found incident later in your conversation is a perfect example of why
this distinction matters: non-blocking hook failures allowed commands to continue,
so the repository remained usable but the intended security check was not active.

For destructive production controls, fail-closed is often appropriate. For cosmetic
formatting, fail-open is usually better.

#### Deterministic hooks versus model-based hooks

A useful hierarchy is:

```text
Exact rule / parser / scanner exists
    → command hook

Judgment is required but result is advisory
    → prompt/model hook

Large cross-file reasoning required
    → reviewer agent / skill
```

Do not ask an LLM to decide something a five-line deterministic check can prove.
Conversely, do not force a fragile regex to solve a semantic authorization review.

#### Test hooks like production code

Hooks sit in front of high-frequency actions, so false positives compound quickly.
A 1% false-positive rate on a hook that runs hundreds of times per day becomes a
constant source of interruption.

The Spendly tests demonstrate the right approach:

- test known blocked cases;
- test near-miss safe cases;
- test exit codes;
- test stdin/stdout contracts;
- test platform-specific command syntax;
- pin every historical false positive as a regression test.

That turns guardrails from "clever regex" into maintained software.

#### Hooks are not the final security boundary

Local hooks can be disabled, misconfigured, or bypassed by edits made outside Claude.
Mandatory controls should also live in systems the local agent cannot override:
branch protection, CI checks, IAM, admission policies, secret scanning, deployment
approvals, and backups.

## 11. Plugins

A plugin bundles skills, commands, agents, hooks, and MCP servers into one
installable unit, distributed via a marketplace (a git repo).

```bash
claude plugin marketplace add <owner>/<repo>
claude plugin install <name>
claude plugin details <name>      # component inventory + projected token cost
claude plugin list
claude plugin disable <name>      # keep installed, stop loading
claude plugin uninstall <name>
```

### Ours

```json
"enabledPlugins": {
  "aws-core@claude-plugins-official": true,
  "aws-dev-toolkit@claude-plugins-official": true,
  "databases-on-aws@claude-plugins-official": true,
  "code-review@claude-plugins-official": true,
  "code-simplifier@claude-plugins-official": true,
  "security-guidance@claude-plugins-official": true,
  "ralph-wiggum@claude-code-plugins": true,
  "agents-observe@agents-observe": true
}
```

`aws-dev-toolkit` earned its place immediately. Asked to deploy on
"t3.medium free tier", we queried its pricing MCP tool instead of reciting from
memory:

| Instance | RAM | Hourly | ~Monthly |
|---|---|---|---|
| t3.micro | 1 GiB | $0.0132 | **$9.64** |
| t3.medium | 4 GiB | $0.0528 | **$38.54** |

**t3.medium is not free tier** — Free Tier is 750 h/month of t2.micro (or t3.micro
where t2 is unavailable), 12 months from account creation. That one lookup changed
the deployment and saved ~$29/month.

### Choosing plugins

**Install:** `claude plugin details` **first**. Ask what it adds *always-on* versus
on-demand.

**Two scope facts:**

- `claude plugin install` is **user-level** — it activates in *every* project. Unlike
  a project `settings.json` allowlist, you cannot scope it to one repo through the
  plugin route.
- Plugins register their own hooks through their manifest. `agents-observe` declares
  28 events, three overlapping ours — and because they are separate config sources,
  **both fire**. Our `protect_paths.py` survived untouched, verified with
  `git status` and 48 passing hook tests.

---


### Expanded theory: plugins are software supply chain

A plugin is attractive because it packages many primitives behind one installation,
but that convenience also creates a supply-chain boundary. A plugin may contribute:

- instructions that influence model behaviour;
- agents with their own tools;
- hooks that execute automatically;
- MCP servers that start processes or access external systems;
- commands that users may invoke without inspecting their internals every time.

Installing a plugin is therefore closer to installing a development tool than to
copying a prompt from a blog post.

#### Evaluate plugins on four dimensions

**1. Capability.** What tools, processes, network access, or credentials does it
need?

**2. Automatic execution.** Which hooks run without explicit invocation, and on
which events?

**3. Context cost.** What descriptions/tool schemas are always present?

**4. Update trust.** Who controls future versions, and how are changes reviewed?

This is why `plugin details` is valuable before installation: inventory first,
execution second.

#### Marketplace versus plugin

A marketplace is a **catalog and distribution source**. A plugin is the executable/
instruction package. Keeping the two concepts separate makes organizational
governance clearer:

```text
Cefalo marketplace
   ├── approved internal plugin A
   ├── approved internal plugin B
   └── metadata / versions

Anthropic official marketplace
   └── official plugins selected by policy
```

A team can permit multiple marketplaces while still selecting only a small set of
approved plugins.

#### Organization-level governance pattern

For a professional team, a mature flow looks like:

```text
Discover → inspect → sandbox test → security review → approve version
      → publish/allowlist → monitor updates → periodically re-review
```

Hooks and MCP components deserve especially careful review because they can execute
automatically or interact with external systems.

## 12. `agents-observe`

Terminal output shows you *one* agent's stream. Once a command forks two reviewers,
scrollback stops being a useful mental model. `agents-observe` renders the hierarchy
in a browser.

### Install

```bash
claude plugin marketplace add simple10/agents-observe
claude plugin install agents-observe
# restart claude — hooks and the MCP server load at session start
```

Then `/observe`, or open **http://localhost:4981**.

| Command | Does |
|---|---|
| `/observe` | open the dashboard |
| `/observe view` | current session |
| `/observe status` | server health, version, config |
| `/observe logs` | container logs |
| `/observe start` / `stop` / `restart` | server control |

**Prerequisites:** Docker (it runs a container), Node.js (hook scripts), bash.

### What it costs, measured

```
Always-on:   ~27 tok       added to every session
Hooks (28)   harness-only — no model context cost
MCP (1)      tool schemas resolved at runtime; not counted
observe      ~30 always-on  /  ~1.9k on-invoke
```

Twenty-seven tokens. Our own `spendly-devops` description is 146. **The real cost is
latency, not context** — its `PreToolUse` matcher is `(all)`, so a bash→node chain
spawns on *every* tool call, including every `Read`. On Windows, where process spawn
is slow, that is noticeable.

### Security check worth doing

```yaml
ports:
  - "${AGENTS_OBSERVE_BIND:-127.0.0.1}:${AGENTS_OBSERVE_SERVER_PORT:-4981}:..."
```

Localhost by default. `AGENTS_OBSERVE_BIND=0.0.0.0` is documented for LAN access —
**and the dashboard has no authentication**, so never set that on untrusted wifi.
Verify after install:

```bash
docker ps --format '{{.Names}} {{.Ports}}' | grep -i observe
# want: 127.0.0.1:4981->4981/tcp
```

### What it actually showed us

**Sequential handoff** — writer finishes, `SubStop`, then Main spawns the runner:

![Test writer to runner](docs/images/observe-test-writer-to-runner.png)

**Parallel fork** — two `Agent` spawns from one `Main`:

![Code review fork](docs/images/observe-code-review-fork.png)

**Policy compliance** — the engineer's `Skill spendly-devops` call, visible:

![Engineer loads skill](docs/images/observe-phase0-engineer-loads-skill.png)

**Gates and shipping**:

![Gates and ship](docs/images/observe-phase0-gates-and-ship.png)

### The failure mode it exposed

Mid-review, a session limit hit:

![Session limit and retry](docs/images/design-refresh-review-session-limit-retry.png)

```
spendly-security-reviewer  (Security review of design refresh) · 2 tool uses · 21.3k tokens
  Done
spendly-quality-reviewer   (Quality review of design refresh) · 0 tool uses
  Done
You've hit your session limit · resets 7:20pm (Asia/Dhaka)
```

**Both say `Done`.** But the quality reviewer used **0 tools** — it died on an API
error and reported completion. Since the security reviewer *had* finished cleanly, a
casual read concludes both passed.

What caught it was a rule written into `/code-review-feature` long before:

> *"If either subagent fails or returns no output, report it and do not present a
> partial review as complete."*

The retry then did real work. **Treat `0 tool uses` as a failure signal, not a clean
pass.** A guardrail written for one reason catching a different failure entirely is
the best argument for writing them down.

---


### Expanded theory: agent observability is distributed-systems observability in miniature

Once one session spawns several agents, the workflow stops looking like a linear
chat and starts looking like a small distributed system:

- work is concurrent;
- agents have independent context;
- failures can be partial;
- status messages can be misleading;
- coordination and handoff matter;
- latency comes from many underlying tool calls.

That is why a visual hierarchy becomes useful.

#### Three kinds of observability

**Execution observability** answers *what ran?* — which agents, tools, hooks, and
commands were invoked.

**Performance observability** answers *where did time/tokens go?* — long-running
agents, tool-heavy branches, repeated searches.

**Correctness observability** answers *did the workflow really complete?* — did a
reviewer inspect files, return evidence, and satisfy the expected output contract?

The "Done with 0 tool uses" incident shows why status alone is insufficient. In
reliable systems, completion should be inferred from **evidence**, not just a final
state label.

A better completion contract can include:

```text
agent status = completed
AND output is non-empty
AND required tool(s) were used where appropriate
AND expected report section exists
AND no API/tool error occurred
```

#### Observability has its own overhead

Instrumentation is never free. A hook that spawns Node on every tool call increases
latency even if it contributes almost no model-context tokens. This mirrors ordinary
APM systems: telemetry can consume CPU, network, storage, and time.

Measure both **context overhead** and **runtime overhead** before deciding a plugin
is cheap.

## 13. Deploying to Docker and AWS

### The phase model

Rather than one leap to production, four phases, each a superset:

| Phase | Target | Reference | Replicas |
|---|---|---|---|
| **0** | make the app deployable at all | `SKILL.md` | 1 |
| **1** | Docker + Compose, one host | `references/phase-1-docker.md` | 1 |
| **2** | AWS EC2 / Azure VM | `references/phase-2-cloud-vm.md` | 1 |
| **3** | Managed Kubernetes | `references/phase-3-kubernetes.md` | **still 1** |
| — | CI/CD | `references/cicd.md` | — |

Phase 0 is not skippable. It is the four code changes from
[Walkthrough 3](#walkthrough-3-phase-0-making-the-app-deployable).

### The chain, applied to infrastructure

```
"can you dockerize this?"
        ↓  devops_router.py  (deterministic, no model judgment)
        ↓  CLAUDE.md DevOps policy  (always in context)
        ↓  /deploy-phase 1
        ↓  spendly-devops-engineer  →  spendly-devops-reviewer
        ↓  Skill(spendly-devops) + Read(references/phase-1-docker.md)
        ↓  ## Handover block relayed, then stop
```

**One rule made this safe:**

```markdown
4. **Never commit, push, or mutate live cloud or cluster state** as part of a
   DevOps request. Print the command; let the user run it.
```

The agent writes artifacts and prints AWS CLI commands. **You** run them. Every
`aws ec2 run-instances` in this project was executed by a human who read it first:

![Phase 2 pre-flight](docs/images/deploy-phase2-preflight-engineer.png)

### Phase 1 — Docker

Key decisions, each with a reason:

**`gunicorn`, not `python app.py`.** `app.py` ends with
`app.run(debug=True, port=5001)`. `debug=True` serves the Werkzeug interactive
debugger, which executes arbitrary Python from a browser. Reachable = compromised.
The `CMD` imports `app:app` as a WSGI callable, so `__main__` never runs and stays
intact for local dev.

**`--workers 1 --threads 4`.** `get_db()` opens a fresh connection per call, so the
code is thread-safe. It is *not* multi-process safe for writes — two gunicorn worker
processes on one SQLite file produce `database is locked`. Threads give concurrency
without cross-process write contention.

**WAL + `busy_timeout`:**

```python
conn.execute("PRAGMA journal_mode = WAL")
conn.execute("PRAGMA busy_timeout = 10000")
```

WAL lets readers proceed during a write — which matters more since the CSV export,
because a full export is a long read. WAL creates `-wal` and `-shm` siblings, so the
**directory** must be writable: mount `/data`, never the single file.

**Non-root user**, because phase 3 sets `runAsNonRoot: true` — build the habit early
so the manifest needs no workaround.

**`urllib` healthcheck**, because `python:*-slim` ships no `curl`.

#### The `.dockerignore` bug — the most valuable finding in the project

The reference said:

```
*.db
```

An agent probed it empirically: planted `database/_probe.db`, built, and **found it
inside an image layer.** In this Docker/BuildKit version a bare `*.db` matches only
at the **build-context root**, not recursively like `.gitignore`.

```diff
- *.db
+ **/*.db
+ **/*.db-wal
+ **/*.db-shm
```

Why this is severe: the `.db` files are gitignored but **exist on disk in every
working checkout**, containing real user emails and password hashes. `.gitignore` does
**not** filter a Docker build context — only `.dockerignore` does. A bare pattern
plus a nested database equals credentials shipped in a published image.

**The lesson:** the agent did not trust the document. It *tested* the claim. That is
the behaviour worth designing for.

### Phase 2 — AWS EC2, actually executed

Region `ap-southeast-1` (Singapore), account `149451857623`, default VPC
`vpc-1ef5dd79`.

**Instance:** `t3.micro`, Ubuntu 24.04 LTS, IMDSv2 enforced, **no key pair** — SSM
Session Manager only.

**Security group** (`sg-0741cb4e86b431320`) — inbound:

| Port | Source | Why |
|---|---|---|
| 443 | `0.0.0.0/0` | HTTPS |
| 80 | `0.0.0.0/0` | ACME challenge + redirect |
| 22 | **absent** | SSM instead — no key material anywhere |
| 5001 | **never** | if reachable, nginx is bypassed and traffic is plaintext |

Compose binds `127.0.0.1:5001:5001`. The prefix is load-bearing: `"5001:5001"` binds
`0.0.0.0`, and Docker's iptables rules **bypass a UFW-style host firewall** — the
port ends up reachable even though `ufw status` says otherwise.

**Other resources:** Elastic IP `eipalloc-056a8e1187edbb266` (allocated *before*
certbot — a default public IP changes on stop/start and breaks both DNS and the
cert), 10 GB data volume `vol-0024c08875df926b0` at `/var/lib/spendly`, IAM instance
profile scoped to one SSM parameter and one S3 prefix, S3 bucket for backups.

**TLS without owning a domain:** `54-251-203-112.sslip.io`. `sslip.io` resolves any
embedded IP, and Let's Encrypt will issue for it. Zero cost, real certificate.

#### The trap that made TLS non-negotiable

`compose.yaml` sets `SPENDLY_ENV=production`, and phase 2 ties
`SESSION_COOKIE_SECURE` to it. **Secure cookies are never transmitted over plain
HTTP.** Deploy behind nginx without TLS and you get a working-looking deploy where
*nobody can log in*, with no error explaining why. Hence `ProxyFix`:

```python
if os.environ.get("SPENDLY_BEHIND_PROXY") == "1":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
```

`x_for=1` means "trust exactly one proxy" — an app that trusts
`X-Forwarded-For` while directly exposed lets any client spoof its own IP.

#### Backups: `VACUUM INTO`, never `cp`

```bash
sqlite3 /var/lib/spendly/spendly.db "VACUUM INTO '/tmp/backup.db'"
aws s3 cp /tmp/backup.db s3://spendly-backups/db/spendly-$(date -u +%FT%H%M%SZ).db
```

With WAL active, `cp spendly.db` copies the main file and misses every transaction
still in `spendly.db-wal` — a silently truncated backup that restores clean and is
missing data.

### The runbook

Full executed steps with real resource IDs: **[`deploy/vm/RUNBOOK.md`](deploy/vm/RUNBOOK.md)**.

It is a record of an actual run, not a template — every command is followed by its
real output (`-> ami-0ed6a65b84536f6ce`, `-> i-0db2a335dd43fd951`). Structure:

```
## Target
## Resources created
## Prerequisite code changes (2.1/2.2)
## Step-by-step: AWS infrastructure provisioning
     1. Latest Ubuntu 24.04 AMI via SSM parameter (never a hardcoded ID)
     2. Pick a public subnet in the default VPC
     3. S3 backup bucket — before the IAM role, so its policy scopes to a real ARN
     4. Security group: 80/443 only, no 22
     5. IAM role + instance profile — SSM, one parameter, one S3 prefix
     6. Launch: t3.micro, IMDSv2 enforced, no key pair
     7. Data disk — same AZ, attached at /dev/sdf
     8. Elastic IP — allocate before use
     9. Generate + store the Flask secret (once, never printed, never committed)
## Step-by-step: configuring the VM
```

Two habits from it worth copying:

**Fetch AMI IDs from SSM, never hardcode:**

```bash
aws ssm get-parameter --name \
  /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
  --query Parameter.Value --output text
```

**Verify before trusting a default.** The runbook confirms the data-disk device name
before running `bootstrap.sh`:

```
-> confirmed: nvme0n1 (20G root), nvme1n1 (10G, unformatted) — matches
```

On Nitro instances the device is `/dev/nvme1n1`, not the `/dev/sdf` you asked for.
Mount by `LABEL=` with `nofail` — a wrong device path in `/etc/fstab` without
`nofail` leaves the VM **unbootable**.

### Never lie about the environment

One correction we insisted on: an app running via `python app.py` on `127.0.0.1:5001`
is **"running locally"**, not "deployed". Calling it deployed implies an
internet-facing app with the Werkzeug debugger exposed — remote code execution. In
documentation, that distinction is not pedantry; it is the difference between a
screenshot and a claim.

### The SQLite ceiling, stated plainly

Phase 3 exists in the skill, and its most important content is a limitation:

- **Phases 1-2 are genuinely fine.** One host, one file, one container.
- **Phase 3 does not scale.** A ReadWriteOnce PVC mounts to one node, so
  `replicas: 2` leaves a pod stuck `ContainerCreating`. `RollingUpdate` **deadlocks**
  on the volume — `strategy: Recreate` is mandatory. HPA is unusable.
- **Never put SQLite on NFS or SMB** (EFS, Azure Files). Locking is unreliable and
  WAL will corrupt the database. Block storage only.

Real horizontal scale means changing the datastore, which contradicts `CLAUDE.md`'s
"SQLite only". **That is the user's decision**, so the skill presents options and
stops:

| Option | Replicas | Code change | Violates CLAUDE.md |
|---|---|---|---|
| SQLite on a PVC | 1 | none | no |
| Litestream-style replication | 1 writer | moderate | partly |
| Managed Postgres | many | rewrite `database/` | yes |

A skill that knows where its authority ends is more useful than one that guesses.

---


### Expanded theory: deployment is progressive risk reduction

The four deployment phases form a **maturity ladder**. Each phase adds operational
assumptions only after the previous layer is understood.

```text
Phase 0: application is deployable
   ↓
Phase 1: process is packaged reproducibly
   ↓
Phase 2: package runs on a real host behind network/TLS controls
   ↓
Phase 3: orchestration adds scheduling, probes, volumes, and rollout behaviour
```

This is safer than jumping straight to Kubernetes because Kubernetes cannot repair
an application that has an unsafe secret key, import-time backdoor, incorrect
persistence path, or nonexistent readiness semantics. Orchestration magnifies those
problems.

#### Immutable compute, explicit state

A core deployment principle is to separate **replaceable compute** from **persistent
state**.

```text
Container / VM image   → replaceable artifact
Database / volume      → persistent state
Secret                 → external configuration
Logs/metrics           → external observability
```

The original `DB_PATH` problem violated this by placing the database inside the
replaceable application layer. The fix is not Docker-specific; it is an instance of
the broader principle that state should have an explicit lifecycle independent from
application binaries.

#### Liveness and readiness encode different failure semantics

A liveness probe should answer: *Is this process so unhealthy that restarting it is
likely to help?*

A readiness probe should answer: *Can this instance safely receive traffic now?*

The distinction prevents cascading failure. If readiness fails because a dependency
is temporarily unavailable, removing the instance from traffic may help. Restarting
the process may do nothing or make the outage worse.

This is an example of **control-loop design**: health signals should trigger actions
that are appropriate for the failure they represent.

#### Reverse proxies create a trust boundary

Once nginx or a load balancer sits in front of the app, headers such as
`X-Forwarded-For` and `X-Forwarded-Proto` become security-sensitive. Trusting them
from any source allows clients to spoof origin information. `x_for=1` means the
application expects exactly one trusted proxy hop.

The general rule is:

> Forwarded headers are trustworthy only when the application can prove the request
> came through the proxy that is allowed to set them.

Network exposure and application middleware must therefore agree.

#### Backups must preserve database consistency, not merely files

Copying a database file is not the same as creating a consistent database backup.
WAL, journaling, pending writes, and multi-file formats can make a byte-for-byte file
copy incomplete even though it appears successful.

A backup process needs four properties:

1. **Consistency** — represents a valid transaction boundary.
2. **Durability** — stored independently from the primary host.
3. **Recoverability** — restore procedure is tested.
4. **Retention** — multiple recovery points exist.

`VACUUM INTO` addresses consistency for this SQLite case. S3 addresses independent
storage. A mature runbook should also include periodic restore tests because an
untested backup is only a hypothesis.

#### The SQLite ceiling is an architectural constraint, not a tuning problem

Many scaling problems cannot be solved with more replicas if the storage model does
not support concurrent writers or multi-node attachment. Recognizing this boundary
is good architecture: it prevents an agent from "solving" a fundamental constraint
with increasingly complicated Kubernetes manifests.

The right question becomes:

> Is single-writer SQLite still an intentional product constraint, or has the
> workload changed enough to justify a datastore migration?

That decision belongs at the architecture/product level because it changes code,
operations, cost, and failure modes.

#### Human-executed cloud mutation is a deliberate control

The rule "agent prints the cloud command; human runs it" is a manual approval gate.
It separates artifact generation from state mutation and provides a final chance to
inspect account, region, IDs, destructive flags, and cost implications.

As automation matures, that gate can later move into a controlled deployment system
with approvals and audit logs. The important concept is not that humans must always
paste commands; it is that high-impact mutation should happen through a **well-defined
control point**.


## 14. AI-Assisted Observability

The earlier deployment chapter answers: **How do we run Spendly safely?**

This chapter answers the next operational question:

> **When the application is running, can Claude help us understand what is happening
> from real telemetry without replacing Prometheus, Grafana, Loki, or deterministic
> alerting?**

The current repository says yes, with one important boundary: Claude is a
**read-only correlation and explanation layer**. Metrics, alert rules, logs, and
dashboards remain the source of evidence.

### 14.1 What the current codebase actually contains

This chapter is not inferred only from screenshots. The current `main` repository
contains the complete control-plane wiring:

```text
.claude/
├── commands/
│   └── observe-local.md
├── agents/
│   └── spendly-observability-analyst.md
└── skills/
    └── spendly-observability/
        └── SKILL.md
```

It also contains:

```text
observability/
├── compose.yaml
├── README.md
├── prometheus/
├── grafana/
├── alloy/
└── loki/...
```

And `app.py` currently implements opt-in RED instrumentation when
`SPENDLY_METRICS_ENABLED=1`.

The application metrics are:

```text
spendly_http_requests_total
spendly_http_request_duration_seconds
spendly_http_requests_in_progress
```

The Prometheus Python client also exposes process CPU/memory metrics. The application
deliberately excludes `/healthz`, `/readyz`, and `/metrics` from the custom
business-request RED metrics.

That detail prevents the monitoring system from measuring its own probe/scrape
traffic as if it were user activity.

### 14.2 The three observability phases

The repository's `observability/README.md` and observability skill describe three
incremental phases.

#### Phase 1 — black-box availability

```text
/healthz
/readyz
   ↓
Blackbox Exporter
   ↓
Prometheus
   ↓
Grafana
```

Signals include:

- liveness;
- DB-aware readiness;
- HTTP status;
- end-to-end probe duration;
- Prometheus scrape/target health.

![Phase 1 Grafana dashboard](docs/images/observability/01-phase1-grafana-dashboard.webp)

The key distinction remains the same as in deployment:

```text
/healthz = process is alive
/readyz  = dependency-aware readiness
```

Do not call a successful health probe proof that the database is healthy.

#### Phase 2 — application RED and process metrics

Spendly then exposes request telemetry:

```text
Rate
Errors
Duration
```

plus CPU and memory.

Prometheus rules evaluate deterministic conditions such as:

- endpoint probe failure;
- missing Spendly metrics scrape;
- p95 application latency above 500 ms;
- 5xx ratio above 5%.

![Prometheus alert rules](docs/images/observability/02-prometheus-alert-rules.webp)

This division of labor is fundamental:

> If Prometheus can evaluate a condition mathematically, Prometheus should evaluate
> it. Do not ask an LLM every minute whether a threshold is bad.

#### Phase 3 — centralized logs

Docker stdout/stderr flows through Grafana Alloy into Loki:

```text
Docker logs
   ↓
Grafana Alloy
   ↓
Loki
   ↓
Grafana
```

![Grafana Alloy pipeline](docs/images/observability/03-alloy-pipeline.webp)

A collector being "up" is not proof that logs arrive. Verify the entire path:

```text
application emits log
   ↓
Alloy discovers source
   ↓
labels/process stages are correct
   ↓
Loki receives stream
   ↓
query returns the expected event
```

Grafana is provisioned with both Prometheus and Loki:

![Grafana datasources](docs/images/observability/04-grafana-datasources.webp)

and a combined dashboard provides metrics and logs in one operational view:

![Grafana metrics and logs dashboard](docs/images/observability/05-grafana-metrics-logs-dashboard.webp)

### 14.3 The complete telemetry + Claude architecture

```text
Browser / test traffic
        │
        ▼
   Spendly :5001
      │
      ├── /healthz ─────┐
      ├── /readyz ──────┼──> Blackbox Exporter ──┐
      └── /metrics ───────────────────────────────┼──> Prometheus
                                                  │
Docker stdout/stderr ──> Grafana Alloy ──> Loki  │
                                      │           │
                                      └─────┬─────┘
                                            ▼
                                          Grafana
                                            │
                                            ▼
                                   Claude /observe-local
                                            │
                                            ▼
                                read-only evidence report
```

The AI is intentionally at the end of the chain:

```text
instrumentation
   ↓
collection
   ↓
storage
   ↓
query
   ↓
alert/visualize
   ↓
AI correlation
```

If an earlier layer is missing, Claude cannot recreate it reliably.

### 14.4 How `/observe-local` is configured

The current command is intentionally small:

```yaml
description: Analyze the local Spendly Prometheus/Grafana/Loki observability stack
argument-hint: "optional symptom, e.g. p95 latency increased"
allowed-tools: Read, Agent
```

Its body performs three steps.

**Step 1 — confirm the setup exists**

It reads:

```text
observability/README.md
.claude/skills/spendly-observability/SKILL.md
```

If either is missing, the workflow stops.

**Step 2 — delegate to the specialist**

It invokes:

```text
spendly-observability-analyst
```

and tells the analyst to:

- load `spendly-observability` first;
- inspect black-box signals;
- inspect RED/process metrics;
- inspect firing Prometheus rules;
- inspect matching Loki logs;
- use bounded Compose logs only when needed;
- stay read-only.

**Step 3 — return a plain-language report**

The command asks for:

```text
current state
metric and log evidence
assessment
correlation
likely cause only if supported
next safe verification step
recommended remediation — not executed
```

This is a clean command → agent → skill reuse of the architecture developed earlier
in the guide.

### 14.5 The analyst's actual read-only tool boundary

The agent is not merely told "please be careful." Its allowed tools are narrow:

```text
Read
Grep
Glob
curl
docker compose ... ps
docker compose ... logs
Skill
```

It is explicitly forbidden from:

```text
up
down
restart
rm
exec
kill
volume deletion
image rebuild
config edits
package installs
cloud commands
```

That means observation and remediation are structurally separated.

### 14.6 The investigation order Claude follows

The skill and agent define a concrete order.

**1. Container/target state**

```bash
docker compose --env-file observability/.env -f observability/compose.yaml ps
```

**2. Prometheus target and black-box health**

```promql
up
probe_success{job="spendly-blackbox"}
ALERTS{alertstate="firing"}
```

**3. Request rate and errors**

```promql
sum(rate(spendly_http_requests_total[1m]))

sum by (route,status) (
  rate(spendly_http_requests_total[5m])
)
```

**4. Application p95**

```promql
histogram_quantile(
  0.95,
  sum by (le,route) (
    rate(spendly_http_request_duration_seconds_bucket[5m])
  )
)
```

**5. Process pressure**

```promql
process_resident_memory_bytes{job="spendly-app"}

rate(process_cpu_seconds_total{job="spendly-app"}[5m])
```

**6. Loki logs over a matching window**

```logql
{stack="spendly-observability",service_name="spendly"}
```

**7. Bounded Compose logs only when a hypothesis needs confirmation**

```text
spendly
prometheus
loki
alloy
```

This order matters. It moves from broad availability toward narrower internal
evidence instead of jumping directly to a favorite root cause.

### 14.7 The prompts we used — step by step

The repository now documents the actual user-facing prompt progression. These are
better evidence than reconstructing a remembered chat from scratch.

#### Prompt 1 — general health baseline

Start with the command alone:

```text
/observe-local
```

Because no symptom is supplied, the command asks the analyst for a general
health/readiness/request-rate/error/p95/process/log-pipeline assessment.

Conceptually Claude does:

```text
stack state
   ↓
up + black-box health/readiness
   ↓
request rate/errors/p95
   ↓
CPU/memory
   ↓
firing alerts
   ↓
Loki pipeline/logs
   ↓
overall assessment
```

Use this first. It establishes whether the monitoring stack itself is trustworthy
before investigating a specific incident.

#### Prompt 2 — health + logs correlation

The repo's documented example is:

```text
/observe-local explain whether the application is healthy and correlate metrics with the last 15 minutes of Spendly logs
```

This changes the task from "show health" to "prove the assessment from two signal
families."

Claude should:

```text
query health/readiness + RED/process metrics
   ↓
query Spendly Loki logs for the same 15-minute window
   ↓
compare timestamps
   ↓
state what both sources agree on
   ↓
call out any conflicting signal
```

This is the first real **correlation** prompt.

#### Prompt 3 — focused p95 investigation

The repo's latency test prompt is:

```text
/observe-local investigate why p95 latency increased and show the Prometheus evidence plus any matching Spendly log evidence
```

The analysis should not begin with "the database is slow." It should begin with:

```text
Is internal p95 actually elevated?
Which route is elevated?
Is black-box latency also elevated?
Did error rate change?
Did CPU/memory move?
Are there matching logs in the same period?
```

Only when supporting signals line up should the report name a likely cause.

This is the prompt represented by the latency-correlation evidence:

![Claude latency correlation report](docs/images/observability/12-claude-latency-correlation-report.webp)

#### Prompt 4 — alerts + errors + readiness + logs

The repository also documents:

```text
/observe-local check for firing alerts, 5xx errors, readiness problems, and relevant Loki logs
```

This prompt is useful when the operator does not yet know whether the incident is
availability, application failure, or an observability-pipeline problem.

It asks Claude to compare:

```text
ALERTS
   +
5xx route/status series
   +
health/readiness probes
   +
Loki evidence
```

A missing log stream alone must not be called an application outage; Alloy and Loki
health must be checked first.

### 14.8 A fuller reusable prompt when you want an explicit report contract

The shorter `/observe-local ...` examples above are the actual repository-documented
inputs. When you want to make the output contract explicit in a manual Claude CLI
session, this fuller form is useful:

```text
Use the Spendly observability workflow and analyze the current application behavior.

Check Prometheus metrics and Loki logs for the same time window.

Focus on:
- request rate,
- errors,
- latency,
- process health,
- firing rules,
- matching log events.

Do not change code, containers, dashboards, alert rules, or infrastructure.

Return:
1. current state,
2. exact metric evidence,
3. exact log evidence,
4. correlation between the two,
5. most likely cause only if supported,
6. confidence and remaining uncertainty,
7. one next safe verification step,
8. recommended remediation, not executed.
```

This is not a replacement for the slash command; it explains the contract the
command/agent/skill already enforce.

### 14.9 What Claude's report looks like

The analyst definition standardizes the output:

```text
Spendly AI-Assisted Observability Report

Current state
- containers
- black-box health/readiness
- Prometheus target health
- request rate / errors / p95
- process CPU / memory
- firing rules
- Loki/Alloy log pipeline

Evidence
- exact metric values, labels, time window, relevant log facts

Assessment
- HEALTHY
- DEGRADED
- UNAVAILABLE
- OBSERVABILITY STACK ISSUE

Correlation
- what metrics and logs agree on
- conflicts still needing explanation

Most likely cause
- evidence-backed only
- otherwise: "not isolated yet"

Next safe verification step
- one read-only query/command

Recommended remediation
- describe only; do not execute
```

The full correlation screenshot captures the same philosophy:

![Claude full correlation report](docs/images/observability/11-claude-full-correlation-report.webp)

### 14.10 Full-stack verification: what we actually proved

![Full-stack observability verification](docs/images/observability/07-full-stack-verification.webp)

A reliable test is not:

```text
Grafana opens
```

or:

```text
Alloy container is running
```

It is:

```text
application generates behavior
   ↓
Prometheus receives metrics
   ↓
rules evaluate
   ↓
Alloy receives logs
   ↓
Loki stores/query returns logs
   ↓
Grafana exposes independent human evidence
   ↓
Claude queries matching windows
   ↓
Claude reports evidence + correlation + uncertainty
```

This mirrors `verify_setup.py` at runtime: verify the **wiring**, not only the
existence of components.

### 14.11 Interpretation rules that prevent confident nonsense

The current skill includes several high-value rules.

```text
health=1, ready=0
→ process/network alive; DB-aware readiness failing
→ verify evidence before naming DB root cause
```

```text
black-box latency high + internal p95 normal
→ inspect probe/network path before application code
```

```text
internal p95 high + black-box health normal
→ app is available but slower
→ narrow by route and logs
```

```text
5xx ratio high
→ identify route/status series
→ query Loki over the same window
```

```text
Grafana "no data"
→ not proof of outage
→ query Prometheus/Loki APIs directly
```

```text
Loki "no data"
→ may be Alloy discovery/socket/config issue
→ verify log pipeline before judging app health
```

And the most important sentence:

> **If evidence is insufficient, say `not isolated yet`.**

That phrase is a feature, not a failure.

### 14.12 Time-window alignment

Correlation without time alignment is storytelling.

Bad:

```text
latency spike at 14:05
+
unrelated error log at 09:10
=
invented root cause
```

Better:

```text
route p95 rises around 14:05
+
5xx/CPU/readiness checked around 14:05
+
matching application logs around 14:05
=
evidence-backed hypothesis
```

The analyst is explicitly told to align metrics and logs to the same window.

### 14.13 What each technology owns

| Layer | Owns |
|---|---|
| Application instrumentation | Emits meaningful RED/process signals |
| Blackbox Exporter | External health/readiness probe evidence |
| Prometheus | Metrics storage/query and deterministic rule evaluation |
| Grafana Alloy | Log discovery/collection/labeling/forwarding |
| Loki | Log storage and LogQL queries |
| Grafana | Human-readable independent evidence |
| Claude analyst | Read-only correlation, explanation, uncertainty, next step |

Claude does **not** become the metric database, alert engine, log store, or final
root-cause authority.

### 14.14 The safe incident workflow

```text
1. Prometheus/Grafana exposes a deterministic signal.

2. Select a time window.

3. Run /observe-local with the symptom.

4. Claude queries metrics and logs read-only.

5. Claude returns:
   - current state,
   - evidence,
   - correlation,
   - hypothesis,
   - uncertainty,
   - next verification.

6. Human validates the hypothesis.

7. Remediation goes through the normal feature/DevOps workflow.

8. Monitoring verifies recovery.
```

Do not collapse steps 3 and 7 into one autonomous "diagnose and fix production"
agent. Separating diagnosis from mutation preserves evidence and keeps blast radius
bounded.

### 14.15 Current boundary and the next phase

The repository currently correlates metrics and centralized container logs.

It **does not yet implement distributed tracing**.

That means the next logical phase is OpenTelemetry tracing/service-dependency
analysis, added separately so the metrics/logging system remains understandable and
reversible.

The order should be:

```text
metrics + logs proven
   ↓
add tracing
   ↓
verify trace propagation
   ↓
then extend Claude correlation to metric + log + trace
```

---

## Appendix A: final metrics

| Metric | Value |
|---|---|
| Merged PRs | 14 |
| Tests | **252**, 0 failing |
| Wiring checks (`verify_setup.py`) | **56** |
| Specs | 12 |
| Subagents | 6 custom + built-ins |
| Slash commands | 7 |
| Skills | 2 (one with 4 references) |
| Hooks | 3, with 48 dedicated tests |
| `CLAUDE.md` | 402 lines ≈ 5,100 always-on tokens |
| Always-on skill cost after refactor | 146 tokens (from 932) |
| Deployed | AWS EC2 t3.micro, ap-southeast-1, HTTPS via sslip.io |
| Monthly infra cost | ~$14 (t3.micro + EIP + 10 GB gp3) |

---


### How to interpret these metrics

The numbers in this project are useful, but they measure different dimensions and
should not be collapsed into a single "quality score."

- **252 tests** measure breadth of executable checks, not necessarily correctness of
  requirements.
- **56 wiring checks** measure integrity of the Claude control plane.
- **48 hook tests** measure guardrail regression coverage.
- **14 merged PRs** measure delivery increments and auditability.
- **5,100 always-on tokens** measure context cost, not documentation quality.

A mature project watches trends rather than chasing raw counts. For example, adding
50 low-value tests can increase the test count while reducing maintainability. A
better metric pair is **coverage of critical contracts + failure-detection quality**.

The most important outcome reported here is qualitative: the workflow caught a real
CSV injection risk before merge and several wiring/configuration defects before they
became runtime surprises. That demonstrates the value of layered independent checks.

## Appendix B: eleven things that went wrong

The failures taught more than the successes. Every one is a real event from this
project.

**1. Five sibling skills cost 932 always-on tokens.** Collapsed to one skill with
`references/` → 146. *Prefer progressive disclosure.*

**2. A skill directory name did not match its frontmatter `name`.** It never
registered — silently. *`verify_setup.py` now checks this.*

**3. Both reviewers had only `Bash(git diff)`.** A feature adding new files produces
an empty diff, so they reported "no findings" on unreviewed work. *Added
`Bash(git status)` and explicit enumeration.*

**4. The test-writer's documented fixture used a `username` field that does not
exist**, and set `app.config['DATABASE']`, which the app never reads — so tests would
have run against the developer's **real database**. *Replaced with the actual
`DB_PATH`-patch pattern.*

**5. Three tests asserted the wrong contract.** They checked a SQL-injection payload
returned zero rows — but a parameterised query binds it as a literal, and `'`
(ASCII 39) sorts below `2` (50), so `BETWEEN` legitimately matches everything. *Now
assert the call returns and the schema survives.*

**6. `protect_paths.py` shipped five false positives**, including blocking every
commit with a `Co-Authored-By` trailer. *48 tests now pin them.*

**7. We nearly wrote `python3 hook.py || python hook.py`** — which silently disables
a blocking guard, because exit 2 reads as failure and the retry sees consumed stdin.
*Documented as a comment so nobody re-adds it.*

**8. `.dockerignore` used bare `*.db`**, which matches only at the build-context root
— a nested database leaked into an image layer with real password hashes. *`**/*.db`.*

**9. A subagent died on an API error and reported `Done` with 0 tool uses.** *Treat
`0 tool uses` as failure.*

**10. Two sessions shared one working tree** while a backgrounded agent was
mid-edit. *Keep the observing session read-only.*

**11. `CLAUDE.md` drifted, repeatedly.** Five implemented routes still marked "stub".
`database/db.py` described as empty when it had six functions. `queries.py` absent
from the architecture tree entirely. A test baseline stale in **five** files at once.
A `/deploy-phase` pre-flight excusing three failures as "known" long after they were
fixed.

That last one is the thesis of this guide. In a normal project, stale docs are
untidy. Here, six subagents read `CLAUDE.md` as ground truth — so a stale fact does
not sit inert, it *propagates into decisions*. The pre-flight excusing fixed failures
would have let a real regression through on the next run.

**Which is why the most valuable file in the whole setup is the 150-line script that
checks whether the documentation is still true.**

```bash
python .claude/verify_setup.py     # 56 checks; non-zero exit on any break
```

---

*Built on Spendly — Flask + SQLite, deliberately simple, so the setup could be the
subject. Every command, screenshot, cost, and failure above is from the actual run.*


---

## Appendix C: conceptual glossary

This glossary is added to make the guide usable as study material as well as a
project diary.

| Term | Meaning in this guide |
|---|---|
| **Agent control plane** | Repository configuration that governs how Claude reasons and acts: instructions, commands, skills, agents, hooks, settings, and verification. |
| **Always-on context** | Information injected into every applicable session, such as `CLAUDE.md` and routing descriptions. |
| **Progressive disclosure** | Keeping routing information small and loading detailed knowledge only when the task requires it. |
| **Spec-Driven Development (SDD)** | A contract-first workflow where behaviour is specified and reviewed before implementation, then validated against that specification. |
| **Definition of Done (DoD)** | Observable acceptance conditions that determine whether a feature is complete. |
| **Traceability** | Mapping requirements/DoD items to implementation, tests, review findings, and evidence. |
| **Slash command** | A named Markdown workflow that orchestrates a repeatable task. |
| **Subagent** | A delegated Claude context with its own role, instructions, and tool access. |
| **Skill** | Reusable domain knowledge and workflow guidance loaded on demand. |
| **Hook** | Code or model logic triggered by a lifecycle event, often used for deterministic automation or guardrails. |
| **MCP** | Model Context Protocol: a client/server protocol for exposing typed tools, resources, and prompts to model clients. |
| **Plugin** | A distributable package that can contain commands, skills, agents, hooks, MCP servers, and related configuration. |
| **Marketplace** | A catalog/source from which plugins are discovered and installed. |
| **Least privilege** | Grant only the minimum tools/permissions needed for a task. |
| **Fail-open** | If a control fails, the underlying action continues. |
| **Fail-closed** | If a control fails, the underlying action is blocked. |
| **Blast radius** | The maximum scope of damage a mistaken action can cause. |
| **Reversibility** | How easily an action can be undone or rolled back. |
| **Liveness** | Whether a process is alive enough that restarting it may help if it fails. |
| **Readiness** | Whether an instance is currently able to serve traffic correctly. |
| **Immutable compute** | Treat application images/instances as replaceable artifacts rather than places where durable state lives. |
| **Configuration drift** | Divergence between documented/desired state and actual implementation. |
| **Soft reference** | A dependency expressed as a string or convention rather than something a compiler/type checker can validate automatically. |
| **Handover contract** | A predictable output format one agent returns to the orchestrating workflow. |

---

## Appendix D: choosing the right Claude Code primitive

When several Claude Code features seem capable of solving the same problem, start
with the **smallest mechanism that provides the guarantee you need**.

### Decision tree

```text
Is this a stable fact every session needs?
  └─ yes → CLAUDE.md

Is this reusable knowledge/procedure needed only for certain tasks?
  └─ yes → Skill (+ references for large detail)

Is this a repeatable multi-step workflow with gates/order?
  └─ yes → Slash command

Does the task need isolated context, specialist role, or narrower tools?
  └─ yes → Subagent

Must something happen automatically at a lifecycle event?
  └─ yes → Hook

Does Claude need a structured capability from another process/service?
  └─ yes → MCP server

Do several repositories/users need the same bundle?
  └─ yes → Plugin + marketplace

Must a rule be authoritative even outside Claude Code?
  └─ yes → CI/CD, IAM, branch protection, policy engine, or other external control

Need deterministic runtime metrics/logs?
  └─ yes → Prometheus / Alloy / Loki / Grafana

Need evidence-based cross-signal explanation without mutation?
  └─ yes → read-only observability command → analyst agent → observability skill
```

### Avoiding overengineering

Do **not** create a hook, skill, reviewer agent, and MCP tool for the same rule just
because all are available. Layer them only when each layer contributes a distinct
property.

A security example:

```text
Hook
  → blocks known dangerous command patterns immediately

Security skill
  → provides the review methodology and checklist

Security reviewer agent
  → performs independent cross-file reasoning on high-risk changes

CI scanner / branch gate
  → enforces organization policy independent of local Claude configuration
```

That is layered defence, not duplication, because each component has a different
trigger and guarantee.

### A compact selection matrix

| Need | Best first choice | Why |
|---|---|---|
| Project architecture facts | `CLAUDE.md` | Always available, simple |
| Detailed Docker/K8s procedure | Skill reference | Loads only when needed |
| "Create spec then branch then report" | Command | Owns sequence and gates |
| Independent security assessment | Reviewer subagent | Fresh context + narrow tools |
| Block `rm` on protected paths | Command hook | Deterministic and immediate |
| Read-only access to internal DB/API | MCP | Typed constrained capability |
| Share team-wide bundle | Plugin | Versionable distribution unit |
| Mandatory production policy | External CI/IAM/policy | Cannot depend on local agent settings |

### Final mental model

A reliable Claude Code repository is not one giant prompt. It is a small system of
specialized components:

```text
                Human intent
                    │
                    ▼
             Project knowledge
                CLAUDE.md
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
       Command            Direct task
          │
          ▼
        Agent  ────────────────┐
          │                    │
          ▼                    │
        Skill                  │
          │                    │
          ▼                    │
   references / tools          │
          │                    │
          └──────────┬─────────┘
                     ▼
                Tool actions
                     │
               Hooks surround
              lifecycle events
                     │
                     ▼
             Code / infrastructure
                     │
                     ▼
              CI and external
             policy validate it
```

The design goal is not maximum automation. It is **predictable automation with
clear contracts, bounded authority, observable failures, and cheap ways to verify
that the wiring still matches reality**.
