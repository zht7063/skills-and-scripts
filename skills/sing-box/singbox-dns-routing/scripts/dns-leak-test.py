#!/usr/bin/env python3
"""[LOCAL] Repeatable DNS-leak test: which resolvers does the world see when this machine looks up unique names?

How it works (bash.ws leak-test API, the service behind dnsleaktest-style pages):
  1. GET <api>/id gives a random test id.
  2. The script triggers lookups of <n>.<id>.<domain> (default domain bash.ws). Only the authoritative server of that
     domain sees the recursive resolver that asked, so the resolver IPs it reports are exactly the resolvers in use.
       mode system (default)  : socket.getaddrinfo, i.e. the OS resolver path (what a TUN/fake-ip setup must take over)
       mode proxy (--via-proxy HOST:PORT): HTTP requests through the local client's mixed port; the *proxy* resolves
                                the names, which is what a browser using the proxy does.
  3. GET <api>/dnsleak/test/<id>?json returns the resolver list; this script prints the resolver IPs.
Verdict needs a BASELINE of the resolvers used WITHOUT the client (ISP resolvers):
  step 1 (client OFF):  dns-leak-test.py --save-baseline baseline.txt
  step 2 (client ON):   dns-leak-test.py [--via-proxy 127.0.0.1:7890] --baseline baseline.txt
  Any resolver IP also present in the baseline = LEAK (exit 1). No overlap = PASS (exit 0).
  Without --baseline it only lists the resolvers (exit 0) - you judge them (are they your ISP's?).
Manual fallback if bash.ws is unreachable: open https://dnsleak.dev in the browser and record its verdict by hand.
Standard library only. Sends nothing but the random id and the lookups; no credentials, no local IPs.
"""
import argparse, json, socket, sys, time, urllib.request


def get(url, opener, timeout=15):
    with opener.open(urllib.request.Request(url, headers={"User-Agent": "dns-leak-test/1"}), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def resolver_ips(payload):
    """Tolerant parse: entries are dicts with an 'ip' and a 'type' (dns = resolver; others are the client / conclusion)."""
    data = json.loads(payload)
    items = data if isinstance(data, list) else data.get("results", data.get("data", []))
    return sorted({str(i["ip"]) for i in items if isinstance(i, dict) and i.get("type") == "dns" and i.get("ip")})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="https://bash.ws"); ap.add_argument("--domain", default="bash.ws")
    ap.add_argument("--via-proxy", metavar="HOST:PORT"); ap.add_argument("--count", type=int, default=8)
    ap.add_argument("--save-baseline", metavar="FILE"); ap.add_argument("--baseline", metavar="FILE")
    ap.add_argument("--wait", type=float, default=3.0, help="seconds to let the service collect (default 3)")
    a = ap.parse_args()
    # the API itself is fetched WITHOUT any proxy: only the lookups are what we steer
    api = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        tid = get(f"{a.api}/id", api).strip()
    except Exception as e:
        print(f"SETUP FAIL: cannot get a test id from {a.api} ({e.__class__.__name__}); use the manual fallback"); return 2
    if not tid.isalnum():
        print("SETUP FAIL: unexpected id format"); return 2
    px = urllib.request.build_opener(urllib.request.ProxyHandler({"http": f"http://{a.via_proxy}"})) if a.via_proxy else None
    print(f"test id {tid}; mode {'proxy ' + a.via_proxy if px else 'system resolver'}; {a.count} lookups")
    for n in range(1, a.count + 1):
        name = f"{n}.{tid}.{a.domain}"
        try:
            if px: get(f"http://{name}/", px, timeout=8)
            else: socket.getaddrinfo(name, 80)
        except Exception:
            pass  # the name only has to be looked up; the lookup (not the connection) is the measurement
    time.sleep(a.wait)
    try:
        ips = resolver_ips(get(f"{a.api}/dnsleak/test/{tid}?json", api))
    except Exception as e:
        print(f"FAIL: could not read results ({e.__class__.__name__})"); return 2
    print("resolver IPs seen: " + (", ".join(ips) or "(none - lookups did not reach the service)"))
    if not ips: return 2
    if a.save_baseline:
        open(a.save_baseline, "w").write("\n".join(ips) + "\n"); print(f"baseline saved to {a.save_baseline}"); return 0
    if a.baseline:
        base = set(open(a.baseline).read().split()); both = sorted(base & set(ips))
        if both: print("LEAK: baseline (non-proxied) resolvers still in use: " + ", ".join(both)); return 1
        print("PASS: no overlap with the baseline resolvers"); return 0
    print("INFO: no --baseline given; judge the list yourself"); return 0


if __name__ == "__main__":
    sys.exit(main())
