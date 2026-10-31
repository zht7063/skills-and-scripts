---
name: singbox-minimal-deploy
description: Minimal sing-box node on a VPS with Docker, driven by a local agent over SSH - server prep, Docker install, Shadowsocks 2022 config, compose up, firewall ports, a basic Clash/mihomo profile and a local test. Use for 搭节点, 部署 sing-box, 最小化部署, VPS 上装代理, 一键搭梯子, Clash / Clash Verge 配置, "set up a sing-box / Shadowsocks proxy server", even if the user doesn't say Docker. This is the base that the UDP, DNS/分流 and VLESS-REALITY skills build on. Not for editing sshd / authorized_keys / SSH port, or generic Docker / nginx setup.
---

# sing-box minimal deployment (base skill)

Result: a Docker `sing-box` container on the remote server with a single **Shadowsocks 2022** inbound (`${SS_PORT}` 8388, TCP+UDP) and `direct` outbound, reachable through the firewall / security group, verified from the local machine with a local client, plus a basic Clash / mihomo profile `./singbox-work/clash.yaml` (one node `My-sing-box`).

This is the **base** of the `singbox-*` skills. `singbox-udp`, `singbox-dns-routing` and `singbox-reality-perf-troubleshoot` all assume this deployment exists and only add changes on top of it (they never repeat these steps). Chained end-to-end by `singbox-deploy-full`.

## Who runs what

You are a **local agent** on the user's machine. You are given remote server info and connect over **SSH when a step says `[REMOTE]`**. Everything marked `[LOCAL]` runs on the user's machine (generating the secret, rendering templates, running a local proxy client, curl tests). **Every step below is marked `[LOCAL]` or `[REMOTE]`.**

