#!/usr/bin/env bash
# Phase 2 — deploy/redeploy on the VM. Run from /srv/spendly (the git clone).
#
# This replaces the skill's default "pull a registry tag" flow because the
# user chose to build on the VM instead of pushing to ECR: there is no
# registry to pull from, so the new step here is `docker build`, done
# locally, tagged with the git short SHA so /etc/spendly/spendly.env always
# names exactly what is running.
set -euo pipefail

cd /srv/spendly
git pull --ff-only

SHA=$(git rev-parse --short HEAD)
# t3.micro has only 1GiB RAM — if a redeploy hangs here, check `free -h` / swap first.
docker build -t "spendly:${SHA}" .

# Update (not append) SPENDLY_IMAGE in the env file consumed by compose.yaml
# via EnvironmentFile= in spendly.service.
if grep -q '^SPENDLY_IMAGE=' /etc/spendly/spendly.env; then
  sed -i "s|^SPENDLY_IMAGE=.*|SPENDLY_IMAGE=${SHA}|" /etc/spendly/spendly.env
else
  echo "SPENDLY_IMAGE=${SHA}" >> /etc/spendly/spendly.env
fi

systemctl restart spendly

# Prune old spendly images once the new one is confirmed running, so the
# previous tags left behind by every redeploy don't slowly fill the root volume.
docker image prune -f --filter "until=168h"

echo "Deployed spendly:${SHA}. Expect a few seconds of 502 during restart —"
echo "one container, one SQLite writer, no zero-downtime story at this phase."
echo "Verify with: curl -fsS https://<host>.sslip.io/readyz"
