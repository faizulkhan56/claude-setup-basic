# Spendly Local Observability

This stack adds a local Prometheus + Grafana observability layer around Spendly without changing the Flask application or adding a Python dependency.

## What it monitors

- `/healthz` availability through Prometheus Blackbox Exporter
- `/readyz` database readiness through Prometheus Blackbox Exporter
- HTTP response status for the probes
- End-to-end probe duration
- Per-phase HTTP probe timings
- Prometheus scrape health

The stack intentionally starts with **external service-level signals** rather than application-internal request counters. This keeps the first observability phase low-risk and compatible with the repo's "no new pip packages" rule. Application instrumentation can be added later as a separate decision.

## Components

- Spendly container — built from the repository `Dockerfile`
- Prometheus — collects and stores metrics
- Blackbox Exporter — probes Spendly over HTTP
- Grafana — visualizes the metrics

## Start

From the repository root:

```bash
export SPENDLY_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export GRAFANA_ADMIN_PASSWORD="change-me-local"
docker compose -f observability/compose.yaml up -d --build
```

Windows PowerShell equivalent:

```powershell
$env:SPENDLY_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
$env:GRAFANA_ADMIN_PASSWORD = "change-me-local"
docker compose -f observability/compose.yaml up -d --build
```

## Verify

```bash
docker compose -f observability/compose.yaml ps
curl http://localhost:5001/healthz
curl http://localhost:5001/readyz
curl http://localhost:9090/-/ready
```

Open:

- Spendly: `http://localhost:5001`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Grafana username is `admin`; password is the value in `GRAFANA_ADMIN_PASSWORD`.
The Prometheus data source and **Spendly Local Observability** dashboard are provisioned automatically.

## Useful PromQL

```promql
probe_success{job="spendly-blackbox"}
probe_duration_seconds{job="spendly-blackbox"}
probe_http_status_code{job="spendly-blackbox"}
probe_http_duration_seconds{job="spendly-blackbox"}
up
```

## AI-assisted analysis with Claude Code

The repo includes `/observe-local`, backed by the `spendly-observability` skill and `spendly-observability-analyst` agent.

After the stack is running, ask Claude Code:

```text
/observe-local
```

or:

```text
/observe-local investigate why Spendly readiness is slow
```

The analyst is read-only. It queries Prometheus and inspects container status/logs, explains likely causes, and recommends the next verification step. It does not restart containers or change configuration.

## Stop

Preserve all named-volume data:

```bash
docker compose -f observability/compose.yaml down
```

To intentionally remove the local Prometheus, Grafana, and Spendly volumes as well, first understand that this deletes local data, then run the destructive command yourself. The AI workflow deliberately does not automate volume deletion.
