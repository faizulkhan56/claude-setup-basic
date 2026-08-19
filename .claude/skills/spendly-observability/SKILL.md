---
name: spendly-observability
description: Analyze Spendly local observability using Prometheus, Blackbox Exporter, and Grafana. Use when the user asks about monitoring, metrics, availability, readiness, probe latency, Grafana dashboards, Prometheus queries, or why the local Spendly observability stack looks unhealthy. Read-only by default.
---

# Spendly Observability

This skill is for the local stack under `observability/`.

## Architecture

```text
Browser / test traffic
        |
        v
Spendly :5001
  | /healthz  -> process liveness only
  | /readyz   -> DB readiness
        ^
        |
Blackbox Exporter :9115
        ^
        |
Prometheus :9090
        |
        v
Grafana :3000
```

Prometheus does not currently scrape application-internal Flask counters. The first observability phase intentionally uses black-box service signals so the application code and Python dependencies remain unchanged.

## Golden questions for this stack

1. **Is the service up?**
   `probe_success{job="spendly-blackbox",target="health"}`
2. **Is it ready to serve traffic?**
   `probe_success{job="spendly-blackbox",target="ready"}`
3. **What HTTP code did the probe receive?**
   `probe_http_status_code{job="spendly-blackbox"}`
4. **Is latency increasing?**
   `probe_duration_seconds{job="spendly-blackbox"}`
5. **Which HTTP phase is slow?**
   `probe_http_duration_seconds{job="spendly-blackbox"}`
6. **Are Prometheus targets themselves healthy?**
   `up`

## Safe investigation sequence

Always investigate from outside inward:

1. Query `up` and `probe_success`.
2. Compare `health` with `ready`.
   - health=1, ready=0 -> Flask process is alive but the DB path/read-write path is unhealthy.
   - health=0, ready=0 -> app/container/network path is the first suspect.
3. Check `probe_http_status_code` and `probe_duration_seconds`.
4. If latency is high, inspect `probe_http_duration_seconds` by `phase`.
5. Check container state with `docker compose ... ps`.
6. Only then read relevant logs. Do not dump every log first.

## Prometheus API

Use the HTTP query API rather than scraping Grafana UI state:

```bash
curl -sG http://localhost:9090/api/v1/query \
  --data-urlencode 'query=probe_success{job="spendly-blackbox"}'
```

Useful queries:

```promql
up
probe_success{job="spendly-blackbox"}
probe_http_status_code{job="spendly-blackbox"}
probe_duration_seconds{job="spendly-blackbox"}
probe_http_duration_seconds{job="spendly-blackbox"}
```

For a short trend, use the range API with a suitable start/end/step rather than claiming a trend from a single instant value.

## Interpretation rules

- `probe_success = 1` means the configured black-box check succeeded; it does **not** prove every business function is healthy.
- `/healthz` deliberately does not touch SQLite. Do not interpret it as DB health.
- `/readyz` calls `db_is_healthy()` and returns 503 when SQLite is not usable, so it is the stronger traffic-readiness signal.
- High `probe_duration_seconds` is an external symptom. Use phase timing and logs to narrow the cause; do not label it a database problem without evidence.
- A Grafana panel showing no data can mean a query/provisioning problem, not an application outage. Check Prometheus first.

## Safety boundary

This skill is diagnostic. By default:

- allowed: Prometheus GET queries, `docker compose ps`, `docker compose logs`
- not allowed: restart, recreate, `down`, volume deletion, config edits, image rebuilds, cloud mutations

If remediation is needed, explain the proposed change and hand control back to the user.

## Current limitation

This phase gives service-level availability/readiness/latency metrics. It does not yet expose per-route request rate, error rate, Flask latency histograms, SQLite query timings, or business metrics. Adding those requires explicit application instrumentation and should be treated as a separate phase rather than silently adding a runtime dependency.
