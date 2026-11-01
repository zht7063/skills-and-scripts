#!/bin/sh
# [REMOTE] Size-based log rotation for sing-box. Uploaded to /opt/sing-box/rotate-logs.sh and run by
# the `log-rotate` service of compose.yaml (busybox sh inside the sing-box image). POSIX sh only.
#
# Every INTERVAL seconds: if sing-box.log >= MAX_BYTES, copy it to sing-box.log.1, truncate the live
# file (sing-box keeps writing to it: it opens the log with O_APPEND, so copy-truncate is safe),
# gzip the copy and shift older archives (.1.gz -> .2.gz ...). At most KEEP archives are kept.
# Worst case disk use: about MAX_BYTES + one interval of new logs + KEEP compressed archives.
# Lines written between the copy and the truncate can be lost (acceptable for connection logs).
#
# Usage: rotate-logs.sh           loop forever (the container's normal mode)
#        rotate-logs.sh --once    rotate now if the size limit is exceeded, then exit
# Overrides (env): LOG_DIR LOG_NAME MAX_BYTES KEEP INTERVAL
LOG_DIR="${LOG_DIR:-/var/log/sing-box}"
LOG_NAME="${LOG_NAME:-sing-box.log}"
MAX_BYTES="${MAX_BYTES:-10485760}"   # 10 MiB
KEEP="${KEEP:-3}"
INTERVAL="${INTERVAL:-300}"

rotate_once() {
  f="$LOG_DIR/$LOG_NAME"
  [ -f "$f" ] || return 0
  size=$(wc -c < "$f")
  [ "$size" -ge "$MAX_BYTES" ] || return 0
  rm -f "$f.$KEEP.gz"
  i=$KEEP
  while [ "$i" -gt 1 ]; do
    p=$((i - 1))
    [ -f "$f.$p.gz" ] && mv "$f.$p.gz" "$f.$i.gz"
    i=$p
  done
  if cp "$f" "$f.1" && : > "$f"; then
    gzip -f "$f.1"
    echo "rotate-logs: rotated $f ($size bytes)"
  else
    echo "rotate-logs: rotation of $f failed" >&2
  fi
}

if [ "${1:-}" = "--once" ]; then rotate_once; exit 0; fi
echo "rotate-logs: watching $LOG_DIR/$LOG_NAME (max $MAX_BYTES bytes, keep $KEEP, every ${INTERVAL}s)"
while true; do
  rotate_once
  sleep "$INTERVAL"
done
