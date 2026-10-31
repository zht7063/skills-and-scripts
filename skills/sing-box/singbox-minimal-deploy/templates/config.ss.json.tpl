{
  "log": { "level": "${LOG_LEVEL}" },
  "inbounds": [
    {
      "type": "shadowsocks",
      "tag": "ss-in",
      "listen": "0.0.0.0",
      "listen_port": ${SS_PORT},
      "method": "${SS_METHOD}",
      "password": "${SS_PASSWORD}"
    }
  ],
  "outbounds": [
    { "type": "direct", "tag": "direct" }
  ]
}
