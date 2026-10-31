---
name: singbox-dns-routing
description: Check and tune DNS and routing (分流) for a deployed sing-box node and its Clash / mihomo profile - Fake-IP, DoH nameserver, DNS 泄露 / DNS leak checks, DIRECT rules for LAN / overlay (EasyTier) ranges, rule order, IPv6, Clash Verge Global Extend Config conflicts. Use for DNS 污染, DNS 泄露, 分流规则, 规则优化, 局域网不通, Clash dns 配置, Fake-IP 198.18, "which traffic goes through the proxy". Builds on singbox-minimal-deploy (deploy it first). Not for UDP proof (singbox-udp), VLESS-REALITY setup, or sshd changes.
---

# sing-box DNS and routing / 分流 (incremental on top of the minimal deployment)

**Prerequisite: `singbox-minimal-deploy` is deployed** (container `sing-box` Up, `./singbox-work/secrets.env` and the basic `./singbox-work/clash.yaml` exist and the node passed base step 7). This skill does not repeat any deployment step; it inspects the DNS/routing parts of the base profile and adds changes on top. If the base is missing, stop and run `singbox-minimal-deploy` (or `singbox-deploy-full`) first.

**Local agent.** Every step is marked **[LOCAL]** or **[REMOTE]** (remote = over `ssh`, read-only here). Hard rules: never change SSH configuration on the server (sshd, `authorized_keys`, SSH port, SSH firewall rules, passwords, users); all sing-box files on the server stay in `/opt/sing-box/` (`REMOTE_DIR`); never modify the server config for DNS/routing without the user's explicit request (this skill's changes are client-side); secrets stay in `./singbox-work/`; one change at a time, keep the original files; do not claim unconfirmed root causes.

Session setup (**[LOCAL]**):
```bash
SB_DIR=/path/to/skills/sing-box
set -a; . ./singbox-work/secrets.env; set +a
REMOTE_DIR=/opt/sing-box
SSH="ssh -p ${SSH_PORT} -i ${SSH_KEY} -o StrictHostKeyChecking=accept-new ${SSH_USER}@${SERVER_IP}"
```

## 0. Base check (read-only)

- **[LOCAL]** the base profile exists and validates: `python3 $SB_DIR/singbox-minimal-deploy/scripts/validate_clash.py ./singbox-work/clash.yaml` prints `OK`; it contains the `dns:` block and the rules below.
- **[REMOTE, read-only]** `$SSH "cd ${REMOTE_DIR} && docker compose ps"` shows `sing-box` Up.

## 1. What the base profile does (existing behaviour, from `templates/clash.ss.yaml.tpl`)

```yaml
dns:
  enable: true
  ipv6: false
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  nameserver:
    - 'https://1.1.1.1/dns-query#PROXY'
  proxy-server-nameserver:
    - 'https://1.1.1.1/dns-query'
...
rules:
  - IP-CIDR,127.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
  - IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
  - IP-CIDR,169.254.0.0/16,DIRECT,no-resolve
  - MATCH,PROXY
```

- The `dns` block is the version moved into the profile (not Global Extend Config). `'...#PROXY'` makes the DoH query use the `PROXY` group: confirm it behaves as expected in the target client.
- Fake-IP answers (`198.18.x.x`) prove local DNS takeover only, not absence of DNS leaks.
- Rule order: private/loopback ranges DIRECT first, `MATCH,PROXY` last. These IPv4 rules do not cover IPv6 or every LAN/overlay (e.g. EasyTier) range.
- Mihomo `ipv6: false` only affects the client resolver, not macOS IPv6.
- The **server** resolves destination domains with its own `/etc/resolv.conf` (recorded: plain UDP 53 to 8.8.8.8 / 1.1.1.1; the sing-box `direct` outbound uses system DNS). Accepted risk in the recorded setup - document it as "accepted", never as "zero DNS leak".

## 2. Verify DNS behaviour (record results, do not over-claim)

