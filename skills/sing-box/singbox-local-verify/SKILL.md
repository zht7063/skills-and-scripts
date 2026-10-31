---
name: singbox-local-verify
description: Use when a local agent must prove that a deployed sing-box server (Shadowsocks 2022 and VLESS-REALITY) really works by running a LOCAL mihomo or sing-box client against it, checking egress IP, HTTP 204, UDP/IPv6/DNS behaviour and a 20-request performance baseline, with matching server-side log checks over SSH. Stage 7 of the sing-box deployment skill set.
---

# sing-box stage 7 - local end-to-end verification

**Mostly LOCAL.** The agent runs a local proxy client on the user's machine, sends test traffic through the **deployed** server, and optionally reads the server log over ssh (read-only). Inputs: `./singbox-work/secrets.env` (all variables), `./singbox-work/clash.yaml` (stage 6) and a `mihomo` **or** `sing-box` binary on PATH (the user installs it; ask before installing anything; Clash Verge can be used manually instead).

**Use the templates/scripts provided. Test each node separately and record pass/fail per node. Do not declare success from one test: TCP egress IP correct does not prove DNS has no leaks, UDP works, or IPv6/WebRTC are right.**

## Files

| File | Use |
| --- | --- |
| `templates/singbox-client.json.tpl` | local **sing-box** client config (`mixed` inbound, `ss-out` + `vless-out`; `${TEST_OUTBOUND}` chooses which one is `route.final`) |
| `../singbox-clash-config/templates/clash.yaml.tpl` | local **mihomo** client config (stage 6 output) |
| `scripts/run-local-client.sh` | start client in background, select node, run egress check, show client log, stop client |
| `scripts/egress-check.sh` | direct vs proxied egress IP, `generate_204`, IPv6 info |
| `scripts/perf-baseline.sh` | 20 sequential requests -> success rate, mean/median/p95/min/max |
| `scripts/render.py` | placeholder renderer |

Set `ENV_FILE=./singbox-work/secrets.env` (default).

## A. Local client = mihomo (primary)

1. **[LOCAL]** static check: `mihomo -t -d singbox-work -f singbox-work/clash.yaml` (if available).
2. **[LOCAL]** per node:
   ```bash
   scripts/run-local-client.sh mihomo ./singbox-work/clash.yaml My-sing-box
   scripts/run-local-client.sh mihomo ./singbox-work/clash.yaml My-VLESS-Reality
   ```
   The script starts mihomo (mixed port `${LOCAL_MIXED_PORT}`), selects the node through the controller (`PUT /proxies/PROXY`), and runs `egress-check.sh`.
   Pass criteria **per node**: proxied egress == `${SERVER_IP}`; `generate_204` = HTTP 204.
   If port 7890/9090 are busy locally, change `LOCAL_MIXED_PORT` / `LOCAL_CONTROLLER_PORT` in `secrets.env` and re-render the clash file.

## B. Local client = sing-box (alternative / cross-check)

```bash
for NODE in ss-out vless-out; do
  TEST_OUTBOUND=$NODE python3 scripts/render.py templates/singbox-client.json.tpl ./singbox-work/client-$NODE.json --env-file ./singbox-work/secrets.env
  sing-box check -c ./singbox-work/client-$NODE.json
  scripts/run-local-client.sh sing-box ./singbox-work/client-$NODE.json
done
```
Same pass criteria. (`render.py` ignores shell-only variables; `TEST_OUTBOUND` is read from the environment.)

## C. Manual curl through a running client (any client)

```bash
curl -4 -x http://127.0.0.1:${LOCAL_MIXED_PORT} https://api.ipify.org          # expect ${SERVER_IP}
curl -4 -x http://127.0.0.1:${LOCAL_MIXED_PORT} -o /dev/null -w '%{http_code}\n' https://www.google.com/generate_204   # expect 204
```
With Clash Verge TUN on (no `-x`): `curl -4 https://api.ipify.org` should also return `${SERVER_IP}`. Do not use `api.ipinfo.io/lookup/...` (needs a token; 403 is an auth error, not a proxy failure); use `api.ipify.org` or `ipinfo.io/ip`. Comparing `DIRECT` vs the node rules out a coincidence where the local network already exits via the same IP.

