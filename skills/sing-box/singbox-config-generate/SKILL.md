---
name: singbox-config-generate
description: Use when a local agent must generate the credentials (Shadowsocks 2022 key, VLESS UUID, REALITY x25519 keypair, short id) and render the sing-box server config.json for a Shadowsocks 2022 + VLESS-REALITY node from the bundled templates. Stage 3 of the sing-box deployment skill set; runs after Docker is installed, before the container is started.
---

# sing-box stage 3 - secrets and server `config.json`

**Local agent.** Secrets are generated and the config is rendered **locally**; the only remote commands are `docker run --rm ghcr.io/sagernet/sing-box ...` (to produce the UUID and REALITY keypair with the same sing-box version that will serve them) and, later, `scp` of the finished file (stage 4).

**Follow this stage strictly and render from the templates in `templates/`. Do not hand-write or "improve" JSON, and do not change field names, ports or the `method`.** If a field you think is needed is not in the template, stop and ask.

## Inputs

From `./singbox-work/secrets.env` (see `singbox-deploy-full/templates/inputs.env.example`): `SERVER_IP SSH_PORT SSH_USER SSH_KEY`, `SS_PORT` (8388), `SS_METHOD` (`2022-blake3-aes-128-gcm`), `VLESS_PORT` (8443), `VLESS_FLOW` (`xtls-rprx-vision`), `LOG_LEVEL` (`info`), and **`REALITY_SNI`** (default `www.microsoft.com`).

### REALITY_SNI: default `www.microsoft.com`, with an ordered fallback

The user decided: **`REALITY_SNI=www.microsoft.com` by default**. It is a real TLS 1.3 / h2 public site that the server impersonates. One value is used in three places and they must always be identical:

| Where | Field |
| --- | --- |
| server `config.json` | `tls.server_name` |
| server `config.json` | `tls.reality.handshake.server` (with `handshake.server_port` = **443**) |
| client (Clash / sing-box client) | `servername` / `tls.server_name` |

**Fallback order, only if real testing fails** (see `singbox-local-verify` for what counts as a failure): `www.microsoft.com` -> `www.intel.com` -> `www.nvidia.com`. Do not pick any other site and do not switch "just in case"; keep microsoft while it works.

Reachability pre-check from the server before the first deployment (**[REMOTE]**, read-only):
```bash
$SSH 'curl -sS -o /dev/null -w "%{http_code} verify=%{ssl_verify_result}\n" --max-time 10 https://www.microsoft.com'
```
Must return an HTTP status (200/301/302) quickly. If it fails or times out, record it and try the next fallback in order (same check) *before* deploying.

### SNI fallback procedure (switching an already deployed node)

Switching the SNI changes **server and clients together**; doing only one side breaks the VLESS node (SS is unaffected).

1. **[LOCAL]** set the next value in `./singbox-work/secrets.env`: `REALITY_SNI=www.intel.com` (second failure: `www.nvidia.com`). If all three fail, stop and report to the user with the logs; do not try other sites.
2. **[LOCAL]** re-render the server config and the client config(s) from the templates:
   ```bash
   python3 scripts/render.py templates/config.ss-vless.json.tpl ./singbox-work/config.json --env-file ./singbox-work/secrets.env
   python3 ../singbox-clash-config/scripts/render.py ../singbox-clash-config/templates/clash.yaml.tpl ./singbox-work/clash.yaml --env-file ./singbox-work/secrets.env
   python3 ../singbox-clash-config/scripts/validate_clash.py ./singbox-work/clash.yaml
   ```
   Credentials (UUID, keypair, short id) are **unchanged** - do not regenerate them.
3. **[REMOTE]** back up, upload, check, restart (details in `singbox-compose-run`):
   ```bash
   $SSH "cd ${INSTALL_DIR} && cp config.json backups/config.json.$(date +%Y%m%d-%H%M%S)"
   scp -P ${SSH_PORT} -i ${SSH_KEY} ./singbox-work/config.json ${SSH_USER}@${SERVER_IP}:${INSTALL_DIR}/config.json
   $SSH "chmod 600 ${INSTALL_DIR}/config.json && cd ${INSTALL_DIR} && docker compose run --rm sing-box -c /etc/sing-box/config.json check && echo CONFIG_OK"
   $SSH "cd ${INSTALL_DIR} && docker compose restart && sleep 3 && docker compose ps && docker compose logs --tail=20"
   ```
   Gate: `CONFIG_OK` before restart; log shows the TCP `${VLESS_PORT}` listener and `sing-box started`.
