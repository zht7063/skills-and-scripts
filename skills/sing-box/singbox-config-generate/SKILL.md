---
name: singbox-config-generate
description: Use when a local agent must generate the credentials (Shadowsocks 2022 key, VLESS UUID, REALITY x25519 keypair, short id) and render the sing-box server config.json for a Shadowsocks 2022 + VLESS-REALITY node from the bundled templates. Stage 3 of the sing-box deployment skill set; runs after Docker is installed, before the container is started.
---

# sing-box stage 3 - secrets and server `config.json`

**Local agent.** Secrets are generated and the config is rendered **locally**; the only remote commands are `docker run --rm ghcr.io/sagernet/sing-box ...` (to produce the UUID and REALITY keypair with the same sing-box version that will serve them) and, later, `scp` of the finished file (stage 4).

**Follow this stage strictly and render from the templates in `templates/`. Do not hand-write or "improve" JSON, and do not change field names, ports or the `method`.** If a field you think is needed is not in the template, stop and ask.

## Inputs

From `./singbox-work/secrets.env` (see `singbox-deploy-full/templates/inputs.env.example`): `SERVER_IP SSH_PORT SSH_USER SSH_KEY`, `SS_PORT` (8388), `SS_METHOD` (`2022-blake3-aes-128-gcm`), `VLESS_PORT` (8443), `VLESS_FLOW` (`xtls-rprx-vision`), `LOG_LEVEL` (`info`), and **`REALITY_SNI`**.

### REALITY_SNI must be decided with the user

`REALITY_SNI` is the real, TLS 1.3 / h2-capable public website the server impersonates (it is used both as `server_name` and as the `handshake.server`; the client must use the **identical** value as its `servername`). The recorded notes do not state which site was used. Do not invent one silently: propose a well-known large site (e.g. a major CDN/vendor site that supports TLS 1.3 and is reachable from the VPS), confirm with the user, and verify reachability from the server:

**[REMOTE]**
```bash
$SSH 'curl -sS -o /dev/null -w "%{http_code} %{ssl_verify_result}\n" --max-time 10 https://${REALITY_SNI}'
```
Must return an HTTP status (200/301/302) quickly.

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
