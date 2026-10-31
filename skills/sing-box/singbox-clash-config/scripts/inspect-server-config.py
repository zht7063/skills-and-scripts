#!/usr/bin/env python3
"""READ-ONLY helper for an EXISTING sing-box server (not deployed by these skills).

Reads the server's config.json from STDIN (the agent fetched it with `ssh ... cat`, nothing is
written back to the server) and extracts the values the client profile must copy.

Usage:
  ssh -p $SSH_PORT -i $SSH_KEY $SSH_USER@$SERVER_IP "cat ${INSTALL_DIR}/config.json" \\
    | python3 inspect-server-config.py --env-out ./singbox-work/server-derived.env [--vless-tag TAG] [--user NAME]

- Prints a REDACTED summary (secrets are never printed).
- Writes ./singbox-work/server-derived.env (mode 600) with VLESS_FLOW (EMPTY if the user has no
  `flow` field), VLESS_UUID, SHORT_ID, REALITY_SNI, VLESS_PORT, SS_PORT, SS_METHOD, SS_PASSWORD.
  REALITY_PUBLIC_KEY is NOT in a server config (it holds the private key): get it from the user.
- If there are several VLESS inbounds/users, it stops and asks for --vless-tag / --user.
- Exit 2 on any ambiguity. It never modifies anything on the server.
"""
import argparse, json, os, sys

ap = argparse.ArgumentParser()
ap.add_argument("--env-out", required=True)
ap.add_argument("--vless-tag")
ap.add_argument("--user")
a = ap.parse_args()
try:
    cfg = json.load(sys.stdin)
except Exception as e:
    sys.exit(f"cannot parse config.json from stdin: {e}")

ib = cfg.get("inbounds", [])
out, notes = {}, []

vl = [i for i in ib if i.get("type") == "vless" and (not a.vless_tag or i.get("tag") == a.vless_tag)]
if len(vl) != 1:
    sys.exit(f"expected exactly 1 vless inbound, found {len(vl)} (tags: {[i.get('tag') for i in ib if i.get('type')=='vless']}); use --vless-tag")
v = vl[0]
users = [u for u in v.get("users", []) if not a.user or u.get("name") == a.user]
if len(users) != 1:
    sys.exit(f"expected exactly 1 vless user, found {len(users)} (names: {[u.get('name') for u in v.get('users', [])]}); use --user")
u = users[0]
tls = v.get("tls", {})
rl = tls.get("reality", {})
flow = u.get("flow", "")           # field absent -> empty string (the client must then use empty flow too)
out["VLESS_FLOW"] = flow
out["VLESS_UUID"] = u.get("uuid", "")
out["VLESS_PORT"] = str(v.get("listen_port", ""))
out["REALITY_SNI"] = tls.get("server_name", "")
out["SHORT_ID"] = (rl.get("short_id") or [""])[0] if isinstance(rl.get("short_id"), list) else rl.get("short_id", "")
hs = rl.get("handshake", {}).get("server", "")
if hs and hs != out["REALITY_SNI"]:
    notes.append(f"WARNING: tls.server_name ({out['REALITY_SNI']}) != reality.handshake.server ({hs}); client servername must be the server_name; report to the user, do NOT edit the server")
if not rl.get("enabled"):
    notes.append("WARNING: reality.enabled is not true on this inbound")

ss = [i for i in ib if i.get("type") == "shadowsocks"]
if len(ss) == 1:
    out["SS_PORT"] = str(ss[0].get("listen_port", ""))
    out["SS_METHOD"] = ss[0].get("method", "")
    out["SS_PASSWORD"] = ss[0].get("password", "")
elif ss:
    notes.append("several shadowsocks inbounds: SS values not extracted")

fd = os.open(a.env_out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as fh:
    for k, val in out.items():
        fh.write(f"{k}={val}\n")
os.chmod(a.env_out, 0o600)

secret = {"VLESS_UUID", "SHORT_ID", "SS_PASSWORD"}
print("existing-server summary (secrets redacted):")
for k, val in out.items():
    if k in secret:
        print(f"  {k} = <{len(val)} chars>")
    elif k == "VLESS_FLOW":
        print(f"  VLESS_FLOW = {val!r}" + ("   (field absent/empty -> client flow must be EMPTY)" if val == "" else ""))
    else:
        print(f"  {k} = {val}")
for n in notes:
    print(n)
print("written:", a.env_out, "(mode 600). Server was not modified.")
