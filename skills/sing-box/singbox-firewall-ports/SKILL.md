---
name: singbox-firewall-ports
description: Use after the sing-box container is running to make sure the proxy ports (SS TCP+UDP, VLESS-REALITY TCP) are reachable from the Internet - check the host firewall over SSH without touching SSH rules, guide the user through the cloud security group, and test reachability from the local machine. Stage 5 of the sing-box deployment skill set.
---

# sing-box stage 5 - firewall and port reachability

**Local agent; remote read via ssh; reachability tested locally.** Inputs: `SERVER_IP SSH_PORT SSH_USER SSH_KEY SS_PORT (8388) VLESS_PORT (8443)`.

Ports that must be open inbound:

| Port | Proto | Purpose |
| --- | --- | --- |
| `${SS_PORT}` | **TCP and UDP** | Shadowsocks 2022 |
| `${VLESS_PORT}` | TCP | VLESS + REALITY |
| `${SSH_PORT}` | TCP | SSH - **already working, must be preserved, never modified by you** |

`ss -lntup` showing a listener does not prove the port is reachable: the cloud provider's **security group / cloud firewall** and the host firewall are separate layers.

## Rules

- You may **read** firewall state. You may add allow rules for `${SS_PORT}` and `${VLESS_PORT}` **only if a host firewall is active and blocking them, and only after telling the user the exact commands**. Never add/remove/alter rules for `${SSH_PORT}`, never enable a default-deny policy, never run `ufw enable`/`ufw reset`/`iptables -F` (risk of locking out SSH). Never touch sshd config.
- The cloud security group cannot be changed from here: ask the user to open the ports in the provider console.

## Steps

1. **[REMOTE] inspect host firewall**
   ```bash
   $SSH 'systemctl is-active ufw 2>/dev/null; ufw status verbose 2>/dev/null; nft list ruleset 2>/dev/null | head -60; iptables -S 2>/dev/null | head -40'
   ```
   Interpret:
   - everything inactive/empty or policy ACCEPT -> nothing to do on the host.
   - active ufw: needed rules (only if missing, after informing the user; SSH port is already allowed, do not touch):
     ```bash
     $SSH "ufw allow ${SS_PORT}/tcp && ufw allow ${SS_PORT}/udp && ufw allow ${VLESS_PORT}/tcp && ufw status"
     ```
   - nftables/iptables with a default DROP: report the situation to the user and propose equivalent accept rules; do not apply without confirmation.

2. **Cloud security group - ask the user (cannot be automated)**
   Tell the user to ensure inbound allow for `${SS_PORT}/tcp`, `${SS_PORT}/udp`, `${VLESS_PORT}/tcp` (source 0.0.0.0/0, or their own client IPs) and that the SSH port rule stays. Wait for confirmation.

3. **[LOCAL] TCP reachability**
   ```bash
   nc -zv -w 5 ${SERVER_IP} ${SS_PORT}
   nc -zv -w 5 ${SERVER_IP} ${VLESS_PORT}
   ```
   (Fallback without nc: `python3 -c "import socket;socket.create_connection(('${SERVER_IP}',${SS_PORT}),5);print('open')"`.)
   Expected: both `succeeded/open`.

4. **UDP reachability (SS)**
   UDP cannot be proven by a connect test. Use the end-to-end test in stage 7 (client with `udp: true`) and, if it is unclear, the server-side capture (read-only, [REMOTE]; ask before installing tcpdump):
   ```bash
   $SSH 'apt-get install -y tcpdump'    # only if missing and user agrees
   # in a second step, while the local client generates traffic (stage 7):
   $SSH "timeout 20 tcpdump -ni any -c 10 -q 'udp dst port ${SS_PORT}'"
   ```
   Expected: packets from the local machine's public IP to `${SERVER_IP}:${SS_PORT}` with `0 packets dropped by kernel`. The `any` device message about promiscuous mode is normal. Bidirectional traffic can be confirmed with `tcpdump -ni <eth-device> -c 20 -q 'udp port ${SS_PORT} and host <client-public-ip>'` (look for both directions). Packet capture shows network reachability only; it does not prove application-layer success.

## Verification summary

- [ ] host firewall state recorded; SSH rule untouched
- [ ] user confirmed cloud security group allows `${SS_PORT}` TCP+UDP and `${VLESS_PORT}` TCP
- [ ] local `nc` to both TCP ports succeeds
- [ ] UDP confirmed later in `singbox-local-verify` (or by capture)
