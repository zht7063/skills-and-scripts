#!/usr/bin/env bash
# LOCAL. Verify that traffic through the local client's mixed port exits from SERVER_IP.
# Usage: egress-check.sh ./singbox-work/secrets.env
set -uo pipefail
set -a; source "${1:?env file}"; set +a
P="http://127.0.0.1:${LOCAL_MIXED_PORT}"
fail=0
direct_ip="$(curl -4 -sS --max-time 10 https://api.ipify.org || echo '?')"
proxy_ip="$(curl -4 -sS --max-time 15 -x "$P" https://api.ipify.org || echo '?')"
echo "direct egress : $direct_ip"
echo "proxied egress: $proxy_ip   (expected: $SERVER_IP)"
[ "$proxy_ip" = "$SERVER_IP" ] || { echo "FAIL: proxied egress != SERVER_IP"; fail=1; }
[ "$direct_ip" != "$proxy_ip" ] || echo "WARN: direct and proxied IP equal - test not conclusive (is local machine behind the same egress?)"
code="$(curl -4 -sS -o /dev/null -w '%{http_code}' --max-time 15 -x "$P" https://www.google.com/generate_204 || echo 000)"
echo "generate_204 via proxy: HTTP $code (expected 204)"
[ "$code" = "204" ] || { echo "FAIL: generate_204"; fail=1; }
# IPv6 is informational only (server may have no IPv6)
v6="$(curl -6 -sS --max-time 8 -x "$P" https://api64.ipify.org 2>/dev/null || echo 'n/a')"
echo "ipv6 via proxy (informational): $v6"
exit $fail