Session setup (**[LOCAL]**, repeat in every shell; `SB_DIR` = the directory that contains the `singbox-*` skill folders, i.e. the parent of this skill's folder):

```bash
SB_DIR=/path/to/skills/sing-box            # parent of singbox-minimal-deploy/
set -a; . ./singbox-work/secrets.env; set +a   # once it exists (step 1.6)
REMOTE_DIR=/opt/sing-box                       # fixed server directory, defined once (see "Server directory rule")
SSH="ssh -p ${SSH_PORT} -i ${SSH_KEY} -o StrictHostKeyChecking=accept-new ${SSH_USER}@${SERVER_IP}"
SCP="scp -P ${SSH_PORT} -i ${SSH_KEY}"
```

## Required inputs (ask the user up front if missing)

| Variable | Meaning |
| --- | --- |
| `${SERVER_IP}` | public IPv4 of the VPS |
| `${SSH_PORT}` | SSH port (the VPS may not use 22) |
| `${SSH_USER}` | SSH user (usually `root`; if not root, prefix remote commands with `sudo`) |
| `${SSH_KEY}` | private key path on the local machine (key auth; never store passwords in files; if the user only has a password, ask them to set up a key/ssh-agent themselves) |
| Optional overrides | `SS_PORT` 8388, `LOG_LEVEL` info (the server directory `REMOTE_DIR` is **fixed** to `/opt/sing-box`, see "Server directory rule") |
| Local tools | `ssh`, `scp`, `openssl`, `python3` (+ PyYAML for validation), `curl`, `nc`; `mihomo` or `sing-box` for step 7 - ask before installing anything |

Template for all variables (the REALITY/VLESS ones are only used by `singbox-reality-perf-troubleshoot`): `templates/inputs.env.example` -> copy to `./singbox-work/secrets.env` (mode 600, never committed).

## Server directory rule: everything lives in `/opt/sing-box/`

All sing-box related files on the server - `config.json`, the compose file (`compose.yaml`), any env file, keys, certificates, `backups/` and any file we create for logs - live in **one directory, `REMOTE_DIR=/opt/sing-box`**, next to the compose file, so nothing pollutes the rest of the system. Every `[REMOTE]` path in all `singbox-*` skills is `${REMOTE_DIR}/...`; never create sing-box files elsewhere on the server (no `/etc/sing-box`, `/root`, `/tmp` leftovers, home directories). The container sees the config only through the compose bind mount `./config.json` (inside `/opt/sing-box`). Docker's own `json-file` container logs (rotated 10m x 3 by the compose file) stay in Docker's data root and are read with `docker compose logs`; system packages (Docker, tcpdump) are installed by `apt` as usual. **Existing servers not deployed by these skills:** their files are read-only - read `config.json` from wherever the user says it lives and never move, copy or rewrite their files.

## Hard rules

1. Follow the steps strictly in order and render configs from the bundled templates. Do not improvise commands, config fields, ports, images or file layouts. If something does not fit (unsupported OS, port taken, check fails), stop and report instead of working around it.
2. **Never change SSH configuration** on the server (`/etc/ssh/*`, `sshd_config`, `authorized_keys`, SSH port, SSH firewall rules, passwords, users) and never enable a default-deny firewall policy. Never close or restart sshd.
3. Secrets only in `./singbox-work/` (chmod 700 dir, 600 files, gitignored). Never put real IPs/passwords/keys into skill files, git, chat logs or screenshots; do not print secret values in reports.
4. Each step ends with a check. Do not start the next step until every box is ticked. Report failures with the failing command and its output (redacted).
5. One change at a time; back up before modifying anything that already exists on the server; destructive or off-box actions need user confirmation.
6. If the SSH host key changed (server reinstalled), tell the user; only after they confirm run `ssh-keygen -R "[${SERVER_IP}]:${SSH_PORT}"` **locally**.

Re-runs: steps are idempotent as written (mkdir -p, config backed up before overwrite). If step 1 finds a container `sing-box` already running, ask the user whether to reuse the existing credentials or replace them (back up first, rotate, update clients). For a server **not** deployed by these skills, do **not** run this skill - use the existing-server path in `singbox-deploy-full` (read-only).

## Image version: `latest` by default, 1.14.4 as the known-stable reference

`templates/compose.yaml` uses `ghcr.io/sagernet/sing-box:latest` (default, do not change it unless this rollback is needed). The version verified in the recorded deployment is **sing-box 1.14.4** (`linux/amd64`, image tag `v1.14.4`) - the known-stable reference.

**If `latest` causes problems** (`sing-box check` fails after a pull, container restarts in a loop, nodes fail although the config and credentials did not change), tell the user and roll back to 1.14.4:

1. **[LOCAL]** make a pinned copy of the compose file (the template itself stays unchanged):
   ```bash
   sed 's#ghcr.io/sagernet/sing-box:latest#ghcr.io/sagernet/sing-box:v1.14.4#' $SB_DIR/singbox-minimal-deploy/templates/compose.yaml > ./singbox-work/compose.pinned.yaml
   grep -n 'image:' ./singbox-work/compose.pinned.yaml     # must show :v1.14.4
   ```
2. **[REMOTE]** back up the current compose file, then **[LOCAL -> REMOTE]** upload the pinned one:
   ```bash
   $SSH "cd ${REMOTE_DIR} && cp compose.yaml backups/compose.yaml.$(date +%Y%m%d-%H%M%S)"
   $SCP ./singbox-work/compose.pinned.yaml ${SSH_USER}@${SERVER_IP}:${REMOTE_DIR}/compose.yaml
   ```
3. **[REMOTE]** pull the pinned image, validate with it, restart:
   ```bash
   $SSH "cd ${REMOTE_DIR} && docker compose config -q && docker compose pull && docker compose run --rm sing-box -c /etc/sing-box/config.json check && echo CONFIG_OK"
   $SSH "cd ${REMOTE_DIR} && docker compose up -d && docker compose ps && docker compose logs --tail=20"
   $SSH "docker exec sing-box sing-box version"          # expect 1.14.4
   ```
   Gate: `CONFIG_OK` before `up -d`. If the config was changed for a newer schema, also restore `backups/config.json.*` (back up the current one first).
4. **[LOCAL]** re-run step 7 for every node. To go back to `latest` later, re-upload the unchanged `templates/compose.yaml`, `docker compose pull`, `check`, `up -d`.

The full update procedure (rollback tag, routine checks) is in `singbox-reality-perf-troubleshoot/references/maintenance.md`.

## Files in this skill

| File | Use |
| --- | --- |
| `templates/inputs.env.example` | all variables -> `./singbox-work/secrets.env` |
| `templates/secrets.env.example` | variable generated by this skill (`SS_PASSWORD`) |
| `templates/config.ss.json.tpl` | **minimal** server config: Shadowsocks 2022 only (`ss-in`, TCP+UDP, no `network` key) + `direct` outbound |
| `templates/compose.yaml` | Docker Compose file (host network, restart policy, log rotation) |
| `templates/clash.ss.yaml.tpl` | basic Clash / mihomo profile, one node `My-sing-box` |
| `templates/singbox-client.ss.json.tpl` | local **sing-box** client config for the test (`ss-out`; `${TEST_OUTBOUND}` = `route.final`) |
| `scripts/gen-secrets.sh` | generates `SS_PASSWORD` into `secrets.env` (local, no remote call) |
| `scripts/render.py` | renders `${VAR}` placeholders, refuses unset/`TODO` values (`VLESS_FLOW` may be explicitly empty), writes mode 600. Shared by all `singbox-*` skills |
| `scripts/validate_clash.py` | static validation of the rendered Clash YAML |
| `scripts/run-local-client.sh`, `scripts/egress-check.sh` | start a local client, select node, egress IP + `generate_204` check |

## Step 1 - server preparation (read-only)

This step only **reads** state; do not make extra changes.

1. **[LOCAL] connectivity**
   ```bash
   $SSH 'echo connected; whoami'
   ```
   Check: prints `connected` and the expected user. If not, stop and report; do not try other credentials.

2. **[REMOTE via ssh] environment facts**
   ```bash
   $SSH 'cat /etc/os-release; uname -m; id -u; docker --version 2>&1; docker compose version 2>&1'
   ```
   Check: recorded deployment used **Debian 13 (Trixie), x86_64**. Other Debian/Ubuntu releases usually work; if architecture is not `x86_64`/`aarch64`, or the OS is not Debian/Ubuntu, stop and ask the user. Note whether Docker and the compose plugin already exist (step 2 is skipped if both work).

3. **[REMOTE] listening ports - choose proxy ports**
   ```bash
   $SSH 'ss -lntup'
   ```
   Check: the SSH port `${SSH_PORT}` is listed (never reuse it). Default `${SS_PORT}=8388` (TCP+UDP) must NOT already be listening. If taken (e.g. by a previous sing-box container), pick another free port and record it in `secrets.env`; if an old `sing-box` container exists, ask the user whether to reuse/replace it (compare with `$SSH 'docker ps -a'`). (The VLESS port `${VLESS_PORT}` 8443 is checked later by `singbox-reality-perf-troubleshoot`.)

4. **[REMOTE] firewall state (read-only)**
   ```bash
   $SSH 'command -v ufw && ufw status verbose; command -v nft && nft list ruleset | head -50; command -v iptables && iptables -S | head -50'
   ```
   Check: note whether a host firewall is active (details handled in step 5). A port being free in `ss` does not prove it is reachable from the Internet: the **cloud provider's security group / cloud firewall** is outside the server and must be checked by the user (step 5).

5. **[REMOTE] outbound connectivity & DNS (read-only)**
   ```bash
   $SSH 'curl -4 -sS --max-time 10 https://api.ipify.org; echo; cat /etc/resolv.conf'
   ```
   Check: returned IP equals `${SERVER_IP}` (server egress = its own IP). Record `resolv.conf` nameservers (the recorded server used plain 8.8.8.8 / 1.1.1.1; this means server-side domain resolution is unencrypted plain DNS - a known and accepted risk, see `singbox-dns-routing`).

6. **[LOCAL] create work dir**
   ```bash
   mkdir -p singbox-work && chmod 700 singbox-work
   # make sure singbox-work/ is in .gitignore of whatever repo you are in
   cp $SB_DIR/singbox-minimal-deploy/templates/inputs.env.example singbox-work/secrets.env && chmod 600 singbox-work/secrets.env
   ```
   Fill `SERVER_IP`, `SSH_PORT`, `SSH_USER`, `SSH_KEY` and any changed ports.

Gate (all must pass before step 2):
- [ ] SSH works with key auth, correct user
- [ ] OS/arch supported
- [ ] `${SS_PORT}` free (or replaced by a free one, recorded)
- [ ] SSH port identified and left untouched
- [ ] `secrets.env` created locally with mode 600

## Step 2 - Docker Engine + Compose on the remote server

Do not install extra packages or change SSH/sshd settings.

**2.0 Skip check [REMOTE]**
```bash
$SSH 'docker --version && docker compose version'
```
If both print versions, mark this step done and go to step 3.

**2.1 Install (Debian/Ubuntu, official apt repository) [REMOTE]**
The recorded deployment only verified that Docker + Compose were present on Debian 13; the install commands below are the standard upstream method (docs.docker.com/engine/install/debian). Show the user the commands and confirm before running them if the server is not a fresh one. (As root; for another user prefix with `sudo`.)
```bash
$SSH 'bash -s' <<'REMOTE'
set -euo pipefail
. /etc/os-release
DIST="$ID"                       # debian or ubuntu
CODENAME="${VERSION_CODENAME}"
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL "https://download.docker.com/linux/${DIST}/gpg" -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<SRC
Types: deb
URIs: https://download.docker.com/linux/${DIST}
Suites: ${CODENAME}
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
SRC
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
REMOTE
```
If the distro codename is not yet published by Docker, stop and ask the user (do not guess a different codename).

**2.2 Verification [REMOTE]**
```bash
$SSH 'docker --version; docker compose version; systemctl is-enabled docker; systemctl is-active docker'
$SSH 'docker run --rm hello-world | head -5'
$SSH 'docker pull ghcr.io/sagernet/sing-box:latest >/dev/null && docker run --rm ghcr.io/sagernet/sing-box:latest version'
```
Gate:
- [ ] Docker and Compose versions print
- [ ] `is-enabled` = `enabled`, `is-active` = `active`
- [ ] `hello-world` runs
- [ ] the sing-box image pulls and prints a version (the recorded run used **sing-box 1.14.4**, `linux/amd64`; see "Image version" above if `latest` misbehaves). If `ghcr.io` is unreachable from the server, stop and report to the user (mirror/registry choice is their decision).

Record the printed sing-box version in `./singbox-work/NOTES.md` (no secrets).

## Step 3 - secret and minimal server `config.json`

**Render from `templates/config.ss.json.tpl`. Do not hand-write or "improve" JSON, and do not change field names, ports or the `method`.** If a field you think is needed is not in the template, stop and ask.

Inputs from `./singbox-work/secrets.env`: `SERVER_IP SSH_PORT SSH_USER SSH_KEY`, `SS_PORT` (8388), `SS_METHOD` (`2022-blake3-aes-128-gcm`), `LOG_LEVEL` (`info`).

Why no `"network": "tcp"` on the SS inbound: the first prototype was TCP-only; removing `network` lets sing-box serve TCP **and** UDP. Do not write `"tcp,udp"` (unverified/invalid).

1. **[LOCAL] generate the secret**
   ```bash
   $SB_DIR/singbox-minimal-deploy/scripts/gen-secrets.sh ./singbox-work/secrets.env
   ```
   Equivalent manual command (only if the script cannot be used): SS key: `openssl rand -base64 16` (16 bytes -> 22 base64 chars + `==`).

   Verify (LOCAL, do not print values):
   ```bash
   set -a; . ./singbox-work/secrets.env; set +a
   [ "$(printf %s "$SS_PASSWORD" | base64 -d 2>/dev/null | wc -c)" = 16 ] && echo "SS key: 16 bytes OK"
   ```

2. **[LOCAL] render the config**
   ```bash
   python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py $SB_DIR/singbox-minimal-deploy/templates/config.ss.json.tpl ./singbox-work/config.json --env-file ./singbox-work/secrets.env
   ```
   `render.py` exits non-zero if any variable is unset or still `TODO*`.

3. **[LOCAL] static verification**
   ```bash
   python3 -c "import json;d=json.load(open('singbox-work/config.json'));print([i['tag'] for i in d['inbounds']], [o['tag'] for o in d['outbounds']])"
   grep -c '\${' singbox-work/config.json   # must print 0
   grep -n '"network"' singbox-work/config.json || echo 'no network key (TCP+UDP) OK'
   ls -l singbox-work/config.json            # -rw------- expected
   ```
   Expected tags: inbounds `['ss-in']`, outbounds `['direct']`. The authoritative syntax check is `sing-box check` on the server in step 4 (same image/version as production).

Security: `secrets.env` and `config.json` contain secrets: mode 600, local `singbox-work/` only, **never** committed, pasted in chat/issues, or screenshotted (the recorded run exposed a test key in screenshots and had to rotate it). If a key was ever displayed publicly, generate a new one.

## Step 4 - upload, check, run

**Use `templates/compose.yaml` exactly as provided. Do not add `ports:` (host networking publishes ports itself), do not change the image to a pinned/other tag unless the user asks or the rollback in "Image version" applies, do not edit the config on the server by hand - re-render locally and re-upload.**

`templates/compose.yaml`:

```yaml
services:
  sing-box:
    image: ghcr.io/sagernet/sing-box:latest
    container_name: sing-box
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./config.json:/etc/sing-box/config.json:ro
    command: -c /etc/sing-box/config.json run
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```
Notes: `network_mode: host` uses the host network stack (no port mapping). `latest` only changes when the image is re-pulled - there is no auto-update.

1. **[REMOTE] working directory** (idempotent)
   ```bash
   $SSH "mkdir -p ${REMOTE_DIR}/backups && chmod 700 ${REMOTE_DIR}"
   ```
   If `${REMOTE_DIR}/config.json` already exists, back it up first (REMOTE): `cp config.json backups/config.json.$(date +%Y%m%d-%H%M%S)`.

2. **[LOCAL -> REMOTE] upload**
   ```bash
   $SCP $SB_DIR/singbox-minimal-deploy/templates/compose.yaml ${SSH_USER}@${SERVER_IP}:${REMOTE_DIR}/compose.yaml
   $SCP singbox-work/config.json ${SSH_USER}@${SERVER_IP}:${REMOTE_DIR}/config.json
   $SSH "chmod 600 ${REMOTE_DIR}/config.json"
   ```

3. **[REMOTE] pull, validate compose and config**
   ```bash
   $SSH "cd ${REMOTE_DIR} && docker compose config -q && docker compose pull"
   $SSH "cd ${REMOTE_DIR} && docker compose run --rm sing-box -c /etc/sing-box/config.json check && echo CONFIG_OK"
   ```
   **Gate:** must print `CONFIG_OK` with exit code 0. If `check` reports an error, fix the template inputs locally (step 3) - do not start the container.

4. **[REMOTE] start**
   ```bash
   $SSH "cd ${REMOTE_DIR} && docker compose up -d && docker compose ps && docker compose logs --tail=30"
   ```
   Check: container `Up`; log contains `sing-box started`.

5. **[REMOTE] listener verification**
   ```bash
   $SSH "ss -lntup | grep -E ':(${SS_PORT})\b'"
   ```
   Expected exactly: `tcp LISTEN 0.0.0.0:${SS_PORT}` and `udp UNCONN 0.0.0.0:${SS_PORT}` (Shadowsocks TCP+UDP).
   Also: `$SSH "docker inspect sing-box --format '{{json .HostConfig.LogConfig}}'"` -> `{"Type":"json-file","Config":{"max-file":"3","max-size":"10m"}}`; `$SSH "docker inspect sing-box --format '{{.HostConfig.RestartPolicy.Name}}'"` -> `unless-stopped`.

6. **[REMOTE] restart-recovery check**
   ```bash
   $SSH "cd ${REMOTE_DIR} && docker compose restart && sleep 3 && docker compose ps && docker compose logs --tail=10"
   ```
   Log should show TCP and UDP listeners on `${SS_PORT}`, then `sing-box started`. (A manual restart proves recovery from restart, not from a crash or reboot; a reboot test is optional and needs user approval.)

Local reachability (can the Internet reach the port?) is verified in steps 5 and 7 - a listener on the server does **not** prove the cloud security group allows it.

Operating notes:
- Logs: agents should use `$SSH "cd ${REMOTE_DIR} && docker compose logs --tail=50"` (never leave `logs -f` running in a non-interactive session; for humans Ctrl+C stops following without stopping the container). With `LOG_LEVEL=info` every connection is logged; switching to `warn` means: edit the template variable, re-render, upload, `check`, then restart.
- Never publish `config.json`.

## Step 5 - firewall and port reachability

Ports that must be open inbound:

| Port | Proto | Purpose |
| --- | --- | --- |
| `${SS_PORT}` | **TCP and UDP** | Shadowsocks 2022 |
| `${SSH_PORT}` | TCP | SSH - **already working, must be preserved, never modified by you** |

(`${VLESS_PORT}` TCP is added later by `singbox-reality-perf-troubleshoot`.) `ss -lntup` showing a listener does not prove the port is reachable: the cloud provider's **security group / cloud firewall** and the host firewall are separate layers.

Rules:
- You may **read** firewall state. You may add allow rules for `${SS_PORT}` **only if a host firewall is active and blocking it, and only after telling the user the exact commands**. Never add/remove/alter rules for `${SSH_PORT}`, never enable a default-deny policy, never run `ufw enable`/`ufw reset`/`iptables -F` (risk of locking out SSH). Never touch sshd config.
- The cloud security group cannot be changed from here: ask the user to open the ports in the provider console.

1. **[REMOTE] inspect host firewall**
   ```bash
   $SSH 'systemctl is-active ufw 2>/dev/null; ufw status verbose 2>/dev/null; nft list ruleset 2>/dev/null | head -60; iptables -S 2>/dev/null | head -40'
   ```
   Interpret:
   - everything inactive/empty or policy ACCEPT -> nothing to do on the host.
   - active ufw: needed rules (only if missing, after informing the user; SSH port is already allowed, do not touch):
     ```bash
     $SSH "ufw allow ${SS_PORT}/tcp && ufw allow ${SS_PORT}/udp && ufw status"
     ```
   - nftables/iptables with a default DROP: report the situation to the user and propose equivalent accept rules; do not apply without confirmation.

2. **Cloud security group - ask the user (cannot be automated)**
   Tell the user to ensure inbound allow for `${SS_PORT}/tcp`, `${SS_PORT}/udp` (source 0.0.0.0/0, or their own client IPs) and that the SSH port rule stays. Wait for confirmation.

3. **[LOCAL] TCP reachability**
   ```bash
   nc -zv -w 5 ${SERVER_IP} ${SS_PORT}
   ```
   (Fallback without nc: `python3 -c "import socket;socket.create_connection(('${SERVER_IP}',${SS_PORT}),5);print('open')"`.)
   Expected: `succeeded/open`.

4. UDP reachability cannot be proven by a connect test - it is covered by `singbox-udp`.

Gate:
- [ ] host firewall state recorded; SSH rule untouched
- [ ] user confirmed cloud security group allows `${SS_PORT}` TCP+UDP
- [ ] local `nc` to the TCP port succeeds

## Step 6 - basic Clash (mihomo) profile

**[LOCAL], no remote commands.** Render from `templates/clash.ss.yaml.tpl`; do not rewrite the YAML by hand. Inputs: `SERVER_IP SS_PORT SS_METHOD SS_PASSWORD LOCAL_MIXED_PORT LOCAL_CONTROLLER_PORT`.

Contents (one node, basic `dns:` block, private ranges DIRECT then `MATCH,PROXY`) - the exact file is `templates/clash.ss.yaml.tpl`:

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

proxy-groups:
  - name: PROXY
    type: select
    proxies: [My-sing-box, DIRECT]

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
- Rule order: private/loopback ranges DIRECT first, `MATCH,PROXY` last (extending the rules: `singbox-dns-routing`).
- Do not use the REALITY *private* key on a client (relevant once `singbox-reality-perf-troubleshoot` adds the VLESS node).
- Clash Verge's TUN switch and Global Extend Config are GUI-level layers; `Runtime Config` is read-only. Stash/Shadowrocket may not accept this YAML unchanged.

1. **[LOCAL] render**
   ```bash
   python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py $SB_DIR/singbox-minimal-deploy/templates/clash.ss.yaml.tpl ./singbox-work/clash.yaml --env-file ./singbox-work/secrets.env
   ```
2. **[LOCAL] validate**
   ```bash
   python3 $SB_DIR/singbox-minimal-deploy/scripts/validate_clash.py ./singbox-work/clash.yaml      # must print OK
   python3 -c "import yaml;yaml.safe_load(open('singbox-work/clash.yaml'));print('yaml ok')"
   ```
   If `mihomo` is installed locally also run: `mihomo -t -d singbox-work -f singbox-work/clash.yaml` (config test).
3. **[LOCAL] deliver** - tell the user the path. The file contains secrets: do not commit, upload to public places or paste into chat. Import in Clash Verge: Profiles -> New -> Local (or edit file), activate, choose `PROXY -> My-sing-box`, turn TUN on if system-wide proxying is wanted.

Gate:
- [ ] `validate_clash.py` prints `OK` (no `TODO`, no `${...}` left)
- [ ] proxy present, group `PROXY` references it, last rule `MATCH,PROXY`

## Step 7 - local end-to-end verification (basic)

**Mostly LOCAL.** The agent runs a local proxy client on the user's machine, sends test traffic through the **deployed** server, and optionally reads the server log over ssh (read-only). Needs `./singbox-work/clash.yaml` and a `mihomo` **or** `sing-box` binary on PATH (the user installs it; ask before installing anything; Clash Verge can be used manually instead). Record pass/fail per node. Do not declare success from one test: TCP egress IP correct does not prove DNS has no leaks, UDP works, or IPv6/WebRTC are right (those are `singbox-udp` and `singbox-dns-routing`).

Set `ENV_FILE=./singbox-work/secrets.env` (default).

**A. Local client = mihomo (primary)**
1. **[LOCAL]** static check: `mihomo -t -d singbox-work -f singbox-work/clash.yaml` (if available).
2. **[LOCAL]** per node:
   ```bash
   $SB_DIR/singbox-minimal-deploy/scripts/run-local-client.sh mihomo ./singbox-work/clash.yaml My-sing-box
   ```
   The script starts mihomo (mixed port `${LOCAL_MIXED_PORT}`), selects the node through the controller (`PUT /proxies/PROXY`), and runs `egress-check.sh`. Pass criteria **per node**: proxied egress == `${SERVER_IP}`; `generate_204` = HTTP 204. If port 7890/9090 are busy locally, change `LOCAL_MIXED_PORT` / `LOCAL_CONTROLLER_PORT` in `secrets.env` and re-render the clash file.

**B. Local client = sing-box (alternative / cross-check)**
```bash
TEST_OUTBOUND=ss-out python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py $SB_DIR/singbox-minimal-deploy/templates/singbox-client.ss.json.tpl ./singbox-work/client-ss-out.json --env-file ./singbox-work/secrets.env
sing-box check -c ./singbox-work/client-ss-out.json
$SB_DIR/singbox-minimal-deploy/scripts/run-local-client.sh sing-box ./singbox-work/client-ss-out.json
```
Same pass criteria. (`render.py` ignores shell-only variables; `TEST_OUTBOUND` is read from the environment.)

**C. Manual curl through a running client (any client)**
```bash
curl -4 -x http://127.0.0.1:${LOCAL_MIXED_PORT} https://api.ipify.org          # expect ${SERVER_IP}
curl -4 -x http://127.0.0.1:${LOCAL_MIXED_PORT} -o /dev/null -w '%{http_code}\n' https://www.google.com/generate_204   # expect 204
```
With Clash Verge TUN on (no `-x`): `curl -4 https://api.ipify.org` should also return `${SERVER_IP}`. Do not use `api.ipinfo.io/lookup/...` (needs a token; 403 is an auth error, not a proxy failure); use `api.ipify.org` or `ipinfo.io/ip`. Comparing `DIRECT` vs the node rules out a coincidence where the local network already exits via the same IP.

**D. Server-side corroboration (read-only, [REMOTE])** while the node is under test:
```bash
$SSH "cd ${REMOTE_DIR} && docker compose logs --tail=40"
```
Expected log evidence for SS: an `inbound/shadowsocks[ss-in]` connection followed by `outbound/direct` for the test domains (e.g. `api.ipify.org`). A node whose requests never appear in the server log was not actually used.

Verification summary (report to the user as a table, no secrets):

| Check | SS 2022 |
| --- | --- |
| egress IP == server | |
| generate_204 == 204 | |
| appears in server log | |

## Done - handoff

Minimal deployment is complete when every gate above is ticked. Next, in order: `singbox-udp` (UDP proof), `singbox-dns-routing` (DNS and 分流), `singbox-reality-perf-troubleshoot` (adds VLESS-REALITY, performance, troubleshooting). Those skills check that this deployment exists (container `sing-box` Up, `${REMOTE_DIR}/config.json` + `compose.yaml` present, `./singbox-work/secrets.env` + `clash.yaml` present) before changing anything. If a gate here fails, see the troubleshooting reference in `singbox-reality-perf-troubleshoot/references/troubleshooting.md`.
