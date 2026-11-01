# sing-box maintenance - backup, logs, update, rollback

Reference for `singbox-reality-perf-troubleshoot` (applies to the base `singbox-minimal-deploy` node and the VLESS-REALITY node). **Local agent, remote execution via ssh** (every command is `[REMOTE]` unless marked `[LOCAL]`). Inputs: `SERVER_IP SSH_PORT SSH_USER SSH_KEY`; `REMOTE_DIR=/opt/sing-box` is fixed - all sing-box files on the server (config, compose file, backups) live there and nowhere else. Run only the section the user asked for. Change one variable class at a time: save the original -> change -> `check` -> restart -> test -> record. Never change SSH configuration. Always re-test (base step 7 / `SKILL.md` A7) after a change.

```bash
REMOTE_DIR=/opt/sing-box
SSH="ssh -p ${SSH_PORT} -i ${SSH_KEY} -o StrictHostKeyChecking=accept-new ${SSH_USER}@${SERVER_IP}"
```

## 1. On-server config backup

**[REMOTE]**
```bash
$SSH "cd ${REMOTE_DIR} && mkdir -p backups && cp compose.yaml backups/compose.yaml && cp config.json backups/config.json && chmod 600 backups/config.json && ls -l backups"
```
`config.json` contains secrets: never upload it to a public repository. This is a same-host backup, not an off-site one; if the user wants durability, copy it **encrypted** off the server (ask first) and/or keep the rendered files in the local gitignored `singbox-work/` (`scp -P ${SSH_PORT} -i ${SSH_KEY} ${SSH_USER}@${SERVER_IP}:${REMOTE_DIR}/config.json ./singbox-work/config.server-copy.json`, then `chmod 600`).

## 2. Log files, rotation + restart policy (verify; already in compose template)

**[REMOTE]**
```bash
$SSH "cd ${REMOTE_DIR} && docker compose config -q && ls -l logs && docker compose ps && docker logs sing-box-logrotate --tail=3"
$SSH "docker inspect sing-box --format '{{json .HostConfig.LogConfig}}' && docker inspect sing-box --format '{{.HostConfig.RestartPolicy.Name}}'"
```
Expected: `logs/sing-box.log` (+ `.N.gz` archives) in `/opt/sing-box/logs`, both `sing-box` and `sing-box-logrotate` Up, the sidecar printing `rotate-logs: watching ...`, `{"Type":"json-file","Config":{"max-file":"3","max-size":"10m"}}` (stdout/stderr safety net) and `unless-stopped`. If something is missing, back up and re-upload `singbox-minimal-deploy/templates/compose.yaml` + `rotate-logs.sh`, `mkdir -p logs`, then `docker compose up -d`. Design and the forced-rotation test: base skill "Logs and rotation".
No Docker `HEALTHCHECK` is used on purpose: compose does not restart on `unhealthy`, and a port check does not prove end-to-end proxying. Rely on restart policy, logs and real client tests (base step 7).

## 3. Update with rollback tag

Record state **before** updating (REMOTE):
```bash
$SSH "docker exec sing-box sing-box version"
$SSH "docker image inspect ghcr.io/sagernet/sing-box:latest --format '{{.Id}}'"
$SSH "docker tag ghcr.io/sagernet/sing-box:latest sing-box:rollback && docker images sing-box"
```
Check: `sing-box:rollback` is listed and its image ID prefix equals the current image (the recorded deployment ran **1.14.4**, `linux/amd64`). Keep a note of the version this tag corresponds to - re-tagging overwrites it.

Update (REMOTE), only after the rollback tag exists:
```bash
$SSH "cd ${REMOTE_DIR} && docker compose pull && docker compose run --rm sing-box -c /etc/sing-box/config.json check && docker compose up -d && docker compose ps && tail -n 20 logs/sing-box.log"
```
Gate: `check` must pass with the **new** image before `up -d`. Then re-run the local verification (base step 7 / `SKILL.md` A7) for both nodes.

Rollback (REMOTE) if broken: set `image: sing-box:rollback` on BOTH services (`sing-box` and `log-rotate`) in `compose.yaml` (edit locally in the template copy, re-upload) and `docker compose up -d`; restore `backups/config.json` if the config format changed incompatibly. Note: **the rollback procedure itself has not been exercised in the recorded deployment** - test it on a maintenance window before relying on it. Do not `docker image prune` while the rollback tag matters.

### Known-stable version 1.14.4 (rollback when `latest` has problems)

`latest` is the default image; **sing-box 1.14.4** (`linux/amd64`, image tag `v1.14.4`) is the known-stable reference from the recorded deployment. If the newly pulled `latest` has problems (`check` fails, restart loop, nodes fail with unchanged config), pin the compose file to `ghcr.io/sagernet/sing-box:v1.14.4` using the commands in `singbox-minimal-deploy/SKILL.md`, section "Image version: `latest` by default, 1.14.4 as the known-stable reference" (**[LOCAL]** `sed` a pinned copy of the template -> **[REMOTE]** back up `compose.yaml` into `${REMOTE_DIR}/backups/` -> upload -> `docker compose pull` -> `check` -> `up -d` -> `docker exec sing-box sing-box version` = 1.14.4). The local `sing-box:rollback` tag above is the alternative that restores whatever image was running *before* the update.

## 4. Rotating credentials

Use when a key was exposed (screenshots, chat, repo). Generate new values (`singbox-minimal-deploy/scripts/gen-secrets.sh` for `SS_PASSWORD`, `scripts/gen-reality-secrets.sh` for UUID, keypair, short id), re-render, back up first (step 1), upload, `check`, restart, re-render the Clash file (`SKILL.md` A6), re-verify. Old clients stop working until updated.

## 5. Routine checks

```bash
$SSH "cd ${REMOTE_DIR} && docker compose ps && tail -n 50 logs/sing-box.log"
$SSH "ss -lntup | grep -E ':(${SS_PORT}|${VLESS_PORT})\b'"
```
Open items in the source notes (not yet done): crash-recovery test, off-site encrypted backup, real update + rollback drill, long-running availability monitoring, security-group source restriction.
