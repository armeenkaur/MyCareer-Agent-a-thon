#!/usr/bin/env bash
# Enable HTTP-only nginx proxy (no TLS). Run as root.
set -euo pipefail
CONF_SRC="${1:-/home/mmtadmin/https-bundle/nginx-http-proxy.conf}"
test -f "$CONF_SRC"
install -m 644 "$CONF_SRC" /etc/nginx/sites-available/mycareercompass
ln -sfn /etc/nginx/sites-available/mycareercompass /etc/nginx/sites-enabled/mycareercompass
rm -f /etc/nginx/sites-enabled/default
ss -lntp | grep -q ':5050' || echo "WARN: start app on :5050 first"
nginx -t
systemctl reload nginx
echo "OK — http://mycareercompass.mmt.com/app/login"
