---
name: singbox-compose-run
description: Use when a local agent must upload the rendered sing-box config.json and docker-compose file to the remote server over SSH, validate it with `sing-box check`, start the container with Docker Compose (host network, restart policy, log rotation) and verify TCP/UDP listeners and logs. Stage 4 of the sing-box deployment skill set.
---

# sing-box stage 4 - upload, check, run

**Local agent driving a remote server.** Inputs: `SERVER_IP SSH_PORT SSH_USER SSH_KEY INSTALL_DIR` (default `/opt/sing-box`, from `secrets.env`) and the rendered `./singbox-work/config.json` from stage 3.

**Use `templates/compose.yaml` exactly as provided. Do not add `ports:` (host networking publishes ports itself), do not change the image to a pinned/other tag unless the user asks, do not edit the config on the server by hand - re-render locally and re-upload.**

```bash
SSH="ssh -p ${SSH_PORT} -i ${SSH_KEY} -o StrictHostKeyChecking=accept-new ${SSH_USER}@${SERVER_IP}"
SCP="scp -P ${SSH_PORT} -i ${SSH_KEY}"
```

## Template: `templates/compose.yaml`

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

## Steps

1. **[REMOTE] working directory** (idempotent)
   ```bash
   $SSH "mkdir -p ${INSTALL_DIR}/backups && chmod 700 ${INSTALL_DIR}"
   ```
   If `${INSTALL_DIR}/config.json` already exists, back it up first (REMOTE): `cp config.json backups/config.json.$(date +%Y%m%d-%H%M%S)`.

2. **[LOCAL -> REMOTE] upload**
   ```bash
   $SCP singbox-compose-run/templates/compose.yaml ${SSH_USER}@${SERVER_IP}:${INSTALL_DIR}/compose.yaml
   $SCP singbox-work/config.json ${SSH_USER}@${SERVER_IP}:${INSTALL_DIR}/config.json
   $SSH "chmod 600 ${INSTALL_DIR}/config.json"
   ```
   (If skills are installed elsewhere, use the actual path of `templates/compose.yaml`.)

3. **[REMOTE] pull, validate compose and config**
   ```bash
   $SSH "cd ${INSTALL_DIR} && docker compose config -q && docker compose pull"
   $SSH "cd ${INSTALL_DIR} && docker compose run --rm sing-box -c /etc/sing-box/config.json check && echo CONFIG_OK"
   ```
   **Gate:** must print `CONFIG_OK` with exit code 0. If `check` reports an error, fix the template inputs locally (stage 3) - do not start the container.

4. **[REMOTE] start**
   ```bash
   $SSH "cd ${INSTALL_DIR} && docker compose up -d && docker compose ps && docker compose logs --tail=30"
   ```
   Check: container `Up`; log contains `sing-box started`.

5. **[REMOTE] listener verification**
   ```bash
   $SSH "ss -lntup | grep -E ':(${SS_PORT}|${VLESS_PORT})\b'"
   ```
   Expected exactly:
   - `tcp LISTEN 0.0.0.0:${SS_PORT}` and `udp UNCONN 0.0.0.0:${SS_PORT}` (Shadowsocks TCP+UDP)
   - `tcp LISTEN 0.0.0.0:${VLESS_PORT}` (VLESS-REALITY)
   Also: `$SSH "docker inspect sing-box --format '{{json .HostConfig.LogConfig}}'"` -> `{"Type":"json-file","Config":{"max-file":"3","max-size":"10m"}}`; `$SSH "docker inspect sing-box --format '{{.HostConfig.RestartPolicy.Name}}'"` -> `unless-stopped`.

6. **[REMOTE] restart-recovery check**
   ```bash
   $SSH "cd ${INSTALL_DIR} && docker compose restart && sleep 3 && docker compose ps && docker compose logs --tail=10"
   ```
   Log should show TCP and UDP listeners on `${SS_PORT}`, the VLESS listener on `${VLESS_PORT}`, then `sing-box started`. (A manual restart proves recovery from restart, not from a crash or reboot; a reboot test is optional and needs user approval.)

Local reachability (can the Internet reach the ports?) is verified in stages 5 and 7 - a listener on the server does **not** prove the cloud security group allows it.

## Operating notes

- Logs: agents should use `$SSH "cd ${INSTALL_DIR} && docker compose logs --tail=50"` (never leave `logs -f` running in a non-interactive session; for humans Ctrl+C stops following without stopping the container). With `LOG_LEVEL=info` every connection is logged; switching to `warn` means: edit the template variable, re-render, upload, `check`, then restart.
- Never publish `config.json`.
