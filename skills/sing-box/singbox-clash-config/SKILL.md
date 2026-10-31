---
name: singbox-clash-config
description: Use when a local agent must produce a ready-to-import Clash / Mihomo (Clash Verge, Stash-style) YAML profile for a deployed sing-box server with Shadowsocks 2022 and VLESS-REALITY nodes, from the bundled template and the generated credentials. Stage 6 of the sing-box deployment skill set.
---

# sing-box stage 6 - Clash (mihomo) profile

**Local agent, no remote commands.** Inputs: all variables in `./singbox-work/secrets.env`: `SERVER_IP SS_PORT SS_METHOD SS_PASSWORD VLESS_PORT VLESS_UUID VLESS_FLOW REALITY_PUBLIC_KEY SHORT_ID REALITY_SNI LOCAL_MIXED_PORT LOCAL_CONTROLLER_PORT`.

**Render from `templates/clash.yaml.tpl`. Do not rewrite the YAML by hand; do not use the REALITY *private* key on the client (only `REALITY_PUBLIC_KEY`).** `REALITY_SNI` must equal the value in the server config (`servername` here = `server_name` on the server).

## Template: `templates/clash.yaml.tpl`

```yaml
mixed-port: ${LOCAL_MIXED_PORT}
allow-lan: false
mode: rule
log-level: info
ipv6: false
external-controller: 127.0.0.1:${LOCAL_CONTROLLER_PORT}

dns:
  enable: true
  ipv6: false
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  nameserver:
    - 'https://1.1.1.1/dns-query#PROXY'
  proxy-server-nameserver:
    - 'https://1.1.1.1/dns-query'

proxies:
  - name: My-sing-box
    type: ss
    server: ${SERVER_IP}
    port: ${SS_PORT}
    cipher: ${SS_METHOD}
    password: "${SS_PASSWORD}"
    udp: true            # was `false` in the TCP-only prototype; the server now serves UDP
  - name: My-VLESS-Reality
    type: vless
    server: ${SERVER_IP}
    port: ${VLESS_PORT}
    uuid: ${VLESS_UUID}
    network: tcp
    tls: true
    udp: true
    flow: ${VLESS_FLOW}
    packet-encoding: xudp
    servername: ${REALITY_SNI}
    client-fingerprint: chrome
    reality-opts:
      public-key: ${REALITY_PUBLIC_KEY}
      short-id: ${SHORT_ID}

proxy-groups:
  - name: PROXY
    type: select
    proxies: [My-sing-box, My-VLESS-Reality, DIRECT]

rules:
  - IP-CIDR,127.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
  - IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
  - IP-CIDR,169.254.0.0/16,DIRECT,no-resolve
  - MATCH,PROXY
```
(The file in `templates/` also contains a commented optional `tun:` block.)

Design notes from the recorded setup:
- A profile with only `proxies:` shows an empty proxy page in Clash Verge: `proxy-groups` and a `rules` entry referencing the group are required.
- Rule order: private/loopback ranges DIRECT first, `MATCH,PROXY` last. These IPv4 rules do not cover IPv6 or every LAN/overlay (e.g. EasyTier) range - add extra DIRECT rules for the user's own overlay networks if needed.
- The `dns` block is the version moved into the profile (not Global Extend Config). `'...#PROXY'` makes the DoH query use the `PROXY` group: confirm it behaves as expected in the target client. Fake-IP answers (`198.18.x.x`) prove local DNS takeover only, not absence of DNS leaks.
- VLESS `udp: true` + `packet-encoding: xudp`: these were discussed when WebRTC UDP showed a local exit address; the user reported it fixed but the exact setting was not recorded - keep both and re-test (stage 7).
- Clash Verge's TUN switch and Global Extend Config are GUI-level layers; `Runtime Config` is read-only. Stash/Shadowrocket may not accept this YAML unchanged.

## Steps

1. **[LOCAL] render**
   ```bash
   python3 scripts/render.py templates/clash.yaml.tpl ./singbox-work/clash.yaml --env-file ./singbox-work/secrets.env
   ```
2. **[LOCAL] validate**
   ```bash
   python3 scripts/validate_clash.py ./singbox-work/clash.yaml      # must print OK
   python3 -c "import yaml;yaml.safe_load(open('singbox-work/clash.yaml'));print('yaml ok')"
   ```
   If `mihomo` is installed locally also run: `mihomo -t -d singbox-work -f singbox-work/clash.yaml` (config test).
3. **[LOCAL] deliver** - tell the user the path. The file contains secrets: do not commit, upload to public places or paste into chat. Import in Clash Verge: Profiles -> New -> Local (or edit file), activate, choose `PROXY -> My-sing-box` (or `My-VLESS-Reality`), turn TUN on if system-wide proxying is wanted.

## Verification summary

- [ ] `validate_clash.py` prints `OK` (no `TODO`, no `${...}` left)
- [ ] both proxies present, group `PROXY` references them, last rule `MATCH,PROXY`
- [ ] functional proof is stage 7 (`singbox-local-verify`)
