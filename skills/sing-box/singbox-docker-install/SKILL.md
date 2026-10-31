---
name: singbox-docker-install
description: Use when the remote server has no working Docker Engine / Docker Compose plugin and a local agent must install it over SSH before deploying sing-box. Skip if `docker compose version` already works. Stage 2 of the sing-box deployment skill set.
---

# sing-box stage 2 - Docker Engine + Compose on the remote server

**Local agent, remote execution via ssh.** Requires the inputs and `$SSH` helper from `singbox-server-prep` (`${SERVER_IP}`, `${SSH_PORT}`, `${SSH_USER}`, `${SSH_KEY}`). Follow the steps strictly; do not install extra packages or change SSH/sshd settings.

```bash
SSH="ssh -p ${SSH_PORT} -i ${SSH_KEY} -o StrictHostKeyChecking=accept-new ${SSH_USER}@${SERVER_IP}"
```

## 0. Skip check

**[REMOTE]**
```bash
$SSH 'docker --version && docker compose version'
```
If both print versions, mark this stage done and go to stage 3.

## 1. Install (Debian/Ubuntu, official apt repository)

The recorded deployment only verified that Docker + Compose were present on Debian 13; the install commands below are the standard upstream method (docs.docker.com/engine/install/debian). Show the user the commands and confirm before running them if the server is not a fresh one.

**[REMOTE]** (as root; for another user prefix with `sudo`)
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

## 2. Verification

**[REMOTE]**
```bash
$SSH 'docker --version; docker compose version; systemctl is-enabled docker; systemctl is-active docker'
$SSH 'docker run --rm hello-world | head -5'
$SSH 'docker pull ghcr.io/sagernet/sing-box:latest >/dev/null && docker run --rm ghcr.io/sagernet/sing-box:latest version'
```
Checks:
- [ ] Docker and Compose versions print
- [ ] `is-enabled` = `enabled`, `is-active` = `active`
- [ ] `hello-world` runs
- [ ] the sing-box image pulls and prints a version (the recorded run used **sing-box 1.14.4**, `linux/amd64`). If `ghcr.io` is unreachable from the server, stop and report to the user (mirror/registry choice is their decision).

Record the printed sing-box version in `./singbox-work/NOTES.md` (no secrets).
