---
name: singbox-udp
description: Enable and prove UDP on an already-deployed sing-box node - Shadowsocks UDP listener, firewall / security-group UDP, Clash udp true setting, tcpdump evidence, WebRTC leak check. Use for UDP 不通, UDP 转发, WebRTC 泄露显示本地 IP, QUIC / 游戏 / 语音走不走代理, "SS works for TCP but UDP doesn't", "does my sing-box proxy UDP". Builds on singbox-minimal-deploy (must be deployed first). Not for DNS / 分流 rules (use singbox-dns-routing), VLESS-REALITY setup, or sshd / SSH firewall changes.
---

# sing-box UDP (incremental on top of the minimal deployment)

**Prerequisite: `singbox-minimal-deploy` is deployed.** This skill does not repeat any deployment step (no server prep, Docker, compose or firewall setup); it checks that the base exists, then adds UDP-specific changes, evidence and tests. If the base is missing, stop and run `singbox-minimal-deploy` first (or `singbox-deploy-full`).

**Local agent.** Every step is marked **[LOCAL]** or **[REMOTE]** (remote = over `ssh`; the agent connects as needed). Hard rules: never change SSH configuration on the server (sshd, `authorized_keys`, SSH port, SSH firewall rules, passwords, users); never enable a default-deny firewall policy; all sing-box files on the server stay in `/opt/sing-box/` (`REMOTE_DIR`, see the base skill's "Server directory rule"); secrets stay in `./singbox-work/` and are never printed or committed; one change at a time, back up before modifying anything on the server; render configs from templates, never hand-write them.

Session setup (**[LOCAL]**; `SB_DIR` = directory containing the `singbox-*` skill folders):
```bash
SB_DIR=/path/to/skills/sing-box
set -a; . ./singbox-work/secrets.env; set +a
REMOTE_DIR=/opt/sing-box                       # fixed, same as the base skill
SSH="ssh -p ${SSH_PORT} -i ${SSH_KEY} -o StrictHostKeyChecking=accept-new ${SSH_USER}@${SERVER_IP}"
SCP="scp -P ${SSH_PORT} -i ${SSH_KEY}"
```

## 0. Base check (read-only)

1. **[REMOTE]** the base node is running and listens on UDP:
   ```bash
   $SSH "cd ${REMOTE_DIR} && docker compose ps"
   $SSH "ss -lntup | grep -E ':(${SS_PORT})\b'"
   ```
   Expect container `Up`, `tcp LISTEN 0.0.0.0:${SS_PORT}` **and** `udp UNCONN 0.0.0.0:${SS_PORT}`.
2. **[LOCAL]** no `"network"` key on the SS inbound and `udp: true` on the client node:
   ```bash
   grep -n '"network"' ./singbox-work/config.json || echo 'no network key (TCP+UDP) OK'
   grep -n 'udp:' ./singbox-work/clash.yaml
   ```
Gate: all of the above hold. If the UDP listener is missing or `"network": "tcp"` is present, apply "Fix" below; do not hand-edit the server config.

## Fix (only if a check above failed)

- Why: the first prototype was TCP-only. Removing `network` from `ss-in` lets sing-box serve TCP **and** UDP. Do not write `"tcp,udp"` (unverified/invalid).
- **[LOCAL]** re-render the server config from the base template (it has no `network` key) and the client profile (`udp: true` is in the template):
  ```bash
  python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py $SB_DIR/singbox-minimal-deploy/templates/config.ss.json.tpl ./singbox-work/config.json --env-file ./singbox-work/secrets.env
  python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py $SB_DIR/singbox-minimal-deploy/templates/clash.ss.yaml.tpl ./singbox-work/clash.yaml --env-file ./singbox-work/secrets.env
  ```
  (If VLESS-REALITY was already added by `singbox-reality-perf-troubleshoot`, render that skill's `config.ss-vless.json.tpl` / `clash.ss-vless.yaml.tpl` instead.)
- **[REMOTE]** back up, upload, check, restart - the same sequence as base step 4 of `singbox-minimal-deploy` (back up `config.json` into `${REMOTE_DIR}/backups/` first, `CONFIG_OK` gate before restart).

## 1. Firewall / security group allows UDP

- **[REMOTE, read-only]** host firewall state (same read-only command as base step 5): `$SSH 'systemctl is-active ufw 2>/dev/null; ufw status verbose 2>/dev/null; nft list ruleset 2>/dev/null | head -60; iptables -S 2>/dev/null | head -40'`. A needed rule, **only if a host firewall is active and blocking it and after telling the user the exact command**: `ufw allow ${SS_PORT}/udp`. Never touch the SSH port's rules.
- **User action:** the cloud security group must allow inbound `${SS_PORT}/udp` (cannot be automated). Wait for confirmation.

## 2. UDP reachability evidence

UDP cannot be proven by a connect test. Use the end-to-end test in step 3 (client with `udp: true`) and, if it is unclear, the server-side capture (read-only, **[REMOTE]**; ask before installing tcpdump):
```bash
$SSH 'apt-get install -y tcpdump'    # only if missing and user agrees
# in a second step, while the local client generates UDP traffic (step 3):
$SSH "timeout 20 tcpdump -ni any -c 10 -q 'udp dst port ${SS_PORT}'"
```
Expected: packets from the local machine's public IP to `${SERVER_IP}:${SS_PORT}` with `0 packets dropped by kernel`. The `any` device message about promiscuous mode is normal. Bidirectional traffic can be confirmed with `tcpdump -ni <eth-device> -c 20 -q 'udp port ${SS_PORT} and host <client-public-ip>'` (look for both directions). Packet capture shows network reachability only; it does not prove application-layer success. (Do not write capture files on the server; if one is ever needed it goes in `${REMOTE_DIR}/`.)

## 3. Application-layer UDP and WebRTC check

- **UDP (SS)**: with `udp: true`, run a non-DNS UDP application test if available (e.g. a controlled UDP echo/QUIC target). Network-layer proof: the server `tcpdump` above shows packets from the client during the test; bidirectional capture shows both directions. Capture alone is not proof that real application requests were decrypted and forwarded.
- **WebRTC UDP** (**[LOCAL]**, browser, only with TUN/system proxy): an IP other than `${SERVER_IP}` in a WebRTC test means UDP is not proxied - confirm the selected node has `udp: true` and retest in the same browser. (For the VLESS node: `udp: true` **and** `packet-encoding: xudp`, see section 4.)
- Start the local client per base step 7 (`$SB_DIR/singbox-minimal-deploy/scripts/run-local-client.sh ...`) and read server logs read-only with `$SSH "cd ${REMOTE_DIR} && docker compose logs --tail=40"`.

## 4. After VLESS-REALITY is added

`singbox-reality-perf-troubleshoot` adds the `My-VLESS-Reality` node. Its template sets `udp: true` + `packet-encoding: xudp`: these were discussed when WebRTC UDP showed a local exit address; the user reported it fixed but the exact setting was not recorded - keep both and **re-run section 3 for the VLESS node** (WebRTC UDP IP == `${SERVER_IP}`).

## Troubleshooting pointers

Symptom rows for UDP/WebRTC (`"network": "tcp"` still present, client `udp: false`, WebRTC shows a local IP) are in `singbox-reality-perf-troubleshoot/references/troubleshooting.md`.

## Known open risk (report, do not hide)

UDP application-layer end-to-end is not strictly proven in the recorded deployment; do not claim more than the evidence shows (TCP egress IP correct != UDP works; UDP packets in a capture != application-layer UDP success).

## TODO (gaps - not invented here)

- TODO: no scripted UDP application test exists yet (the existing notes only say "a controlled UDP echo/QUIC target if available"); add a concrete, verified procedure once yubai decides the test target.
- TODO: the exact setting that fixed the WebRTC local-IP exit in the recorded setup was not recorded; this skill only says to keep `udp: true` (+ `xudp` for VLESS) and re-test.
- TODO: UDP-specific tuning (timeouts, QUIC/HTTP3 handling) has no source material in the existing skills.

## Verification summary (report to the user, no secrets)

| Check | SS 2022 | VLESS-REALITY (if added) |
| --- | --- | --- |
| server UDP listener on `${SS_PORT}` (`UNCONN`) | | n/a (TCP only) |
| firewall + security group allow UDP | | n/a |
| client `udp: true` | | `udp: true` + `xudp` |
| tcpdump sees UDP from client | | |
| WebRTC UDP IP == server | | |
