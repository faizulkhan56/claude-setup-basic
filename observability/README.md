# Spendly Local AI-Assisted Observability

This local stack now covers three incremental observability phases:

1. **Phase 1 — external service health**: Prometheus + Blackbox Exporter probe `/healthz` and `/readyz`.
2. **Phase 2 — application metrics**: Spendly exposes Prometheus RED metrics when `SPENDLY_METRICS_ENABLED=1`, plus the Python client's process CPU/memory metrics.
3. **Phase 3 — centralized logs**: Grafana Alloy reads Docker logs and sends them to Loki. Grafana is provisioned with both Prometheus and Loki so metrics and logs can be correlated in one place.

The Claude Code `/observe-local` command uses a read-only observability analyst to query Prometheus and Loki, correlate metrics with logs and container state, and recommend a next verification step without restarting or changing the stack.

## Architecture

```text
Browser / test traffic
        |
        v
Spendly :5001
  |-- /healthz ----------------------.
  |-- /readyz -----------------------+--> Blackbox Exporter --> Prometheus
  `-- /metrics --> app RED/process --'
                                          |
Docker stdout/stderr --> Grafana Alloy --> Loki
                                          |
                                          v
                                      Grafana
                                          |
                                          v
                             Claude /observe-local analyst
```

## What is monitored now

### Phase 1 — black-box service signals

- liveness from `/healthz`
- DB-aware readiness from `/readyz`
- probe HTTP status
- end-to-end probe duration
- HTTP phase timings
- Prometheus target/scrape health

### Phase 2 — application metrics

- request rate by Flask route
- HTTP status / 5xx ratio
- request duration histogram and p95 latency
- in-progress request gauge
- Spendly process resident memory
- Spendly process CPU time/rate
- Prometheus alert-rule state

Health, readiness and `/metrics` traffic are excluded from the custom business-request RED metrics so the probes do not dominate the request-rate panels.

### Phase 3 — centralized logs

- Docker stdout/stderr for all services in the `spendly-observability` Compose project
- service/container labels added by Grafana Alloy
- Loki queries in Grafana and through the Loki HTTP API
- metric + log correlation by the Claude observability analyst

## Components

- Spendly container
- Prometheus
- Blackbox Exporter
- Grafana
- Loki
- Grafana Alloy

## One-time local setup

From the repository root:

```bash
cp observability/.env.example observability/.env
```

Generate a strong local Spendly secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Edit `observability/.env` and replace both placeholder values. Never commit this file.

Using an explicit env file also prevents `docker compose ... ps` and `logs` from failing in a new Claude/background-agent shell just because previously exported environment variables are not present there.

## Validate before starting

```bash
docker compose --env-file observability/.env -f observability/compose.yaml config
```

After images are available, Prometheus rules can also be checked from the running container with Prometheus tooling if needed. The local workflow should treat configuration validation as a gate before startup.

## Start or upgrade the full Phase 1-3 stack

```bash
docker compose --env-file observability/.env -f observability/compose.yaml up -d --build
```

If Phase 1 is already running, the same command recreates only what changed and adds the Phase 2-3 services/configuration.

## Verify

```bash
docker compose --env-file observability/.env -f observability/compose.yaml ps
curl http://localhost:5001/healthz
curl http://localhost:5001/readyz
curl http://localhost:5001/metrics
curl http://localhost:9090/-/ready
curl http://localhost:3100/ready
curl http://localhost:12345/-/ready
```

Open:

- Spendly: `http://localhost:5001`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Loki readiness/API: `http://localhost:3100`
- Alloy debugging UI: `http://localhost:12345`

Grafana username is `admin`; the password is the value in `GRAFANA_ADMIN_PASSWORD` from `observability/.env`.

Provisioned dashboards include:

- **Spendly Local Observability** — Phase 1 black-box health/readiness view
- **Spendly AI Observability — Metrics + Logs** — Phase 2-3 RED/process metrics and Loki log panels

## Useful PromQL

```promql
up
probe_success{job="spendly-blackbox"}
probe_duration_seconds{job="spendly-blackbox"}
probe_http_status_code{job="spendly-blackbox"}
sum(rate(spendly_http_requests_total[1m]))
sum by (route, status) (rate(spendly_http_requests_total[5m]))
histogram_quantile(0.95, sum by (le, route) (rate(spendly_http_request_duration_seconds_bucket[5m])))
process_resident_memory_bytes{job="spendly-app"}
rate(process_cpu_seconds_total{job="spendly-app"}[5m])
ALERTS{alertstate="firing"}
```

## Useful LogQL / Loki API

Grafana Explore query for Spendly logs:

```logql
{stack="spendly-observability",service_name="spendly"}
```

All stack logs:

```logql
{stack="spendly-observability"}
```

Read-only Loki API example for the last 15 minutes:

```bash
curl -sG http://localhost:3100/loki/api/v1/query_range \
  --data-urlencode 'query={stack="spendly-observability",service_name="spendly"}' \
  --data-urlencode 'since=15m' \
  --data-urlencode 'limit=100' \
  --data-urlencode 'direction=backward'
```

## Local Prometheus alert rules

`observability/prometheus/rules/spendly-alerts.yml` evaluates these conditions:

- black-box endpoint probe failure
- missing Spendly `/metrics` scrape
- p95 application latency above 500 ms
- 5xx ratio above 5%

There is intentionally **no Alertmanager notification integration yet**. A firing rule is visible in Prometheus/Grafana and to the AI analyst, but it does not page or send email/Slack. Notification routing is a later operationalization step.

## AI-assisted analysis with Claude Code

After the stack is running:

```text
/observe-local
```

Examples:

```text
/observe-local explain whether the application is healthy and correlate metrics with the last 15 minutes of Spendly logs
```

```text
/observe-local investigate why p95 latency increased and show the Prometheus evidence plus any matching Spendly log evidence
```

```text
/observe-local check for firing alerts, 5xx errors, readiness problems, and relevant Loki logs
```

The analyst is read-only. It may query Prometheus/Loki and inspect bounded Docker logs/container state. It must not restart containers, edit configuration, delete volumes, rebuild images, or mutate cloud resources.

## Stop

Preserve local data:

```bash
docker compose --env-file observability/.env -f observability/compose.yaml down
```

Do not automate `down -v`: it intentionally deletes the local Spendly database plus Prometheus, Grafana, Loki and Alloy state.

## Current boundary

Phase 3 centralizes container logs, but it does not yet add distributed tracing. OpenTelemetry traces/service dependency analysis should be treated as the next separate phase so metrics/logging changes remain understandable and reversible.
