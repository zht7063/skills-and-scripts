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
    { "type": "direct", "tag": "direct" }
  ],
  "route": {
    "final": "${TEST_OUTBOUND}"
  }
}
