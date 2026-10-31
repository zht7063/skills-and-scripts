---
name: singbox-reality-perf-troubleshoot
description: Add VLESS-REALITY to a deployed sing-box node, then measure performance and troubleshoot common problems - REALITY keys / UUID / short id, SNI camouflage (microsoft, then intel, then nvidia), flow (xtls-rprx-vision) mismatch, handshake timeouts, 20-request latency baseline, node 连不上 / 没网 / 超时 排查, update and rollback (latest, rolling back to 1.14.4), backup, key rotation. Use for VLESS Reality 节点, 搭 Reality, Reality 连不上, 测速 / 延迟对比, sing-box 故障排查, "VLESS node fails but SS works", and for existing servers where the client profile must copy the server's flow (read-only). Builds on singbox-minimal-deploy. Not for sshd / SSH port changes, other proxy protocols, or generic Docker / nginx.
---

# sing-box VLESS-REALITY + performance + troubleshooting (incremental on top of the minimal deployment)

**Prerequisite: `singbox-minimal-deploy` is deployed** (and `singbox-udp` / `singbox-dns-routing` done or consciously skipped). This skill never repeats server prep, Docker, compose or SS setup. It checks the base exists, then **adds** the VLESS-REALITY inbound/node on top of it, and provides the performance baseline, the common-problem troubleshooting reference and maintenance (backup, update/rollback, key rotation). If the base is missing, stop and run `singbox-minimal-deploy` (or `singbox-deploy-full`) first.

