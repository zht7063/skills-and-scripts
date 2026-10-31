{
  "log": { "level": "info" },
  "inbounds": [
    {
      "type": "mixed",
      "tag": "mixed-in",
      "listen": "127.0.0.1",
      "listen_port": ${LOCAL_MIXED_PORT}
    }
  ],
  "outbounds": [
    {
      "type": "shadowsocks",
      "tag": "ss-out",
      "server": "${SERVER_IP}",
      "server_port": ${SS_PORT},
      "method": "${SS_METHOD}",
      "password": "${SS_PASSWORD}"
    },
    {
      "type": "vless",
      "tag": "vless-out",
      "server": "${SERVER_IP}",
      "server_port": ${VLESS_PORT},
      "uuid": "${VLESS_UUID}",
      "flow": "${VLESS_FLOW}",
      "packet_encoding": "xudp",
      "tls": {
        "enabled": true,
        "server_name": "${REALITY_SNI}",
        "utls": { "enabled": true, "fingerprint": "chrome" },
        "reality": {
          "enabled": true,
          "public_key": "${REALITY_PUBLIC_KEY}",
          "short_id": "${SHORT_ID}"
        }
      }
    },
    { "type": "direct", "tag": "direct" }
  ],
  "route": {
    "final": "${TEST_OUTBOUND}"
  }
}
