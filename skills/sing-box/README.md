# sing-box deployment skills

Skills for a **local agent** (Claude Code, Codex, ...) that deploys a [sing-box](https://sing-box.sagernet.org/) proxy node with Docker on a remote VPS over SSH - Shadowsocks 2022 + VLESS-REALITY - verifies it with a local mihomo / sing-box client, and produces a Clash (mihomo) profile. Derived from a recorded, working deployment (Debian 13, Docker Compose, sing-box 1.14.x).

All skills use placeholders (`${SERVER_IP}`, `${SS_PASSWORD}`, `${VLESS_UUID}`, `${REALITY_PRIVATE_KEY}`, `${REALITY_PUBLIC_KEY}`, `${SHORT_ID}`, ...). **No real secrets, IPs or passwords belong in this repository.** Generated files live in a local gitignored `singbox-work/` directory.

Five skills, built incrementally: **`singbox-minimal-deploy` is the base** - the UDP, DNS/routing and VLESS-REALITY skills each check that it is deployed and then only add their own changes on top (they never repeat deployment steps). `singbox-deploy-full` chains them in order.

| # | Skill | Purpose |
| --- | --- | --- |
| 1 | [`singbox-minimal-deploy`](singbox-minimal-deploy/SKILL.md) | Base: server prep (read-only), Docker + Compose, Shadowsocks 2022 config (`config.ss.json.tpl`), compose up + `sing-box check`, firewall/ports, basic Clash profile (`clash.ss.yaml.tpl`), local verification; image rule (`latest` default, 1.14.4 known-stable + rollback). Holds the shared scripts (`render.py`, `validate_clash.py`, `run-local-client.sh`, `egress-check.sh`, `gen-secrets.sh`) and `inputs.env.example` |
| 2 | [`singbox-udp`](singbox-udp/SKILL.md) | UDP listener / firewall / client `udp: true`, tcpdump evidence, WebRTC check (has TODO gaps) |
| 3 | [`singbox-dns-routing`](singbox-dns-routing/SKILL.md) | DNS and routing (分流): Fake-IP/DoH profile behaviour, DNS/IPv6 checks, DIRECT rules for LAN/overlay, Clash DNS conflicts (has TODO gaps: server DoH/DoT, geo rules) |
| 4 | [`singbox-reality-perf-troubleshoot`](singbox-reality-perf-troubleshoot/SKILL.md) | Adds VLESS-REALITY (REALITY secrets, SNI default/fallback, `VLESS_FLOW`, two-node Clash profile), performance baseline, existing-server read-only path, `references/troubleshooting.md` and `references/maintenance.md` (backup, update/rollback, key rotation) |
| 5 | [`singbox-deploy-full`](singbox-deploy-full/SKILL.md) | Orchestrator: inputs, global rules, runs skills 1-4 in order, final report |

Design rules shared by all skills: remote commands are marked `[REMOTE]` (via `ssh`), local ones `[LOCAL]`; **all sing-box files on the server live in `/opt/sing-box/`** (`REMOTE_DIR`); configs are rendered from templates, never hand-written; the server's SSH configuration is never modified; every step ends with a verification checklist.

Install a skill folder into your agent's skills directory (e.g. copy `skills/sing-box/<skill>/` to `~/.claude/skills/`). Skills 2-5 use the shared scripts/templates of `singbox-minimal-deploy` and reference each other by path (`$SB_DIR` = the directory holding the skill folders), so install the whole `sing-box/` set together.