**Local agent.** Every step is marked **[LOCAL]** or **[REMOTE]** (remote = over `ssh`; the agent connects as needed). Hard rules:
1. Render configs from the bundled templates; do not hand-write or "improve" JSON/YAML, do not change field names or ports. If something does not fit, stop and report.
2. **Never change SSH configuration** on the server (sshd_config, `authorized_keys`, SSH port, SSH firewall rules, passwords, users) and never enable a default-deny firewall policy.
3. All sing-box files on the server stay in `/opt/sing-box/` (`REMOTE_DIR`, see the base skill's "Server directory rule").
4. Secrets only in `./singbox-work/` (chmod 700 dir, 600 files, gitignored); never print them. Only the REALITY **public** key and short id go into client configs; never use the private key on a client.
5. **Client follows server for `flow`.** Never change a server's `flow` to match a client; on an existing server copy its actual flow (empty if absent) into the client first.
6. One change at a time; back up before modifying anything on the server; do not claim unconfirmed root causes.

Session setup (**[LOCAL]**, repeat in every shell; `SB_DIR` = directory containing the `singbox-*` skill folders, `R` = this skill):
```bash
SB_DIR=/path/to/skills/sing-box
R=$SB_DIR/singbox-reality-perf-troubleshoot
set -a; . ./singbox-work/secrets.env; set +a
REMOTE_DIR=/opt/sing-box
SSH="ssh -p ${SSH_PORT} -i ${SSH_KEY} -o StrictHostKeyChecking=accept-new ${SSH_USER}@${SERVER_IP}"
SCP="scp -P ${SSH_PORT} -i ${SSH_KEY}"
```

## Files in this skill

| File | Use |
| --- | --- |
| `templates/config.ss-vless.json.tpl` | server config: SS 2022 (`ss-in`, 8388 TCP+UDP) + VLESS-REALITY (`vless-reality-in`, 8443 TCP) + `direct` outbound - replaces the minimal `config.ss.json.tpl` |
| `templates/clash.ss-vless.yaml.tpl` | Clash / mihomo profile with both nodes (`My-sing-box`, `My-VLESS-Reality`) - replaces `clash.ss.yaml.tpl` |
| `templates/singbox-client.ss-vless.json.tpl` | local **sing-box** client config for the test (`ss-out` + `vless-out`; `${TEST_OUTBOUND}` = `route.final`) |
| `templates/secrets.env.example` | variables generated here |
| `scripts/gen-reality-secrets.sh` | generates `VLESS_UUID`, REALITY keypair, `SHORT_ID` into `secrets.env` (keeps `SS_PASSWORD`) |
| `scripts/inspect-server-config.py` | **read-only** helper for an existing server: extracts flow/UUID/short id/SNI/ports/SS values from its `config.json` |
| `scripts/perf-baseline.sh` | 20 sequential requests -> success rate, mean/median/p95/min/max |
| `references/troubleshooting.md` | symptom -> cause -> action -> verify table (all common problems) |
| `references/maintenance.md` | backup, log rotation, update + rollback tag, credential rotation, routine checks |
| (base skill) `scripts/render.py`, `validate_clash.py`, `run-local-client.sh`, `egress-check.sh` | shared helpers in `singbox-minimal-deploy/scripts/` |

## 0. Base check (read-only)

1. **[REMOTE]** base node running with the minimal config:
   ```bash
   $SSH "cd ${REMOTE_DIR} && docker compose ps && ls -l config.json compose.yaml"
   $SSH "ss -lntup | grep -E ':(${SS_PORT})\b'"
   ```
   Expect container `Up`, `config.json` + `compose.yaml` in `/opt/sing-box`, SS TCP+UDP listening.
2. **[LOCAL]** `./singbox-work/secrets.env` and `./singbox-work/clash.yaml` exist.

If the server is **not** one deployed by these skills, do not run Part A: use "Existing server path" below.

## Required values

From `secrets.env`: `SERVER_IP SSH_PORT SSH_USER SSH_KEY`, `VLESS_PORT` (8443), **`VLESS_FLOW`** (`xtls-rprx-vision`), **`REALITY_SNI`** (default `www.microsoft.com`), plus the generated `VLESS_UUID REALITY_PRIVATE_KEY REALITY_PUBLIC_KEY SHORT_ID`.

### VLESS flow: one variable for server and client

`flow` in the server `config.json` and in every client config (Clash, local sing-box client) is rendered from the **same `VLESS_FLOW`** variable (default `xtls-rprx-vision`), so they always match on a fresh deploy. Do not edit `flow` by hand in any rendered file; change `VLESS_FLOW` and re-render all.

### REALITY_SNI: default `www.microsoft.com`, with an ordered fallback

The user decided: **`REALITY_SNI=www.microsoft.com` by default**. It is a real TLS 1.3 / h2 public site that the server impersonates. One value is used in three places and they must always be identical:

| Where | Field |
| --- | --- |
| server `config.json` | `tls.server_name` |
| server `config.json` | `tls.reality.handshake.server` (with `handshake.server_port` = **443**) |
| client (Clash / sing-box client) | `servername` / `tls.server_name` |

**Fallback order, only if real testing fails** (see Part B): `www.microsoft.com` -> `www.intel.com` -> `www.nvidia.com`. Do not pick any other site and do not switch "just in case"; keep microsoft while it works. If all three fail, stop and report; never try other sites.

## Part A - add VLESS-REALITY on top of the minimal deployment

### A1. Pre-checks (read-only)

**[REMOTE]** the VLESS port must be free (default `${VLESS_PORT}` 8443 TCP; if taken, e.g. by nginx on 8443, pick another free port and record it in `secrets.env`):
```bash
$SSH 'ss -lntup'
```
**[REMOTE]** reachability of the camouflage site from the server before the first deployment:
```bash
$SSH 'curl -sS -o /dev/null -w "%{http_code} verify=%{ssl_verify_result}\n" --max-time 10 https://www.microsoft.com'
```
Must return an HTTP status (200/301/302) quickly. If it fails or times out, record it and try the next fallback in order (same check, with that site) *before* deploying.

### A2. Generate the REALITY secrets

1. **[LOCAL]** (the only remote call is `docker run --rm` of the official sing-box image, so the UUID/keypair come from the same version that will serve them; nothing persistent changes on the server)
   ```bash
   $R/scripts/gen-reality-secrets.sh ./singbox-work/secrets.env
   ```
   Equivalent manual commands (only if the script cannot be used):
   - short id: `openssl rand -hex 8` (16 hex chars)
   - UUID: `[REMOTE] docker run --rm ghcr.io/sagernet/sing-box:latest generate uuid`
   - REALITY keypair: `[REMOTE] docker run --rm ghcr.io/sagernet/sing-box:latest generate reality-keypair` -> `PrivateKey` goes to the server config, **`PublicKey` goes to clients only**.

   Verify (LOCAL, do not print values):
   ```bash
   set -a; . ./singbox-work/secrets.env; set +a
   [[ "$SHORT_ID" =~ ^[0-9a-f]{16}$ ]] && echo "short id OK"
   [[ "$VLESS_UUID" =~ ^[0-9a-f-]{36}$ ]] && echo "uuid OK"
   [ -n "$REALITY_PRIVATE_KEY" ] && [ -n "$REALITY_PUBLIC_KEY" ] && [ "$REALITY_PRIVATE_KEY" != "$REALITY_PUBLIC_KEY" ] && echo "keypair OK"
   ```
Security: `secrets.env` and `config.json` contain secrets (mode 600, local only, never committed/pasted/screenshotted - the recorded run exposed a test key in screenshots and had to rotate it). If a key was ever displayed publicly, rotate (`references/maintenance.md`, section 4).

### A3. Render the full server config (SS + VLESS-REALITY)

1. **[LOCAL] render**
   ```bash
   python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py $R/templates/config.ss-vless.json.tpl ./singbox-work/config.json --env-file ./singbox-work/secrets.env
   ```
   `render.py` exits non-zero if any variable is unset or still `TODO*`.
2. **[LOCAL] static verification**
   ```bash
   python3 -c "import json;d=json.load(open('singbox-work/config.json'));print([i['tag'] for i in d['inbounds']], [o['tag'] for o in d['outbounds']])"
   grep -c '\${' singbox-work/config.json   # must print 0
   grep -n '"network"' singbox-work/config.json || echo 'no network key (TCP+UDP) OK'
   ls -l singbox-work/config.json            # -rw------- expected
   ```
   Expected tags: inbounds `['ss-in', 'vless-reality-in']`, outbounds `['direct']`. The authoritative check is `sing-box check` on the server (A4).

### A4. Upload, check, restart (same sequence as base step 4)

**[REMOTE]** back up, **[LOCAL -> REMOTE]** upload, **[REMOTE]** check, restart:
```bash
$SSH "cd ${REMOTE_DIR} && cp config.json backups/config.json.$(date +%Y%m%d-%H%M%S)"
$SCP singbox-work/config.json ${SSH_USER}@${SERVER_IP}:${REMOTE_DIR}/config.json
$SSH "chmod 600 ${REMOTE_DIR}/config.json && cd ${REMOTE_DIR} && docker compose run --rm sing-box -c /etc/sing-box/config.json check && echo CONFIG_OK"
$SSH "cd ${REMOTE_DIR} && docker compose restart && sleep 3 && docker compose ps && tail -n 20 logs/sing-box.log"
$SSH "ss -lntup | grep -E ':(${SS_PORT}|${VLESS_PORT})\b'"
```
Gate: `CONFIG_OK` before restart (if `check` fails, fix the inputs locally and re-render - do not edit on the server; the previous config is in `backups/`); log shows the TCP `${VLESS_PORT}` listener and `sing-box started`. Expected listeners: `tcp LISTEN 0.0.0.0:${SS_PORT}`, `udp UNCONN 0.0.0.0:${SS_PORT}`, `tcp LISTEN 0.0.0.0:${VLESS_PORT}`.

### A5. Firewall for the VLESS port

Same rules as the base skill (read-only inspection; never touch the SSH port or default policies). Needed: inbound `${VLESS_PORT}/tcp`.
- **[REMOTE]** if a host firewall (ufw) is active and blocking it, after informing the user: `$SSH "ufw allow ${VLESS_PORT}/tcp && ufw status"`.
- **User action:** the cloud security group must allow `${VLESS_PORT}/tcp`.
- **[LOCAL]** `nc -zv -w 5 ${SERVER_IP} ${VLESS_PORT}` must succeed (fallback: `python3 -c "import socket;socket.create_connection(('${SERVER_IP}',${VLESS_PORT}),5);print('open')"`).

### A6. Render and validate the two-node Clash profile

1. **[LOCAL]**
   ```bash
   python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py $R/templates/clash.ss-vless.yaml.tpl ./singbox-work/clash.yaml --env-file ./singbox-work/secrets.env
   python3 $SB_DIR/singbox-minimal-deploy/scripts/validate_clash.py ./singbox-work/clash.yaml      # must print OK
   grep -n 'flow' ./singbox-work/clash.yaml ./singbox-work/config.json    # same value in both
   ```
   If `mihomo` is installed: `mihomo -t -d singbox-work -f singbox-work/clash.yaml`.
   The VLESS node uses `udp: true` + `packet-encoding: xudp` (see `singbox-udp` section 4). Tell the user the path only (file contains secrets; do not paste it). If you customised the profile in `singbox-dns-routing` (local `clash.custom.yaml.tpl`), re-apply those extra rules to the two-node template copy instead.
2. Gate: [ ] `flow` equal on server and client; [ ] `validate_clash.py` OK; [ ] both proxies present, group `PROXY` references them, last rule `MATCH,PROXY`.

### A7. Verify the VLESS node (and re-verify SS)

Use the base skill's scripts; test each node separately and record pass/fail per node.

1. **[LOCAL]** mihomo (primary):
   ```bash
   $SB_DIR/singbox-minimal-deploy/scripts/run-local-client.sh mihomo ./singbox-work/clash.yaml My-sing-box
   $SB_DIR/singbox-minimal-deploy/scripts/run-local-client.sh mihomo ./singbox-work/clash.yaml My-VLESS-Reality
   ```
   Pass criteria **per node**: proxied egress == `${SERVER_IP}`; `generate_204` = HTTP 204.
2. **[LOCAL]** sing-box client (alternative / cross-check):
   ```bash
   for NODE in ss-out vless-out; do
     TEST_OUTBOUND=$NODE python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py $R/templates/singbox-client.ss-vless.json.tpl ./singbox-work/client-$NODE.json --env-file ./singbox-work/secrets.env
     sing-box check -c ./singbox-work/client-$NODE.json
     $SB_DIR/singbox-minimal-deploy/scripts/run-local-client.sh sing-box ./singbox-work/client-$NODE.json
   done
   ```
3. **[REMOTE, read-only]** server-side corroboration while a node is under test: `$SSH "cd ${REMOTE_DIR} && tail -n 40 logs/sing-box.log"`. Expected for VLESS: `inbound/vless[vless-reality-in]`, `[client-1]` and `outbound/direct` for the test domains (e.g. `api.ipify.org`). A node whose requests never appear in the server log was not actually used.
4. UDP / WebRTC for the VLESS node: `singbox-udp` section 3 (re-run).

Report as a table (no secrets):

| Check | SS 2022 | VLESS-REALITY |
| --- | --- | --- |
| egress IP == server | | |
| generate_204 == 204 | | |
| appears in server log | | |
| UDP evidence | | |
| IPv6 (info) | | |

## Existing server path (server NOT deployed by these skills) - read-only

Use this instead of Part A when the user already has a working sing-box server and only wants client profiles / verification. **Do not change the server in any way and do not move its files.**

1. Read-only parts of the base step 1 only: SSH works, find where `config.json` lives (ask the user; for servers deployed by these skills it is `/opt/sing-box`). Call that directory `EXISTING_CONFIG_DIR` (only used for reading).
2. **[REMOTE, read-only] Before generating any client config**, check the server's actual flow and other client-relevant values (nothing is written on the server):
   ```bash
   ssh -p ${SSH_PORT} -i ${SSH_KEY} ${SSH_USER}@${SERVER_IP} "cat ${EXISTING_CONFIG_DIR}/config.json" \
     | python3 $R/scripts/inspect-server-config.py --env-out ./singbox-work/server-derived.env
   ```
   It prints a redacted summary, e.g. `VLESS_FLOW = 'xtls-rprx-vision'` or `VLESS_FLOW = ''   (field absent/empty -> client flow must be EMPTY)`. Several VLESS inbounds/users -> it stops; re-run with `--vless-tag` / `--user`.
3. **[LOCAL]** merge into `secrets.env` (derived values replace the defaults; `VLESS_FLOW=` with an empty value is valid and is accepted by `render.py`):
   ```bash
   grep -v -E '^(VLESS_FLOW|VLESS_UUID|VLESS_PORT|REALITY_SNI|SHORT_ID|SS_PORT|SS_METHOD|SS_PASSWORD)=' ./singbox-work/secrets.env > ./singbox-work/.tmp \
     && cat ./singbox-work/.tmp ./singbox-work/server-derived.env > ./singbox-work/secrets.env && rm ./singbox-work/.tmp && chmod 600 ./singbox-work/secrets.env
   ```
   Copy `VLESS_FLOW` from the server into `secrets.env` - **empty if the server user has no `flow` field**. Also take UUID, short id, ports, SS method/password and `REALITY_SNI` (= server `tls.server_name`) from the same output; `REALITY_PUBLIC_KEY` is not in a server config (only the private key is) - take it from the user.
4. **[LOCAL]** render the client profile (A6 step 1) and **verify** `grep -n 'flow' ./singbox-work/clash.yaml` shows exactly the value printed in step 2 (`flow: ""` for empty). Then A7.
5. **Never modify the server's `flow` (or any server setting) to match the client.** If a mismatch appears later, the client is changed, not the server (`VLESS_FLOW` in `secrets.env`, re-render, re-test). The SNI fallback procedure does not apply to an existing server unless the user explicitly asks to change the server. Report the flow value that was copied and its source.

Typical flow-mismatch symptom: TCP connects, server log shows an error about flow/`XTLS`/`unexpected` or the connection is closed right after the REALITY handshake, while SS works.

## Part B - when to switch the REALITY SNI, and how

Switch only if SS passes but the **VLESS-REALITY** node fails in a way that points to the handshake, i.e. **after** you have excluded the other causes (port `${VLESS_PORT}` reachable via `nc`, `uuid`/public key/short id/`flow` identical on both sides, server `check` OK):
- local client log shows REALITY/TLS handshake errors, `EOF`, `reality verification failed`, or connection timeouts to `${SERVER_IP}:${VLESS_PORT}` while `nc -zv` succeeds;
- server log shows no `inbound/vless[vless-reality-in]` entry for the test, or shows handshake/`REALITY: processed invalid connection` style errors;
- the server cannot reach the SNI site: `[REMOTE] curl -sS -o /dev/null -m 10 -w '%{http_code}\n' https://${REALITY_SNI}` fails/times out.

Do not switch for SS problems or for a single slow request.

### SNI fallback procedure (switching an already deployed node)

Switching the SNI changes **server and clients together**; doing only one side breaks the VLESS node (SS is unaffected). Try one fallback at a time: `www.microsoft.com` (default) -> `www.intel.com` -> `www.nvidia.com`.

1. **[LOCAL]** set the next value in `./singbox-work/secrets.env`: `REALITY_SNI=www.intel.com` (second failure: `www.nvidia.com`). If all three fail, stop and report to the user with the logs; do not try other sites.
2. **[LOCAL]** re-render the server config and the client config(s) from the templates:
   ```bash
   python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py $R/templates/config.ss-vless.json.tpl ./singbox-work/config.json --env-file ./singbox-work/secrets.env
   python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py $R/templates/clash.ss-vless.yaml.tpl ./singbox-work/clash.yaml --env-file ./singbox-work/secrets.env
   python3 $SB_DIR/singbox-minimal-deploy/scripts/validate_clash.py ./singbox-work/clash.yaml
   ```
   Credentials (UUID, keypair, short id) are **unchanged** - do not regenerate them.
3. **[REMOTE]** back up, upload, check, restart (same as A4):
   ```bash
   $SSH "cd ${REMOTE_DIR} && cp config.json backups/config.json.$(date +%Y%m%d-%H%M%S)"
   $SCP ./singbox-work/config.json ${SSH_USER}@${SERVER_IP}:${REMOTE_DIR}/config.json
   $SSH "chmod 600 ${REMOTE_DIR}/config.json && cd ${REMOTE_DIR} && docker compose run --rm sing-box -c /etc/sing-box/config.json check && echo CONFIG_OK"
   $SSH "cd ${REMOTE_DIR} && docker compose restart && sleep 3 && docker compose ps && tail -n 20 logs/sing-box.log"
   ```
   Gate: `CONFIG_OK` before restart; log shows the TCP `${VLESS_PORT}` listener and `sing-box started`.
4. **[LOCAL]** re-import/refresh `clash.yaml` in the client and re-run A7 for **both** nodes. Record which SNI finally works in `singbox-work/NOTES.md` (no secrets).

## Part C - performance baseline (optional, run when comparing protocols)

```bash
$SB_DIR/singbox-minimal-deploy/scripts/run-local-client.sh ... # select node, keep it running, or use your GUI client
$R/scripts/perf-baseline.sh http://127.0.0.1:${LOCAL_MIXED_PORT} 20
```
**[LOCAL].** 20 sequential requests, 1 s apart -> success rate, mean/median/p95/min/max. Recorded reference (one mobile-hotspot run, not conclusive): SS 2022 ~401 ms mean / 100 % success; VLESS+REALITY ~545 ms mean / 100 % success. For a fair comparison alternate A->B->B->A, same network, same target; do not generalise from a single run.

### Throughput (optional)

```bash
$R/scripts/throughput-test.sh -x http://127.0.0.1:${LOCAL_MIXED_PORT} -n 3 -b 10000000
```
**[LOCAL].** Downloads the same file `-n` times through the local proxy and directly (`curl -x` vs `curl --noproxy '*'`) and prints MB/s per run, averages and the proxy/direct ratio. Endpoints, tried in order until one answers through the proxy: `speed.cloudflare.com/__down?bytes=N`, `proof.ovh.net/files/10Mb.dat`, `speedtest.tele2.net/10MB.zip`. `--iperf HOST[:PORT]` is **optional** (needs `iperf3` locally and an iperf3 server you control; direct TCP only, skipped if iperf3 is missing). Single samples are noisy: use `-n 5`, alternate SS/VLESS node selection between runs, ignore differences under ~20 %. PASS only means the proxy path delivered data. Do not set `*_proxy` variables for this script.

## Part D - troubleshooting and maintenance

- **Diagnose with `references/troubleshooting.md`** (symptom -> cause -> action -> verify; covers firewall/port, `check` failures, UDP/WebRTC, VLESS failures, flow mismatch, SNI, Clash empty list, IP-info API 403, DNS/Fake-IP, IPv6, LAN/overlay, iOS clients, reboot, log growth). Change one variable at a time, keep originals, never touch SSH settings.
- **Maintenance with `references/maintenance.md`**: on-server backup into `/opt/sing-box/backups`, log rotation check, update with rollback tag, rollback to the known-stable 1.14.4, credential rotation, routine checks. The `latest` image is the default; **1.14.4 is the known-stable reference** (rollback commands: base skill section "Image version").
- Reminder: any key that was ever shown in a screenshot/chat must be rotated.

## TODO (gaps)

- TODO: long-running availability monitoring is not defined (the latency baseline and the throughput test above are one-shot).

## Verification summary

- [ ] base node verified before adding anything (section 0)
- [ ] `CONFIG_OK` before restart; listeners `${SS_PORT}` TCP+UDP and `${VLESS_PORT}` TCP
- [ ] user confirmed security group allows `${VLESS_PORT}/tcp`; `nc` succeeds
- [ ] `flow` identical on server and client; SNI identical in all three places
- [ ] both nodes: egress IP == server, 204 OK, seen in server log
