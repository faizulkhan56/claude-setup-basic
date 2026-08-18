#!/usr/bin/env bash
# Phase 2 — one-time (idempotent) host bootstrap for the Spendly EC2 VM.
# Run as root (or via sudo) over an SSM Session Manager session — port 22 is
# never opened on this box, see deploy/vm's security-group commands.
#
# What it does:
#   1. Installs Docker Engine + Compose plugin, nginx, sqlite3 (for backups),
#      git (the image is built ON this VM from a git clone — no ECR).
#   2. Formats and mounts the second EBS volume at /var/lib/spendly.
#   3. chowns it to uid/gid 1001, which is the non-root `spendly` user baked
#      into the image by ../../Dockerfile — without this the container gets
#      "unable to open database file".
set -euo pipefail

curl -fsSL https://get.docker.com | sh
apt-get update
apt-get install -y nginx sqlite3 git unattended-upgrades

# Data disk. CONFIRM the device name with `lsblk` before the first run — on
# Nitro-based instances (t3, t3.micro included) the root volume is
# /dev/nvme0n1 and an attached data volume shows up as /dev/nvme1n1, but the
# exact suffix depends on attach order. Do not assume it.
DEV=/dev/nvme1n1
blkid "$DEV" >/dev/null 2>&1 || mkfs.ext4 -L spendly "$DEV"
mkdir -p /var/lib/spendly
grep -q 'LABEL=spendly' /etc/fstab || \
  echo 'LABEL=spendly /var/lib/spendly ext4 defaults,nofail 0 2' >> /etc/fstab
mount -a

# uid/gid must match the container's non-root user (see Dockerfile: spendly, 1001:1001)
chown 1001:1001 /var/lib/spendly

mkdir -p /etc/spendly
chmod 700 /etc/spendly

echo "bootstrap.sh complete. Next: clone the repo into /srv/spendly, build the"
echo "image, and install compose.yaml / spendly.service / nginx site config."
