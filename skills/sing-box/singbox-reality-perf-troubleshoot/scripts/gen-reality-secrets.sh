#!/usr/bin/env bash
# Generate VLESS UUID, REALITY keypair and short id (the SS password comes from the minimal deployment's gen-secrets.sh and is kept).
# Runs LOCALLY; the only remote call is `docker run --rm` of the official sing-box image
# (so the keypair/uuid come from the same sing-box version that will serve them).
# Usage: gen-reality-secrets.sh ./singbox-work/secrets.env     (file must already contain SERVER_IP/SSH_*)
set -euo pipefail
umask 077
ENV_FILE="${1:?usage: gen-reality-secrets.sh path/to/secrets.env}"
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a
SSH=(ssh -p "$SSH_PORT" -i "$SSH_KEY" "$SSH_USER@$SERVER_IP")
IMG="ghcr.io/sagernet/sing-box:latest"

# 1. short id: 8 random bytes hex (16 chars)
short_id="$(openssl rand -hex 8)"
# 2. UUID + REALITY keypair from sing-box itself  [REMOTE: docker run --rm, no persistent change]
vless_uuid="$("${SSH[@]}" "docker run --rm $IMG generate uuid" | tr -d '\r\n')"
kp="$("${SSH[@]}" "docker run --rm $IMG generate reality-keypair" | tr -d '\r')"
priv="$(printf '%s\n' "$kp" | awk '/PrivateKey/{print $2}')"
pub="$(printf '%s\n' "$kp" | awk '/PublicKey/{print $2}')"

for v in short_id vless_uuid priv pub; do
  [ -n "${!v}" ] || { echo "empty value for $v" >&2; exit 1; }
done

# rewrite the four variables in the env file (keep everything else)
tmp="$(mktemp)"
grep -v -E '^(VLESS_UUID|REALITY_PRIVATE_KEY|REALITY_PUBLIC_KEY|SHORT_ID)=' "$ENV_FILE" > "$tmp" || true
{
  echo "VLESS_UUID=$vless_uuid"
  echo "REALITY_PRIVATE_KEY=$priv"
  echo "REALITY_PUBLIC_KEY=$pub"
  echo "SHORT_ID=$short_id"
} >> "$tmp"
mv "$tmp" "$ENV_FILE"; chmod 600 "$ENV_FILE"
echo "secrets written to $ENV_FILE (values not printed)"
