---
name: singbox-deploy-full
description: End-to-end sing-box deployment on a VPS from a local agent over SSH - chains the four skills in order (minimal deployment, then UDP, then DNS/分流, then VLESS-REALITY + performance + troubleshooting) and ends with a verified Clash / mihomo profile. Use for 完整部署 sing-box, 从零搭节点, 一条龙搭梯子, VPS 装 sing-box + Reality + Clash 配置, "deploy everything", "set up a full sing-box node with Clash config". Also the entry for existing servers that only need a client profile (read-only). Not for sshd / authorized_keys / SSH port changes, other proxy protocols, or generic Docker / nginx setup.
---

# sing-box full deployment (orchestrator)

Result: a Docker `sing-box` container on the remote server with **Shadowsocks 2022** (`${SS_PORT}` 8388 TCP+UDP) and **VLESS + REALITY** (`${VLESS_PORT}` 8443 TCP), UDP proven, DNS/routing reviewed, verified end-to-end from the local machine, and a Clash / mihomo profile `./singbox-work/clash.yaml`.

Architecture: local Clash Verge / mihomo -> (SS 2022 | VLESS-REALITY) -> VPS Docker sing-box -> `direct` outbound -> Internet. No domain, TLS certificate, panel or subscription service is used.

This skill only **chains** four skills; all procedures live in them. `singbox-minimal-deploy` is the base; each later skill checks the base exists and adds its changes on top (no repeated deployment steps).

## The five skills (all under `skills/sing-box/`)

| # | Skill | What it does | Where | Gate to proceed |
| --- | --- | --- | --- | --- |
| 1 | `singbox-minimal-deploy` | server prep, Docker, SS 2022 config, compose up, firewall, basic Clash profile, local verify | LOCAL + REMOTE | SS node: egress IP == server, 204 OK, seen in server log; `clash.yaml` validated |
| 2 | `singbox-udp` | UDP listener/firewall/client `udp: true`, tcpdump + WebRTC checks | LOCAL + REMOTE (read-only) | UDP evidence recorded (with its stated limits) |
| 3 | `singbox-dns-routing` | DNS / Fake-IP checks, DIRECT rules for LAN/overlay, IPv6, Clash DNS conflicts | LOCAL (+ remote read) | profile re-validated, DNS result recorded as "accepted risk", not "zero leak" |
| 4 | `singbox-reality-perf-troubleshoot` | adds VLESS-REALITY (secrets, SNI, flow), performance baseline, troubleshooting + maintenance references | LOCAL + REMOTE | both nodes: egress IP == server, 204 OK, seen in server log |
| 5 | `singbox-deploy-full` (this) | runs 1-4 in order, global rules, final report | - | final report delivered |

**Run 1 -> 2 -> 3 -> 4 in order; do not start the next skill until the previous gate holds.** If any gate fails, use `singbox-reality-perf-troubleshoot/references/troubleshooting.md`. Re-runs: the skills are idempotent as written (mkdir -p, config backed up before overwrite). If the server already runs the node (skill 1, step 1 finds container `sing-box`), ask the user whether to reuse the existing credentials (copy them into `secrets.env`) or replace them (back up first, rotate, update clients).

## Who runs what

You are a **local agent** on the user's machine. You are given remote server info and connect over **SSH when a step says `[REMOTE]`**. Everything marked `[LOCAL]` runs on the user's machine (generating secrets, rendering templates, running a local proxy client, curl tests). Every step in every skill is marked accordingly.

## Required inputs - collect ALL before starting