4. **[LOCAL]** re-import/refresh `clash.yaml` in the client and re-run `singbox-local-verify` for **both** nodes. Record which SNI finally works in `singbox-work/NOTES.md` (no secrets).

## Templates (in this skill)

| File | Use |
| --- | --- |
| `templates/config.ss.json.tpl` | Shadowsocks-2022-only baseline (TCP+UDP, no `network` key) |
| `templates/config.ss-vless.json.tpl` | **Default**: SS 2022 (`ss-in`, 8388 TCP+UDP) + VLESS-REALITY (`vless-reality-in`, 8443 TCP) + `direct` outbound |
| `templates/secrets.env.example` | variable names produced by this stage |
| `scripts/gen-secrets.sh` | generates the 5 secrets into `secrets.env` |
| `scripts/render.py` | renders `${VAR}` placeholders, refuses unset/`TODO` values, writes mode 600 |

Why no `"network": "tcp"` on the SS inbound: the first prototype was TCP-only; removing `network` lets sing-box serve TCP **and** UDP. Do not write `"tcp,udp"` (unverified/invalid).

## Steps

1. **[LOCAL] generate secrets**
   ```bash
   ./scripts/gen-secrets.sh ./singbox-work/secrets.env
   ```
   Equivalent manual commands (only if the script cannot be used):
   - SS key: `openssl rand -base64 16` (16 bytes -> 22 base64 chars + `==`)
   - short id: `openssl rand -hex 8` (16 hex chars)
   - UUID: `[REMOTE] docker run --rm ghcr.io/sagernet/sing-box:latest generate uuid`
   - REALITY keypair: `[REMOTE] docker run --rm ghcr.io/sagernet/sing-box:latest generate reality-keypair` -> `PrivateKey` goes to the server config, **`PublicKey` goes to clients only**.

   Verify (LOCAL, do not print values):
   ```bash
   set -a; . ./singbox-work/secrets.env; set +a
   [ "$(printf %s "$SS_PASSWORD" | base64 -d 2>/dev/null | wc -c)" = 16 ] && echo "SS key: 16 bytes OK"
   [[ "$SHORT_ID" =~ ^[0-9a-f]{16}$ ]] && echo "short id OK"
   [[ "$VLESS_UUID" =~ ^[0-9a-f-]{36}$ ]] && echo "uuid OK"
   [ -n "$REALITY_PRIVATE_KEY" ] && [ -n "$REALITY_PUBLIC_KEY" ] && [ "$REALITY_PRIVATE_KEY" != "$REALITY_PUBLIC_KEY" ] && echo "keypair OK"
   ```

2. **[LOCAL] render the config**
   ```bash
   python3 ./scripts/render.py templates/config.ss-vless.json.tpl ./singbox-work/config.json --env-file ./singbox-work/secrets.env
   ```
   `render.py` exits non-zero if any variable is unset or still `TODO*`.

3. **[LOCAL] static verification**
   ```bash
   python3 -c "import json;d=json.load(open('singbox-work/config.json'));print([i['tag'] for i in d['inbounds']], [o['tag'] for o in d['outbounds']])"
   grep -c '\${' singbox-work/config.json   # must print 0
   grep -n '"network"' singbox-work/config.json || echo 'no network key (TCP+UDP) OK'
   ls -l singbox-work/config.json            # -rw------- expected
   ```
   Expected tags: inbounds `['ss-in', 'vless-reality-in']`, outbounds `['direct']`.

   The authoritative syntax check is `sing-box check` on the server in stage 4 (same image/version as production).

## Security rules

- `secrets.env` and `config.json` contain secrets: mode 600, local `singbox-work/` only, **never** committed, pasted in chat/issues, or screenshotted (the recorded run exposed a test key in screenshots and had to rotate it). If a key was ever displayed publicly, generate a new one.
- Only the REALITY **public** key and short id go into client configs.
