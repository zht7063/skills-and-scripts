#!/usr/bin/env bash
# [LOCAL] Download-throughput test: the same file through the local proxy and directly (curl; iperf3 optional).
# Usage: throughput-test.sh [-x http://127.0.0.1:7890] [-n 3] [-b 10000000] [--iperf HOST[:PORT]]
#   -x  proxy URL of the local client's mixed port (default http://127.0.0.1:${LOCAL_MIXED_PORT:-7890})
#   -n  runs per path (default 3)      -b  bytes per download (default 10000000 = 10 MB)
#   --iperf HOST  [OPTIONAL, needs iperf3 and a reachable iperf3 server you control] extra TCP test, direct only
# Endpoints, tried in order until one works through the proxy (all public, no account):
#   https://speed.cloudflare.com/__down?bytes=N   (fallback 1)
#   https://proof.ovh.net/files/10Mb.dat          (fallback 2, fixed ~1.25 MB)
#   http://speedtest.tele2.net/10MB.zip           (fallback 3, fixed 10 MB)
# The direct run uses `curl --noproxy '*'` and ignores any *_proxy variable. Do NOT set env proxies for this script.
# Reading the result: compare MB/s proxy vs direct; the proxy path is bounded by server bandwidth and TCP/BBR, not by
# this script. A single 10 MB sample is noisy - use -n 5 and treat <20% differences as noise. Prints no secrets.
set -u
PROXY="http://127.0.0.1:${LOCAL_MIXED_PORT:-7890}"; N=3; BYTES=10000000; IPERF=""
while [ $# -gt 0 ]; do case "$1" in
  -x) PROXY="$2"; shift 2;; -n) N="$2"; shift 2;; -b) BYTES="$2"; shift 2;; --iperf) IPERF="$2"; shift 2;;
  -h|--help) sed -n '2,15p' "$0"; exit 0;; *) echo "unknown arg $1" >&2; exit 2;; esac; done
URLS=("https://speed.cloudflare.com/__down?bytes=$BYTES" "https://proof.ovh.net/files/10Mb.dat" "http://speedtest.tele2.net/10MB.zip")
# one timed download; prints "<bytes/s> <http_code>"
dl() { # $1 = proxy URL or "" for direct, $2 = url
  if [ -n "$1" ]; then curl -sS -m 60 -x "$1" -o /dev/null -w '%{speed_download} %{http_code}' "$2" 2>/dev/null
  else curl -sS -m 60 --noproxy '*' -o /dev/null -w '%{speed_download} %{http_code}' "$2" 2>/dev/null; fi
}
mbs() { awk -v b="$1" 'BEGIN{printf "%.2f", b/1048576}'; }
FAIL=0; PICK=""
for u in "${URLS[@]}"; do
  r=$(dl "$PROXY" "$u") || r="0 000"; code=${r##* }
  if [ "$code" = 200 ]; then PICK="$u"; echo "endpoint: $u"; break; else echo "  skip ($code): $u"; fi
done
[ -z "$PICK" ] && { echo "FAIL: no endpoint works through $PROXY"; exit 1; }
run() { # $1 label, $2 proxy-or-empty
  local sum=0 ok=0 i r s c
  for i in $(seq 1 "$N"); do
    r=$(dl "$2" "$PICK") || r="0 000"; s=${r% *}; c=${r##* }
    if [ "$c" = 200 ]; then ok=$((ok+1)); sum=$(awk -v a="$sum" -v b="$s" 'BEGIN{print a+b}'); echo "  $1 run $i: $(mbs "$s") MB/s"
    else echo "  $1 run $i: failed (http $c)"; fi
  done
  [ "$ok" -gt 0 ] && AVG=$(awk -v a="$sum" -v n="$ok" 'BEGIN{print a/n}') || AVG=0
  echo "$1 average: $(mbs "$AVG") MB/s over $ok/$N ok runs"
}
run proxy "$PROXY"; PA=$AVG
run direct "";      DA=$AVG
[ "$PA" = 0 ] && FAIL=1
awk -v p="$PA" -v d="$DA" 'BEGIN{ if (d>0 && p>0) printf "proxy/direct ratio: %.0f%%\n", 100*p/d; else print "ratio: n/a (a path had no successful run; direct may be blocked)" }'
if [ -n "$IPERF" ]; then
  if command -v iperf3 >/dev/null; then h=${IPERF%%:*}; p=${IPERF##*:}; [ "$p" = "$IPERF" ] && p=5201
    echo "[optional] iperf3 -c $h -p $p -t 10 (direct TCP, not through the proxy):"; iperf3 -c "$h" -p "$p" -t 10 2>&1 | tail -4
  else echo "[optional] iperf3 not installed - skipped"; fi
fi
[ "$FAIL" = 0 ] && echo "RESULT: PASS (proxy path delivered data)" || echo "RESULT: FAIL"
exit "$FAIL"
