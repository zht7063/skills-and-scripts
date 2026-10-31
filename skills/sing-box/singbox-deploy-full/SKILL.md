---
name: singbox-deploy-full
description: Use when the user asks a local agent (Claude Code, Codex, ...) to deploy a sing-box proxy server with Docker on a remote VPS over SSH - Shadowsocks 2022 plus VLESS-REALITY nodes - verify it from the local machine with a local mihomo/sing-box client, and end with a ready-to-use Clash (mihomo) YAML profile. Orchestrates the whole singbox-* skill set in order.
---

# sing-box full deployment (orchestrator)

Result: a Docker `sing-box` container on the remote server with **Shadowsocks 2022** (`${SS_PORT}` 8388 TCP+UDP) and **VLESS + REALITY** (`${VLESS_PORT}` 8443 TCP), verified end-to-end from the local machine, and a Clash / mihomo profile `./singbox-work/clash.yaml`.

Architecture: local Clash Verge / mihomo -> (SS 2022 | VLESS-REALITY) -> VPS Docker sing-box -> `direct` outbound -> Internet. No domain, TLS certificate, panel or subscription service is used.

## Who runs what

You are a **local agent** on the user's machine. You are given remote server info and connect over **SSH when a step says `[REMOTE]`**. Everything marked `[LOCAL]` runs on the user's machine (generating secrets, rendering templates, running a local proxy client, curl tests). Each stage skill marks every command accordingly.

## Required inputs - collect ALL before starting

