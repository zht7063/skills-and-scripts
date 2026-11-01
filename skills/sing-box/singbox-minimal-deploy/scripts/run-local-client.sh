#!/usr/bin/env bash
# LOCAL. Start a local client in the background, run egress-check, then stop it.
# Usage: run-local-client.sh mihomo   ./singbox-work/clash.yaml  [node-name]
#        run-local-client.sh sing-box ./singbox-work/client-ss.json
# Requires the `mihomo` or `sing-box` binary on PATH (install separately; this script installs nothing).
set -uo pipefail
KIND="${1:?mihomo|sing-box}"; CFG="${2:?config path}"; NODE="${3:-}"
ENV_FILE="${ENV_FILE:-./singbox-work/secrets.env}"
HERE="$(cd "$(dirname "$0")" && pwd)"
set -a; source "$ENV_FILE"; set +a
LOG="$(mktemp)"
case "$KIND" in
  mihomo)   mihomo -d "$(dirname "$CFG")" -f "$CFG" >"$LOG" 2>&1 & ;;
  sing-box) sing-box run -c "$CFG" >"$LOG" 2>&1 & ;;
  *) echo "unknown kind"; exit 2 ;;
esac
PID=$!
trap 'kill $PID 2>/dev/null; wait $PID 2>/dev/null; rm -f "$LOG"' EXIT
for _ in $(seq 1 20); do
  (exec 3<>/dev/tcp/127.0.0.1/"$LOCAL_MIXED_PORT") 2>/dev/null && break; sleep 0.5
done
if [ "$KIND" = mihomo ] && [ -n "$NODE" ]; then
  curl -sS -X PUT "http://127.0.0.1:${LOCAL_CONTROLLER_PORT}/proxies/PROXY" -d "{\"name\":\"$NODE\"}" -o /dev/null -w "select $NODE: HTTP %{http_code}\n"
fi
"$HERE/egress-check.sh" "$ENV_FILE"; rc=$?
echo "--- client log tail ---"; tail -n 15 "$LOG"
exit $rc
