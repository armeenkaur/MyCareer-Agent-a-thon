#!/usr/bin/env bash
# Run ON VM as root after certs installed to /etc/ssl/...
set -euo pipefail

APP=/home/mmtadmin/mycareer
CONF_SRC="${1:-$APP/deploy/nginx-https.conf}"

test -f /etc/ssl/certs/mycareercompass.fullchain.pem
test -f /etc/ssl/private/mycareercompass.key

install -m 644 "$CONF_SRC" /etc/nginx/sites-available/mycareercompass
ln -sfn /etc/nginx/sites-available/mycareercompass /etc/nginx/sites-enabled/mycareercompass
rm -f /etc/nginx/sites-enabled/default

if [[ -f "$APP/.env" ]]; then
  sed -i.bak -E 's/^SSL_CERTFILE=/# SSL_CERTFILE=/' "$APP/.env" || true
  sed -i.bak -E 's/^SSL_KEYFILE=/# SSL_KEYFILE=/' "$APP/.env" || true
fi

ss -lntp | grep -q ':80' || echo "WARN: start app on :80 first"

nginx -t
systemctl reload nginx
echo "OK — https://mycareercompass.mmt.com/app/login"
