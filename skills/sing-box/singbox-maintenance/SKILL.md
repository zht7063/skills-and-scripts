---
name: singbox-maintenance
description: Use when a local agent must back up, update, roll back, rotate credentials or inspect logs of an already deployed sing-box Docker node over SSH (backup of compose/config, log rotation, restart policy, image update with a local rollback tag). Stage 8 of the sing-box deployment skill set.
---

# sing-box stage 8 - backup, logs, update, rollback

**Local agent, remote execution via ssh.** Inputs: `SERVER_IP SSH_PORT SSH_USER SSH_KEY INSTALL_DIR` (`/opt/sing-box`). Run only the stage the user asked for. Change one variable class at a time: save the original -> change -> `check` -> restart -> test -> record. Never change SSH configuration. Always re-test with `singbox-local-verify` after a change.

```bash
SSH="ssh -p ${SSH_PORT} -i ${SSH_KEY} -o StrictHostKeyChecking=accept-new ${SSH_USER}@${SERVER_IP}"
```

## 1. On-server config backup

**[REMOTE]**
```bash
$SSH "cd ${INSTALL_DIR} && mkdir -p backups && cp compose.yaml backups/compose.yaml && cp config.json backups/config.json && chmod 600 backups/config.json && ls -l backups"
```
`config.json` contains secrets: never upload it to a public repository. This is a same-host backup, not an off-site one; if the user wants durability, copy it **encrypted** off the server (ask first) and/or keep the rendered files in the local gitignored `singbox-work/` (`scp -P ${SSH_PORT} -i ${SSH_KEY} ${SSH_USER}@${SERVER_IP}:${INSTALL_DIR}/config.json ./singbox-work/config.server-copy.json`, then `chmod 600`).

## 2. Log rotation + restart policy (verify; already in compose template)

**[REMOTE]**
```bash
$SSH "cd ${INSTALL_DIR} && docker compose config -q && docker inspect sing-box --format '{{json .HostConfig.LogConfig}}' && docker inspect sing-box --format '{{.HostConfig.RestartPolicy.Name}}'"
```
Expected: `{"Type":"json-file","Config":{"max-file":"3","max-size":"10m"}}` and `unless-stopped`. If missing, re-upload `singbox-compose-run/templates/compose.yaml` and run `docker compose up -d`.
No Docker `HEALTHCHECK` is used on purpose: compose does not restart on `unhealthy`, and a port check does not prove end-to-end proxying. Rely on restart policy, logs and real client tests (stage 7).

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
$SSH "cd ${INSTALL_DIR} && docker compose pull && docker compose run --rm sing-box -c /etc/sing-box/config.json check && docker compose up -d && docker compose ps && docker compose logs --tail=20"
```
Gate: `check` must pass with the **new** image before `up -d`. Then run `singbox-local-verify` for both nodes.

Rollback (REMOTE) if broken: set `image: sing-box:rollback` in `compose.yaml` (edit locally in the template copy, re-upload) and `docker compose up -d`; restore `backups/config.json` if the config format changed incompatibly. Note: **the rollback procedure itself has not been exercised in the recorded deployment** - test it on a maintenance window before relying on it. Do not `docker image prune` while the rollback tag matters.

## 4. Rotating credentials

Use when a key was exposed (screenshots, chat, repo). Re-run `singbox-config-generate` (new `SS_PASSWORD`, UUID, keypair, short id), re-render, back up first (step 1), upload, `check`, restart, re-render the Clash file (`singbox-clash-config`), re-verify. Old clients stop working until updated.

## 5. Routine checks

```bash
$SSH "cd ${INSTALL_DIR} && docker compose ps && docker compose logs --tail=50"
$SSH "ss -lntup | grep -E ':(${SS_PORT}|${VLESS_PORT})\b'"
```
Open items in the source notes (not yet done): crash-recovery test, off-site encrypted backup, real update + rollback drill, long-running availability monitoring, security-group source restriction.
