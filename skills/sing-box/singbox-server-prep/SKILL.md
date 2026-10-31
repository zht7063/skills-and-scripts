---
name: singbox-server-prep
description: Use FIRST when deploying sing-box on a fresh or existing remote Linux VPS from a local agent over SSH - checks OS, CPU architecture, listening ports, existing Docker and firewall state and picks free proxy ports without touching the server's SSH configuration. Part of the sing-box deployment skill set (stage 1).
---

# sing-box stage 1 - server preparation (read-only)

You are a **local** agent (Claude Code / Codex on the user's machine). The server is remote and is reached only through `ssh`. This stage only **reads** state. Follow the steps in order; do not improvise extra changes.

## Required inputs (ask the user up front if missing)

| Variable | Meaning |
| --- | --- |
| `${SERVER_IP}` | public IPv4 of the VPS |
| `${SSH_PORT}` | SSH port (the VPS may not use 22) |
| `${SSH_USER}` | SSH user (usually `root`; if not root, prefix remote commands with `sudo`) |
| `${SSH_KEY}` | private key path on the local machine (key auth; never store passwords in files) |

Define the helper once per session (LOCAL):

```bash
SSH="ssh -p ${SSH_PORT} -i ${SSH_KEY} -o StrictHostKeyChecking=accept-new ${SSH_USER}@${SERVER_IP}"
```

## Hard rules

- Never edit `/etc/ssh/*`, `authorized_keys`, the SSH port, or SSH firewall rules. Never close or restart sshd.
- Never write real IPs, passwords or keys into skill files or git. Keep them in `./singbox-work/secrets.env` (mode 600, gitignored).
- If the SSH host key changed (server reinstalled), tell the user; only after they confirm run `ssh-keygen -R "[${SERVER_IP}]:${SSH_PORT}"` **locally**.

## Steps

1. **[LOCAL] connectivity**
   ```bash
   $SSH 'echo connected; whoami'
   ```
   Check: prints `connected` and the expected user. If not, stop and report; do not try other credentials.

2. **[REMOTE via ssh] environment facts**
   ```bash
   $SSH 'cat /etc/os-release; uname -m; id -u; docker --version 2>&1; docker compose version 2>&1'
   ```
   Check: recorded deployment used **Debian 13 (Trixie), x86_64**. Other Debian/Ubuntu releases usually work; if architecture is not `x86_64`/`aarch64`, or the OS is not Debian/Ubuntu, stop and ask the user. Note whether Docker and the compose plugin already exist (stage 2 is skipped if both work).

3. **[REMOTE] listening ports - choose proxy ports**
   ```bash
   $SSH 'ss -lntup'
   ```
   Check: the SSH port `${SSH_PORT}` is listed (never reuse it). Defaults `${SS_PORT}=8388` (TCP+UDP) and `${VLESS_PORT}=8443` (TCP) must NOT already be listening. If taken (e.g. by a previous sing-box container, nginx on 8443), pick other free ports and record them in `secrets.env`; if an old `sing-box` container exists, ask the user whether to reuse/replace it (compare with `$SSH 'docker ps -a'`).

4. **[REMOTE] firewall state (read-only)**
   ```bash
   $SSH 'command -v ufw && ufw status verbose; command -v nft && nft list ruleset | head -50; command -v iptables && iptables -S | head -50'
   ```
   Check: note whether a host firewall is active (details handled in stage 5). A port being free in `ss` does not prove it is reachable from the Internet: the **cloud provider's security group / cloud firewall** is outside the server and must be checked by the user (stage 5).

5. **[REMOTE] outbound connectivity & DNS (read-only)**
   ```bash
   $SSH 'curl -4 -sS --max-time 10 https://api.ipify.org; echo; cat /etc/resolv.conf'
   ```
   Check: returned IP equals `${SERVER_IP}` (server egress = its own IP). Record `resolv.conf` nameservers (the recorded server used plain 8.8.8.8 / 1.1.1.1; this means server-side domain resolution is unencrypted plain DNS - a known and accepted risk, see `singbox-troubleshooting`).

6. **[LOCAL] create work dir**
   ```bash
   mkdir -p singbox-work && chmod 700 singbox-work
   # make sure singbox-work/ is in .gitignore of whatever repo you are in
   cp <skill>/../singbox-deploy-full/templates/inputs.env.example singbox-work/secrets.env && chmod 600 singbox-work/secrets.env
   ```
   Fill `SERVER_IP`, `SSH_PORT`, `SSH_USER`, `SSH_KEY` and any changed ports.

## Verification summary (all must pass before stage 2)

- [ ] SSH works with key auth, correct user
- [ ] OS/arch supported
- [ ] `${SS_PORT}` / `${VLESS_PORT}` free (or replaced by free ones, recorded)
- [ ] SSH port identified and left untouched
- [ ] `secrets.env` created locally with mode 600