| Input | Variable | Notes |
| --- | --- | --- |
| Server public IPv4 | `SERVER_IP` | |
| SSH port | `SSH_PORT` | often not 22 |
| SSH user | `SSH_USER` | usually root |
| SSH private key path (local) | `SSH_KEY` | key auth; if the user only has a password, ask them to set up a key/ssh-agent themselves - do not store passwords |
| REALITY camouflage site | `REALITY_SNI` | **default `www.microsoft.com`** (user's decision); fallbacks in order only if real testing fails: `www.intel.com`, then `www.nvidia.com` |
| Optional overrides | `SS_PORT` 8388, `VLESS_PORT` 8443, `INSTALL_DIR` /opt/sing-box, `LOG_LEVEL` info, `VLESS_FLOW` xtls-rprx-vision (same variable renders server and client) | defaults come from the recorded deployment |
| Local tools | `ssh`, `scp`, `openssl`, `python3` (+ PyYAML for validation), `curl`, `nc`; `mihomo` or `sing-box` for stage 7 | ask before installing anything |

Template for all variables: `templates/inputs.env.example` -> copy to `./singbox-work/secrets.env` (mode 600, never committed). Generated secrets use variables `SS_PASSWORD VLESS_UUID REALITY_PRIVATE_KEY REALITY_PUBLIC_KEY SHORT_ID`.

## Global rules (apply to every stage)

1. **Follow the stages strictly in order and render configs from the bundled templates. Do not improvise** commands, config fields, ports, images or file layouts. If something does not fit (unsupported OS, port taken, check fails), stop and report instead of working around it.
2. **Never change SSH configuration** on the server (sshd_config, authorized_keys, SSH port, SSH firewall rules) and never enable a default-deny firewall policy.
3. Secrets only in `./singbox-work/` (chmod 700 dir, 600 files, gitignored). Never put real IPs/passwords/keys into skill files, git, chat logs or screenshots. Do not print secret values in your reports.
4. Each stage ends with a verification checklist. **Do not start the next stage until every box is ticked.** Report failures with the failing command and its output (redacted).
5. **Client follows server for `flow`.** Never change a server's `flow` to match a client; on an existing server copy its actual flow (empty if absent) into the client first.
6. One change at a time; back up before modifying anything that already exists on the server; destructive or off-box actions need user confirmation.

## Stages (run in order)

| # | Skill | Where | Gate to proceed |
| --- | --- | --- | --- |
| 1 | `singbox-server-prep` | LOCAL + REMOTE (read-only) | SSH ok, OS/arch ok, ports free, work dir ready |
| 2 | `singbox-docker-install` | REMOTE | `docker compose version` works, sing-box image pulls |
| 3 | `singbox-config-generate` | LOCAL (+ remote `docker run --rm` for keys) | secrets valid, `config.json` rendered, no `${` left |
| 4 | `singbox-compose-run` | LOCAL -> REMOTE | `sing-box check` = CONFIG_OK, container Up, TCP/UDP 8388 + TCP 8443 listening |
| 5 | `singbox-firewall-ports` | REMOTE read + user (cloud SG) + LOCAL | ports reachable from local machine |
| 6 | `singbox-clash-config` | LOCAL | `validate_clash.py` OK |
| 7 | `singbox-local-verify` | LOCAL (+ remote log read) | both nodes: egress IP == server, 204 OK, seen in server log |
| 8 | `singbox-maintenance` | REMOTE | optional: backup, rollback tag, log rotation verified |

`singbox-troubleshooting` is the reference when any gate fails.

Re-runs: stages are idempotent as written (mkdir -p, config backed up before overwrite). If the server already runs the node (stage 1 finds container `sing-box`), ask the user whether to reuse the existing credentials (then skip stage 3 and copy the existing values into `secrets.env`) or replace them (back up first, rotate, update clients).

## REALITY SNI default and fallback

- Default: `REALITY_SNI=www.microsoft.com` for server `tls.server_name`, server `reality.handshake.server` (`handshake.server_port` 443) and the client `servername` - all three always identical.
- Keep it unless **real testing fails** (VLESS handshake failure/timeouts after port, UUID, keys, short id and flow were ruled out - see `singbox-local-verify` "When to switch the REALITY SNI"). Then switch in this order: `www.intel.com`, then `www.nvidia.com`. If all three fail, stop and report; never try other sites.
- Switching changes **both** the server `config.json` and the Clash `servername` together: set the new `REALITY_SNI` in `secrets.env` -> re-render server config and `clash.yaml` (credentials unchanged) -> back up + upload -> `sing-box check` (must pass) -> `docker compose restart` -> re-run stage 7 for both nodes. Full commands: `singbox-config-generate`, section "SNI fallback procedure".

## Existing server path (server NOT deployed by these skills)

Use this instead of stages 2-5 when the user already has a working sing-box server and only wants client profiles / verification. **Do not change the server in any way.**

1. Stage 1 (`singbox-server-prep`) read-only parts only: SSH works, find where `config.json` lives (ask the user; default `${INSTALL_DIR}` = `/opt/sing-box`).
2. **[REMOTE, read-only] Before generating any client config**, check the server's actual flow and other client-relevant values with `scripts/inspect-server-config.py` (see `singbox-clash-config`, "Flow rule"). Copy `VLESS_FLOW` from the server into `secrets.env` - **empty if the user has no `flow` field**. Also copy UUID, short id, ports, SS method/password and `REALITY_SNI` (= server `tls.server_name`) from the same output; the REALITY *public* key comes from the user.
3. **Never modify the server's `flow` (or any server setting) to match the client.** If a mismatch appears later, the client is changed, not the server. The SNI fallback procedure does not apply to an existing server unless the user explicitly asks to change the server.
4. Stage 6 `singbox-clash-config` -> stage 7 `singbox-local-verify` (it re-checks flow if the VLESS node fails). Report the flow value that was copied and its source.

Fresh deploys (stages 1-8): server and client `flow` are rendered from the **same `VLESS_FLOW`** variable (default `xtls-rprx-vision`), so they always match; never edit `flow` by hand in rendered files.

## Final deliverable and report

1. `./singbox-work/clash.yaml` (path only; do not paste contents).
2. Table of verification results per node (see `singbox-local-verify`).
3. List of known open risks (from the recorded deployment, report them rather than hide them): server-side plain DNS to 8.8.8.8 / 1.1.1.1; UDP application-layer end-to-end not strictly proven; update/rollback and crash-recovery not drilled; no off-site encrypted backup; cloud security group source not restricted.
4. Reminder: any key that was ever shown in a screenshot/chat must be rotated (`singbox-maintenance` section 4).

## Quick reference (all commands are in the stage skills)

```bash
# LOCAL
mkdir -p singbox-work && chmod 700 singbox-work
cp singbox-deploy-full/templates/inputs.env.example singbox-work/secrets.env && chmod 600 singbox-work/secrets.env
# ... fill SERVER_IP SSH_PORT SSH_USER SSH_KEY (REALITY_SNI defaults to www.microsoft.com), then run stages 1..7 in order
singbox-config-generate/scripts/gen-secrets.sh singbox-work/secrets.env
python3 singbox-config-generate/scripts/render.py singbox-config-generate/templates/config.ss-vless.json.tpl singbox-work/config.json --env-file singbox-work/secrets.env
python3 singbox-clash-config/scripts/render.py singbox-clash-config/templates/clash.yaml.tpl singbox-work/clash.yaml --env-file singbox-work/secrets.env
python3 singbox-clash-config/scripts/validate_clash.py singbox-work/clash.yaml
```
