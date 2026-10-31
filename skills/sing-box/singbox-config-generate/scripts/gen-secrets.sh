#!/usr/bin/env bash
# Generate SS password, VLESS UUID, REALITY keypair and short id.
# Runs LOCALLY; the only remote call is `docker run --rm` of the official sing-box image
# (so the keypair/uuid come from the same sing-box version that will serve them).
# Usage: gen-secrets.sh ./singbox-work/secrets.env     (file must already contain SERVER_IP/SSH_*)
set -euo pipefail
umask 077
ENV_FILE="${1:?usage: gen-secrets.sh path/to/secrets.env}"
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a
SSH=(ssh -p "$SSH_PORT" -i "$SSH_KEY" "$SSH_USER@$SERVER_IP")
IMG="ghcr.io/sagernet/sing-box:latest"

# 1. SS 2022 key: 16 random bytes, base64 (matches 2022-blake3-aes-128-gcm)
ss_password="$(openssl rand -base64 16)"
# 2. short id: 8 random bytes hex (16 chars)
short_id="$(openssl rand -hex 8)"
# 3. UUID + REALITY keypair from sing-box itself  [REMOTE: docker run --rm, no persistent change]
vless_uuid="$("${SSH[@]}" "docker run --rm $IMG generate uuid" | tr -d '\r\n')"
kp="$("${SSH[@]}" "docker run --rm $IMG generate reality-keypair" | tr -d '\r')"
priv="$(printf '%s\n' "$kp" | awk '/PrivateKey/{print $2}')"
pub="$(printf '%s\n' "$kp" | awk '/PublicKey/{print $2}')"

for v in ss_password short_id vless_uuid priv pub; do
  [ -n "${!v}" ] || { echo "empty value for $v" >&2; exit 1; }
done

# rewrite the five variables in the env file (keep everything else)
tmp="$(mktemp)"
grep -v -E '^(SS_PASSWORD|VLESS_UUID|REALITY_PRIVATE_KEY|REALITY_PUBLIC_KEY|SHORT_ID)=' "$ENV_FILE" > "$tmp" || true
{
  echo "SS_PASSWORD=$ss_password"
  echo "VLESS_UUID=$vless_uuid"
  echo "REALITY_PRIVATE_KEY=$priv"
  echo "REALITY_PUBLIC_KEY=$pub"
  echo "SHORT_ID=$short_id"
} >> "$tmp"
mv "$tmp" "$ENV_FILE"; chmod 600 "$ENV_FILE"
echo "secrets written to $ENV_FILE (values not printed)"
