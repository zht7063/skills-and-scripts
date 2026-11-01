#!/usr/bin/env bash
# LOCAL. 20 sequential HTTP requests through the local proxy, 1 s apart; prints per-request
# timing and summary (success, mean, median, p95, min, max in ms).
# Usage: perf-baseline.sh http://127.0.0.1:7890 [N=20]
set -uo pipefail
PROXY="${1:?proxy url}"; N="${2:-20}"
tmp="$(mktemp)"
for i in $(seq 1 "$N"); do
  curl -4 -sS -o /dev/null --max-time 10 -x "$PROXY" \
    -w "HTTP:%{http_code} TTFB:%{time_starttransfer}s Total:%{time_total}s\n" \
    https://www.google.com/generate_204 | tee -a "$tmp"
  sleep 1
done
python3 - "$tmp" "$N" <<'PY'
import re, sys, statistics as st
rows = [l for l in open(sys.argv[1]) if l.startswith("HTTP:")]
ok = [float(re.search(r"Total:([\d.]+)s", l).group(1)) * 1000 for l in rows if l.startswith("HTTP:204")]
n = int(sys.argv[2])
print(f"success {len(ok)}/{n}")
if ok:
    ok.sort()
    k = 0.95 * (len(ok) - 1); f = int(k); c = min(f + 1, len(ok) - 1)
    p95 = ok[f] + (ok[c] - ok[f]) * (k - f)
    print(f"mean {st.mean(ok):.1f} ms  median {st.median(ok):.1f} ms  p95 {p95:.1f} ms  min {ok[0]:.1f}  max {ok[-1]:.1f}")
PY
rm -f "$tmp"
