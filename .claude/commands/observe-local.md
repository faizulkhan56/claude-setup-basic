---
description: Analyze the local Spendly Prometheus/Grafana observability stack. Optional argument describes a symptom to investigate.
argument-hint: "optional symptom, e.g. readiness is slow"
allowed-tools: Read, Agent
---

Analyze the local Spendly observability stack. The user's optional focus is:

`$ARGUMENTS`

## Step 1 — Confirm the observability setup exists

Read:

- `observability/README.md`
- `.claude/skills/spendly-observability/SKILL.md`

If either is missing, stop and report that the local observability setup is incomplete.

## Step 2 — Delegate the investigation

Invoke `spendly-observability-analyst`.

Pass it:

- the user's symptom from `$ARGUMENTS`, if any
- instruction to load the `spendly-observability` skill first
- instruction to inspect container state, Prometheus metrics, and only relevant bounded logs
- instruction to remain read-only and never restart or mutate anything

If no symptom was supplied, ask the analyst for a general health/readiness/latency assessment.

## Step 3 — Report

Relay the analyst's findings in plain language with:

- current state
- evidence
- assessment
- likely cause, only if supported
- next safe verification step
- recommended remediation, not executed

Do not modify files or restart the stack from this command.