| Input | Variable | Notes |
| --- | --- | --- |
| Server public IPv4 | `SERVER_IP` | |
| SSH port | `SSH_PORT` | often not 22 |
| SSH user | `SSH_USER` | usually root |
| SSH private key path (local) | `SSH_KEY` | key auth; if the user only has a password, ask them to set up a key/ssh-agent themselves - do not store passwords |
| REALITY camouflage site | `REALITY_SNI` | **default `www.microsoft.com`** (user's decision); fallbacks in order only if real testing fails: `www.intel.com`, then `www.nvidia.com` |
| Optional overrides | `SS_PORT` 8388, `VLESS_PORT` 8443, `LOG_LEVEL` info, `VLESS_FLOW` xtls-rprx-vision (same variable renders server and client) | defaults come from the recorded deployment |
| Server directory | `REMOTE_DIR` = `/opt/sing-box` | **fixed**, not an input (see below) |
| Local tools | `ssh`, `scp`, `openssl`, `python3` (+ PyYAML for validation), `curl`, `nc`; `mihomo` or `sing-box` for local verification | ask before installing anything |

Template for all variables: `singbox-minimal-deploy/templates/inputs.env.example` -> copy to `./singbox-work/secrets.env` (mode 600, never committed). Generated secrets use variables `SS_PASSWORD VLESS_UUID REALITY_PRIVATE_KEY REALITY_PUBLIC_KEY SHORT_ID`.

## Global rules (apply to every skill)

1. **Follow the skills strictly in order and render configs from the bundled templates. Do not improvise** commands, config fields, ports, images or file layouts. If something does not fit (unsupported OS, port taken, check fails), stop and report instead of working around it.
2. **Never change SSH configuration** on the server (sshd_config, authorized_keys, SSH port, SSH firewall rules, passwords, users) and never enable a default-deny firewall policy.
3. **Server directory rule: all sing-box related files on the server (config.json, compose file, env, keys, certs, backups, logs) live in `/opt/sing-box/`** together with the compose file; nothing is created elsewhere (sing-box writes `logs/sing-box.log` there; a `log-rotate` compose service caps it - base skill "Logs and rotation"; only Docker's own capped stdout/stderr capture lives outside). Every `[REMOTE]` path is `${REMOTE_DIR}/...` with `REMOTE_DIR=/opt/sing-box` defined once per session. Existing servers not deployed by these skills: read-only, their files are never moved.
4. Secrets only in `./singbox-work/` (chmod 700 dir, 600 files, gitignored). Never put real IPs/passwords/keys into skill files, git, chat logs or screenshots. Do not print secret values in your reports.
5. Each skill ends with a verification checklist. **Do not start the next skill until every box is ticked.** Report failures with the failing command and its output (redacted).
6. **Client follows server for `flow`.** Never change a server's `flow` to match a client; on an existing server copy its actual flow (empty if absent) into the client first.
7. One change at a time; back up before modifying anything that already exists on the server; destructive or off-box actions need user confirmation.
8. Image: `ghcr.io/sagernet/sing-box:latest` is the default; **1.14.4 is the known-stable reference**. If `latest` has problems, roll back to 1.14.4 (commands in `singbox-minimal-deploy`, section "Image version").

## REALITY SNI default and fallback

- Default: `REALITY_SNI=www.microsoft.com` for server `tls.server_name`, server `reality.handshake.server` (`handshake.server_port` 443) and the client `servername` - all three always identical.
- Keep it unless **real testing fails** (VLESS handshake failure/timeouts after port, UUID, keys, short id and flow were ruled out - see `singbox-reality-perf-troubleshoot` Part B). Then switch in this order: `www.intel.com`, then `www.nvidia.com`. If all three fail, stop and report; never try other sites.
- Switching changes **both** the server `config.json` and the Clash `servername` together: set the new `REALITY_SNI` in `secrets.env` -> re-render server config and `clash.yaml` (credentials unchanged) -> back up + upload -> `sing-box check` (must pass) -> `docker compose restart` -> re-verify both nodes. Full commands: `singbox-reality-perf-troubleshoot`, "SNI fallback procedure".

## Existing server path (server NOT deployed by these skills)

Use this instead of skills 1-3 and Part A of skill 4 when the user already has a working sing-box server and only wants client profiles / verification. **Do not change the server in any way and do not move its files.** The full procedure is in `singbox-reality-perf-troubleshoot`, section "Existing server path"; in short:

1. Read-only part of `singbox-minimal-deploy` step 1: SSH works; find where `config.json` lives (ask the user).
2. **[REMOTE, read-only]** before generating any client config, run `scripts/inspect-server-config.py` on the server's `config.json` and copy `VLESS_FLOW` from the server into `secrets.env` - **empty if the user has no `flow` field**. Also copy UUID, short id, ports, SS method/password and `REALITY_SNI` (= server `tls.server_name`); the REALITY *public* key comes from the user.
3. **Never modify the server's `flow` (or any server setting) to match the client**; a mismatch is fixed on the client. The SNI fallback does not apply unless the user explicitly asks to change the server.
4. Render the two-node Clash profile and verify (skill 4, A6/A7). Report the flow value that was copied and its source.

Fresh deploys: server and client `flow` are rendered from the **same `VLESS_FLOW`** variable (default `xtls-rprx-vision`), so they always match; never edit `flow` by hand in rendered files.

## Final deliverable and report

1. `./singbox-work/clash.yaml` (path only; do not paste contents).
2. Table of verification results per node (see `singbox-minimal-deploy` step 7 and `singbox-reality-perf-troubleshoot` A7).
3. The Skill 2/3 TODO gaps that remain open (UDP application test, server-side DoH/DoT, geo-based 分流 - listed in those skills).
4. List of known open risks (from the recorded deployment, report them rather than hide them): server-side plain DNS to 8.8.8.8 / 1.1.1.1; UDP application-layer end-to-end not strictly proven; update/rollback and crash-recovery not drilled; no off-site encrypted backup; cloud security group source not restricted.
5. Reminder: any key that was ever shown in a screenshot/chat must be rotated (`singbox-reality-perf-troubleshoot/references/maintenance.md`, section 4).

## Quick reference (all commands are in the skills)

```bash
# LOCAL   (SB_DIR = directory containing the singbox-* skill folders)
SB_DIR=/path/to/skills/sing-box
mkdir -p singbox-work && chmod 700 singbox-work
cp $SB_DIR/singbox-minimal-deploy/templates/inputs.env.example singbox-work/secrets.env && chmod 600 singbox-work/secrets.env
# ... fill SERVER_IP SSH_PORT SSH_USER SSH_KEY (REALITY_SNI defaults to www.microsoft.com), then run skills 1..4 in order
$SB_DIR/singbox-minimal-deploy/scripts/gen-secrets.sh singbox-work/secrets.env                     # skill 1
python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py $SB_DIR/singbox-minimal-deploy/templates/config.ss.json.tpl singbox-work/config.json --env-file singbox-work/secrets.env
python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py $SB_DIR/singbox-minimal-deploy/templates/clash.ss.yaml.tpl singbox-work/clash.yaml --env-file singbox-work/secrets.env
$SB_DIR/singbox-reality-perf-troubleshoot/scripts/gen-reality-secrets.sh singbox-work/secrets.env  # skill 4
python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py $SB_DIR/singbox-reality-perf-troubleshoot/templates/config.ss-vless.json.tpl singbox-work/config.json --env-file singbox-work/secrets.env
python3 $SB_DIR/singbox-minimal-deploy/scripts/render.py $SB_DIR/singbox-reality-perf-troubleshoot/templates/clash.ss-vless.yaml.tpl singbox-work/clash.yaml --env-file singbox-work/secrets.env
python3 $SB_DIR/singbox-minimal-deploy/scripts/validate_clash.py singbox-work/clash.yaml
```
