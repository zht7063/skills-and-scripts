# Mihomo (Clash Meta) profile for the sing-box server ${SERVER_IP}
# Node: My-sing-box (Shadowsocks 2022, TCP+UDP ${SS_PORT}). The VLESS-REALITY node is added later by singbox-reality-perf-troubleshoot (templates/clash.ss-vless.yaml.tpl).
# Contains secrets -> keep local, never commit.
mixed-port: ${LOCAL_MIXED_PORT}
allow-lan: false
mode: rule
log-level: info
ipv6: false
# Used by the local CLI test. Clash Verge manages its own controller and ignores/overrides this.
external-controller: 127.0.0.1:${LOCAL_CONTROLLER_PORT}

dns:
  enable: true
  ipv6: false
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  nameserver:
    - 'https://1.1.1.1/dns-query#PROXY'
  proxy-server-nameserver:
    - 'https://1.1.1.1/dns-query'

# Optional (Clash Verge normally controls TUN from its GUI; enable here only for a bare mihomo client):
# tun:
#   enable: true
#   stack: mixed
#   auto-route: true
#   dns-hijack:
#     - any:53

proxies:
  - name: My-sing-box
    type: ss
    server: ${SERVER_IP}
    port: ${SS_PORT}
    cipher: ${SS_METHOD}
    password: "${SS_PASSWORD}"
    udp: true

proxy-groups:
  - name: PROXY
    type: select
    proxies:
      - My-sing-box
      - DIRECT

rules:
  - IP-CIDR,127.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
  - IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
  - IP-CIDR,169.254.0.0/16,DIRECT,no-resolve
  - MATCH,PROXY