## D. Server-side corroboration (read-only, [REMOTE])

While a node is under test:
```bash
SSH="ssh -p ${SSH_PORT} -i ${SSH_KEY} ${SSH_USER}@${SERVER_IP}"
$SSH "cd ${INSTALL_DIR} && docker compose logs --tail=40"
```
Expected log evidence: for SS, an `inbound/shadowsocks[ss-in]` connection followed by `outbound/direct`; for VLESS, `inbound/vless[vless-reality-in]`, `[client-1]` and `outbound/direct` for the test domains (e.g. `api.ipify.org`). A node whose requests never appear in the server log was not actually used.

## E. Extra checks (record results, do not over-claim)

- **UDP (SS)**: with `udp: true`, run a non-DNS UDP application test if available (e.g. a controlled UDP echo/QUIC target). Network-layer proof: server `tcpdump -ni any -c 10 -q 'udp dst port ${SS_PORT}'` shows packets from the client during the test; bidirectional capture shows both directions. Capture alone is not proof that real application requests were decrypted and forwarded.
- **DNS**: `dig @1.1.1.1 google.com +notcp` with TUN/Fake-IP active returns `198.18.x.x` -> local DNS takeover only. Optionally capture local physical NIC for plain port-53 traffic: `sudo tcpdump -ni <nic> -q '(udp port 53 or tcp port 53)'`. Known accepted risk: the **server** resolves destination domains with its system resolver (plain UDP 53 to 8.8.8.8/1.1.1.1) - do not report this as "zero DNS leak".
- **IPv6**: `curl -6 --max-time 8 -x http://127.0.0.1:${LOCAL_MIXED_PORT} https://api64.ipify.org`; compare with `$SSH 'curl -6 --max-time 10 https://api64.ipify.org'` (equal -> the request exits via the VPS; if the VPS has no IPv6 this fails, which is informational).
- **WebRTC UDP** (browser, only with TUN/system proxy): an IP other than `${SERVER_IP}` in a WebRTC test means UDP is not proxied - confirm the selected node has `udp: true` (and `packet-encoding: xudp` for VLESS) and retest.

## E2. When to switch the REALITY SNI (VLESS node only)

Switch only if SS passes but the **VLESS-REALITY** node fails in a way that points to the handshake, i.e. **after** you have excluded the other causes (port 8443 reachable via `nc`, `uuid`/public key/short id/`flow` identical on both sides, server `check` OK):
- local client log shows REALITY/TLS handshake errors, `EOF`, `reality verification failed`, or connection timeouts to `${SERVER_IP}:${VLESS_PORT}` while `nc -zv` succeeds;
- server log shows no `inbound/vless[vless-reality-in]` entry for the test, or shows handshake/`REALITY: processed invalid connection` style errors;
- the server cannot reach the SNI site: `[REMOTE] curl -sS -o /dev/null -m 10 -w '%{http_code}\n' https://${REALITY_SNI}` fails/times out.

Then follow the **SNI fallback procedure in `singbox-config-generate`**: `www.microsoft.com` (default) -> `www.intel.com` -> `www.nvidia.com`. Server `config.json` (`tls.server_name` + `reality.handshake.server`, port 443) and the client `servername` **must be changed together**, then `sing-box check`, restart, and re-run stage 7 for both nodes. Try one fallback at a time; if all three fail, stop and report instead of trying other sites. Do not switch for SS problems or for a single slow request.

## F. Performance baseline (optional, run when comparing protocols)

```bash
scripts/run-local-client.sh ... # select node, keep it running, or use your GUI client
scripts/perf-baseline.sh http://127.0.0.1:${LOCAL_MIXED_PORT} 20
```
Recorded reference (one mobile-hotspot run, not conclusive): SS 2022 ~401 ms mean / 100 % success; VLESS+REALITY ~545 ms mean / 100 % success. For a fair comparison alternate A->B->B->A, same network, same target; do not generalise from a single run.

## Verification summary (report to the user as a table, no secrets)

| Check | SS 2022 | VLESS-REALITY |
| --- | --- | --- |
| egress IP == server | | |
| generate_204 == 204 | | |
| appears in server log | | |
| UDP evidence | | |
| IPv6 (info) | | |
