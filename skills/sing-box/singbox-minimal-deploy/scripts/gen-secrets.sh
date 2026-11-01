#!/usr/bin/env bash
# Generate the Shadowsocks 2022 password for the minimal deployment. Runs LOCALLY, no remote call.
# (UUID / REALITY keypair / short id are generated later by
#  singbox-reality-perf-troubleshoot/scripts/gen-reality-secrets.sh.)
# Usage: gen-secrets.sh ./singbox-work/secrets.env
set -euo pipefail
umask 077
ENV_FILE="${1:?usage: gen-secrets.sh path/to/secrets.env}"

# SS 2022 key: 16 random bytes, base64 (matches 2022-blake3-aes-128-gcm)
ss_password="$(openssl rand -base64 16)"
[ -n "$ss_password" ] || { echo "empty value for ss_password" >&2; exit 1; }

# rewrite SS_PASSWORD in the env file (keep everything else)
tmp="$(mktemp)"
grep -v -E '^SS_PASSWORD=' "$ENV_FILE" > "$tmp" || true
echo "SS_PASSWORD=$ss_password" >> "$tmp"
mv "$tmp" "$ENV_FILE"; chmod 600 "$ENV_FILE"
echo "secrets written to $ENV_FILE (values not printed)"
