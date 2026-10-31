# Mihomo (Clash Meta) profile for the sing-box server ${SERVER_IP}
# Nodes: My-sing-box (Shadowsocks 2022, TCP+UDP ${SS_PORT}), My-VLESS-Reality (VLESS+REALITY, TCP ${VLESS_PORT})
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

  - name: My-VLESS-Reality
    type: vless
    server: ${SERVER_IP}
    port: ${VLESS_PORT}
    uuid: ${VLESS_UUID}
    network: tcp
    tls: true
    udp: true
    flow: "${VLESS_FLOW}"
    packet-encoding: xudp
    servername: ${REALITY_SNI}
    client-fingerprint: chrome
    reality-opts:
      public-key: ${REALITY_PUBLIC_KEY}
      short-id: ${SHORT_ID}

proxy-groups:
  - name: PROXY
    type: select
    proxies:
      - My-sing-box
      - My-VLESS-Reality
      - DIRECT

rules:
  - IP-CIDR,127.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
  - IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
  - IP-CIDR,169.254.0.0/16,DIRECT,no-resolve
  - MATCH,PROXY
