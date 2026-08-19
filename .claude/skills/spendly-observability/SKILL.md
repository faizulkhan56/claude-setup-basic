---
name: spendly-observability
description: Analyze Spendly local observability using Prometheus, Blackbox Exporter, Grafana, Loki, and Grafana Alloy. Use for monitoring, metrics, availability, readiness, latency, errors, Grafana dashboards, Prometheus queries, Loki logs, or metric/log correlation. Read-only by default.
---

# Spendly Observability

This skill is for the local stack under `observability/`.

## Three phases now present

1. **Phase 1 — black box:** `/healthz`, `/readyz`, probe status and latency.
2. **Phase 2 — application metrics:** `/metrics` exposes RED metrics plus process CPU/memory when `SPENDLY_METRICS_ENABLED=1`.
3. **Phase 3 — logs:** Grafana Alloy discovers the Compose containers, tails Docker stdout/stderr, labels streams, and writes them to Loki.

## Architecture

```text
Spendly :5001
  |-- /healthz ----> Blackbox Exporter --.
  |-- /readyz -----> Blackbox Exporter ---+--> Prometheus :9090
  `-- /metrics ---------------------------'

Docker stdout/stderr --> Alloy :12345 --> Loki :3100

Prometheus + Loki --> Grafana :3000 --> Claude /observe-local
```

## Investigation order

Always move from broad availability to internal evidence:

1. `up` — are Prometheus scrape targets healthy?
2. `probe_success` — compare health vs readiness.
3. Application RED metrics — request rate, status/error ratio, p95 latency.
4. Process metrics — memory and CPU if resource pressure is plausible.
5. `ALERTS{alertstate="firing"}` — check evaluated local rules.
6. Loki logs for `service_name="spendly"` over the same time window.
7. Docker container state and bounded logs only if needed to confirm a hypothesis.

Never jump from one slow sample to a root-cause claim. Correlation needs matching time windows and at least two supporting signals when possible.

## Prometheus queries

```promql
up
probe_success{job="spendly-blackbox"}
probe_http_status_code{job="spendly-blackbox"}
probe_duration_seconds{job="spendly-blackbox"}
sum(rate(spendly_http_requests_total[1m]))
sum by (route, status) (rate(spendly_http_requests_total[5m]))
histogram_quantile(0.95, sum by (le, route) (rate(spendly_http_request_duration_seconds_bucket[5m])))
process_resident_memory_bytes{job="spendly-app"}
rate(process_cpu_seconds_total{job="spendly-app"}[5m])
ALERTS{alertstate="firing"}
```

Custom RED metrics intentionally exclude `/healthz`, `/readyz`, and `/metrics`, so probe/scrape traffic does not masquerade as user request volume.

## Loki / LogQL

Spendly logs:

```logql
{stack="spendly-observability",service_name="spendly"}
```

All local stack logs:

```logql
{stack="spendly-observability"}
```

Read-only API example:

```bash
curl -sG http://localhost:3100/loki/api/v1/query_range \
  --data-urlencode 'query={stack="spendly-observability",service_name="spendly"}' \
  --data-urlencode 'since=15m' \
  --data-urlencode 'limit=100' \
  --data-urlencode 'direction=backward'
```

## Interpretation rules

- health=1, ready=0: process/network path is alive but DB-aware readiness is failing; verify logs/DB evidence before naming the cause.
- health=0 and app `up`=0: app/container/network availability is the first suspect.
- black-box latency high but internal p95 normal: investigate network/probe path before application code.
- internal p95 high with normal black-box health: service is available but slower; use route-level p95 and logs to narrow scope.
- 5xx ratio high: identify affected route/status series, then query Loki over the same period.
- Grafana no-data alone is not proof of outage; check Prometheus/Loki APIs directly.
- Loki no-data can be an Alloy discovery/socket/config problem; do not call the application healthy or unhealthy from log absence alone.

## Compose environment rule

Use the explicit env file on every Compose read command so Claude background shells do not depend on exported variables from another shell:

```bash
docker compose --env-file observability/.env -f observability/compose.yaml ps
```

## Safety boundary

Allowed by default: Prometheus/Loki GET queries, Compose `ps`, bounded Compose `logs`, file reads.

Not allowed by this diagnostic workflow: `up`, `down`, restart, recreate, `rm`, volume deletion, config edits, image rebuilds, shelling into containers, or cloud mutation.

If remediation is indicated, explain the evidence and proposed change, then hand control back to the user.

## Current boundary

Metrics and logs are correlated locally. Distributed tracing is not part of this phase; OpenTelemetry should be a separate next phase.
