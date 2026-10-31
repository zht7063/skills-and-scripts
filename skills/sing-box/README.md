# sing-box deployment skills

Skills for a **local agent** (Claude Code, Codex, ...) that deploys a [sing-box](https://sing-box.sagernet.org/) proxy node with Docker on a remote VPS over SSH - Shadowsocks 2022 + VLESS-REALITY - verifies it with a local mihomo / sing-box client, and produces a Clash (mihomo) profile. Derived from a recorded, working deployment (Debian 13, Docker Compose, sing-box 1.14.x).

All skills use placeholders (`${SERVER_IP}`, `${SS_PASSWORD}`, `${VLESS_UUID}`, `${REALITY_PRIVATE_KEY}`, `${REALITY_PUBLIC_KEY}`, `${SHORT_ID}`, ...). **No real secrets, IPs or passwords belong in this repository.** Generated files live in a local gitignored `singbox-work/` directory.

| Skill | Purpose |
| --- | --- |
| [`singbox-deploy-full`](singbox-deploy-full/SKILL.md) | Orchestrator: inputs, global rules, runs stages 1-8 in order, ends with `clash.yaml` |
| [`singbox-server-prep`](singbox-server-prep/SKILL.md) | 1 - read-only checks of OS, arch, ports, firewall over SSH |
| [`singbox-docker-install`](singbox-docker-install/SKILL.md) | 2 - install/verify Docker Engine + Compose, pull sing-box image |
| [`singbox-config-generate`](singbox-config-generate/SKILL.md) | 3 - generate SS key, UUID, REALITY keypair, short id; render server `config.json` (templates + scripts) |
| [`singbox-compose-run`](singbox-compose-run/SKILL.md) | 4 - upload, `sing-box check`, `docker compose up`, listener/log checks (`compose.yaml` template) |
| [`singbox-firewall-ports`](singbox-firewall-ports/SKILL.md) | 5 - host firewall (read-only by default), cloud security group, reachability from local |
| [`singbox-clash-config`](singbox-clash-config/SKILL.md) | 6 - render + validate the Clash/mihomo YAML (template + validator) |
| [`singbox-local-verify`](singbox-local-verify/SKILL.md) | 7 - local client tests: egress IP, 204, UDP/DNS/IPv6/WebRTC notes, perf baseline |
| [`singbox-maintenance`](singbox-maintenance/SKILL.md) | 8 - backup, log rotation, update + rollback tag, credential rotation |
| [`singbox-troubleshooting`](singbox-troubleshooting/SKILL.md) | symptom -> cause -> action -> verify reference |

Design rules shared by all skills: remote commands are marked `[REMOTE]` (via `ssh`), local ones `[LOCAL]`; configs are rendered from templates, never hand-written; the server's SSH configuration is never modified; every stage ends with a verification checklist.

Install a skill folder into your agent's skills directory (e.g. copy `skills/sing-box/<skill>/` to `~/.claude/skills/`). Because the stages reference sibling skills' templates and scripts, install the whole `sing-box/` set together.
