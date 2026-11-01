#!/usr/bin/env python3
"""[LOCAL] Judge from mihomo's own records whether domestic hosts went DIRECT and foreign hosts via the proxy.

The traffic is generated elsewhere (a browser started with `agent-browser --proxy http://127.0.0.1:<mixed-port>`,
see singbox-dns-routing SKILL.md section 4). This script never sends test traffic through the proxy and
never uses an environment proxy: it only reads mihomo's log file and/or its local REST controller.

Evidence sources (use either or both):
  --log FILE            mihomo stdout log (log-level info). Lines look like
                        [TCP] 127.0.0.1:53074 --> www.baidu.com:443 match DomainSuffix(baidu.com) using DIRECT
                        [TCP] 127.0.0.1:53050 --> api.ipify.org:443 match Match using PROXY[My-sing-box]
                        A log is a complete record (closed connections too). Use --since to skip older lines.
  --controller H:P      REST controller, e.g. 127.0.0.1:19090 (GET /connections: ACTIVE connections only, so
                        take the snapshot while the page is still open). --secret S if the profile sets one.

Usage:
  domestic-direct-test.py --log mihomo.log --print-offset            # print the current end-of-log offset (a mark)
  domestic-direct-test.py --log mihomo.log --since OFFSET --direct baidu.com,qq.com --proxy api.ipify.org,github.com
  domestic-direct-test.py --controller 127.0.0.1:19090 --direct baidu.com --proxy api.ipify.org

A host matches a domain when it equals it or ends with ".<domain>". Verdict per expected domain:
  PASS      seen, and every record agrees (DIRECT for --direct, not DIRECT for --proxy)
  FAIL      at least one record disagrees
  NOT SEEN  no record (the browser never visited it / the log mark is wrong) - inconclusive, not a pass
Exit code: 0 all PASS, 1 any FAIL, 2 no FAIL but something NOT SEEN.
Other hosts the browser contacted (CDNs, telemetry) are listed separately with --show-other and never judged.
"""
import argparse, json, os, re, sys, urllib.request

LINE = re.compile(r'--> (?P<host>\[[^\]]+\]|[^\s:]+):(?P<port>\d+) (?:match (?P<rule>.+?) )?using (?P<chain>[^\s"]+)')


def from_log(path, since):
    recs = []
    with open(path, "rb") as fh:
        fh.seek(since)
        for raw in fh:
            m = LINE.search(raw.decode("utf-8", "replace"))
            if m:
                recs.append((m["host"].strip("[]").lower(), m["rule"] or "(none)", m["chain"]))
    return recs


def from_controller(addr, secret):
    req = urllib.request.Request(f"http://{addr}/connections")
    if secret:
        req.add_header("Authorization", "Bearer " + secret)
    # explicit empty ProxyHandler: the controller is on loopback and must never go through any proxy
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    data = json.load(opener.open(req, timeout=10))
    recs = []
    for c in data.get("connections") or []:
        md = c.get("metadata", {})
        host = (md.get("host") or md.get("sniffHost") or md.get("destinationIP") or "").lower()
        chains = c.get("chains") or []
        chain = "DIRECT" if chains[:1] == ["DIRECT"] else (f"PROXY[{chains[0]}]" if chains else "?")
        recs.append((host, f'{c.get("rule", "")}({c.get("rulePayload", "")})', chain))
    return recs


def matches(host, dom):
    return host == dom or host.endswith("." + dom)


def judge(recs, doms, want_direct):
    worst = 0   # 0 pass, 1 fail, 2 not seen (a FAIL always wins over NOT SEEN)
    for dom in doms:
        rows = [r for r in recs if matches(r[0], dom)]
        if not rows:
            print(f"NOT SEEN  {dom}"); worst = worst or 2; continue
        bad = [r for r in rows if (r[2] == "DIRECT") != want_direct]
        want = "DIRECT" if want_direct else "proxy"
        if bad:
            print(f"FAIL      {dom}  expected {want}, got {bad[0][2]} via rule {bad[0][1]} ({len(bad)}/{len(rows)} records)")
            worst = 1
        else:
            print(f"PASS      {dom}  {want}: {len(rows)} record(s), e.g. {rows[0][0]} {rows[0][1]} -> {rows[0][2]}")
    return worst


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log"); ap.add_argument("--since", type=int, default=0)
    ap.add_argument("--print-offset", action="store_true")
    ap.add_argument("--controller"); ap.add_argument("--secret", default=os.environ.get("MIHOMO_SECRET", ""))
    ap.add_argument("--direct", default=""); ap.add_argument("--proxy", default="")
    ap.add_argument("--show-other", action="store_true")
    a = ap.parse_args()
    if a.print_offset:
        if not a.log: sys.exit("--print-offset needs --log")
        print(os.path.getsize(a.log)); return
    if not (a.log or a.controller): sys.exit("give --log and/or --controller")
    direct = [d.strip().lower() for d in a.direct.split(",") if d.strip()]
    proxy = [d.strip().lower() for d in a.proxy.split(",") if d.strip()]
    if not (direct or proxy): sys.exit("give --direct and/or --proxy domains")
    worst = 0
    sources = []
    if a.log: sources.append((f"log {a.log} from offset {a.since}", from_log(a.log, a.since)))
    if a.controller: sources.append((f"controller {a.controller} /connections", from_controller(a.controller, a.secret)))
    for name, recs in sources:
        print(f"== {name}: {len(recs)} record(s)")
        for w in (judge(recs, direct, True), judge(recs, proxy, False)):
            worst = 1 if 1 in (worst, w) else (worst or w)
        if a.show_other:
            other = sorted({(h, c) for h, _, c in recs if not any(matches(h, d) for d in direct + proxy)})
            for h, c in other: print(f"   other: {h} -> {c}")
    print({0: "RESULT: PASS", 1: "RESULT: FAIL", 2: "RESULT: INCONCLUSIVE (some domains not seen)"}[worst])
    sys.exit(worst)

if __name__ == "__main__":
    main()
