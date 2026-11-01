#!/usr/bin/env python3
"""Static validation of a rendered Clash/mihomo YAML. Usage: validate_clash.py clash.yaml"""
import re, sys, yaml

d = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
errs = []
proxies = {p["name"]: p for p in d.get("proxies", [])}
if not proxies:
    errs.append("no proxies")
for n, p in proxies.items():
    for k in ("server", "port", "type"):
        if k not in p:
            errs.append(f"{n}: missing {k}")
    if p.get("type") == "ss" and not p.get("password"):
        errs.append(f"{n}: empty ss password")
    if p.get("type") == "vless":
        ro = p.get("reality-opts", {})
        for k in ("public-key", "short-id"):
            if not ro.get(k):
                errs.append(f"{n}: reality-opts.{k} missing")
        for k in ("uuid", "servername"):
            if not p.get(k):
                errs.append(f"{n}: {k} missing")
groups = {g["name"]: g for g in d.get("proxy-groups", [])}
for g in groups.values():
    for m in g.get("proxies", []):
        if m not in proxies and m not in groups and m not in ("DIRECT", "REJECT"):
            errs.append(f"group {g['name']}: unknown member {m}")
rules = d.get("rules", [])
if not rules or not str(rules[-1]).startswith("MATCH,"):
    errs.append("last rule must be MATCH,<group>")
for r in rules:
    t = str(r).split(",")
    tgt = t[2] if t[0].startswith("IP-CIDR") else t[-1]
    if tgt not in groups and tgt not in ("DIRECT", "REJECT"):
        errs.append(f"rule {r}: unknown target")
blob = open(sys.argv[1], encoding="utf-8").read()
for m in re.findall(r"TODO\w*", blob):
    errs.append(f"unresolved placeholder {m}")
if re.search(r"\$\{[A-Z_]+\}", blob):
    errs.append("unrendered ${VAR} left in file")
if errs:
    print("INVALID:\n- " + "\n- ".join(errs)); sys.exit(1)
print("OK: YAML valid;", len(proxies), "proxies,", len(groups), "groups,", len(rules), "rules")