1. **[LOCAL]** `dig @1.1.1.1 google.com +notcp` with TUN/Fake-IP active returns `198.18.x.x` -> local DNS takeover only (expected; does **not** prove no leak or that DNS traversed the VPS).
2. **[LOCAL]** optionally capture the local physical NIC for plain port-53 traffic: `sudo tcpdump -ni <nic> -q '(udp port 53 or tcp port 53)'` (needs sudo - ask the user).
3. **[REMOTE, read-only]** server resolver: `$SSH 'cat /etc/resolv.conf'` (compare with the recorded 8.8.8.8 / 1.1.1.1).
4. **IPv6** (**[LOCAL]** + **[REMOTE]**): `curl -6 --max-time 8 -x http://127.0.0.1:${LOCAL_MIXED_PORT} https://api64.ipify.org`; compare with `$SSH 'curl -6 --max-time 10 https://api64.ipify.org'` (equal -> the request exits via the VPS; if the VPS has no IPv6 this fails, which is informational).

## 3. Routing (分流) changes

### 3.1 LAN / overlay ranges must be DIRECT

Symptom: LAN or overlay (e.g. EasyTier) target unreachable with the proxy on - private ranges are not DIRECT. Action: extend the DIRECT `IP-CIDR` rules (+ IPv6 ranges if needed) of the profile, then verify `ping`/`curl` to the LAN target works with the proxy on.

1. **[LOCAL]** work on a local copy of the template, never on the repo file:
   ```bash
   cp $SB_DIR/singbox-minimal-deploy/templates/clash.ss.yaml.tpl ./singbox-work/clash.custom.yaml.tpl
   ```
   (If the VLESS node was added, copy `$SB_DIR/singbox-reality-perf-troubleshoot/templates/clash.ss-vless.yaml.tpl` instead.)
2. **[LOCAL]** insert extra DIRECT lines of the same form **before** the final `MATCH,PROXY`, e.g. `  - IP-CIDR,<user's overlay range>,DIRECT,no-resolve` (the user supplies the ranges; do not guess them).
3. **[LOCAL]** render and validate:
   ```bash
   python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py ./singbox-work/clash.custom.yaml.tpl ./singbox-work/clash.yaml --env-file ./singbox-work/secrets.env
   python3 $SB_DIR/singbox-minimal-deploy/scripts/validate_clash.py ./singbox-work/clash.yaml   # must print OK, last rule MATCH,<group>
   ```
   (`mihomo -t -d singbox-work -f singbox-work/clash.yaml` if mihomo is installed.) Re-import in the client and re-run base step 7 for the node(s).

### 3.2 DNS settings lost or duplicated in Clash Verge

Cause: DNS in Global Extend Config vs profile; Runtime Config is read-only. Action: keep `dns:` in the local profile, remove duplicates in Global Extend Config, re-activate. Verify: inspect Runtime Config for the expected values.

### 3.3 iOS Stash / Shadowrocket

Import may fail: they are not fully Mihomo-compatible. Generate an adapted client config separately; test node protocol, DNS, rules, VPN takeover; record differences.

## Troubleshooting pointers

The DNS/routing symptom rows (Fake-IP `198.18.x.x`, DNS test shows Google resolvers, DNS settings lost, LAN/overlay unreachable, IPv6 egress, Stash/Shadowrocket) are also listed in `singbox-reality-perf-troubleshoot/references/troubleshooting.md`.

## TODO (gaps - not invented here; the existing skills contain no procedure for these)

- TODO: encrypted DNS (DoH/DoT) on the **server** side. The existing notes only say "stronger option = plan DoH/DoT for the server and re-verify with captures"; no sing-box `dns` configuration is defined or tested yet.
- TODO: geo-based 分流 (e.g. domestic sites DIRECT via GEOIP/GEOSITE or rule providers, ad blocking) - the base profile only has private-range DIRECT + `MATCH,PROXY`.
- TODO: multi-node groups (url-test / fallback) and per-domain routing rules.
- TODO: a repeatable DNS-leak test procedure (the current checks prove local takeover only).

## Verification summary (report to the user, no secrets)

- [ ] base profile validated before the change; `validate_clash.py` OK after
- [ ] Fake-IP / local takeover observed (stated as takeover only)
- [ ] server resolver recorded and reported as an accepted risk (not "zero leak")
- [ ] LAN/overlay targets reachable with the proxy on (if changed)
- [ ] IPv6 result recorded (informational)
