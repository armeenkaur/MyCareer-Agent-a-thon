#!/usr/bin/env bash
# Pack HTTPS/nginx deploy files → zip. SCP zip to VM home (avoids deploy/ perms).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/mycareer-https-bundle.zip}"
cd "$ROOT"
rm -f "$OUT"
zip -j "$OUT" \
  deploy/nginx-https.conf \
  deploy/nginx-http-proxy.conf \
  scripts/vm-install-certs-system.sh \
  scripts/vm-enable-nginx-https.sh \
  scripts/vm-enable-nginx-http.sh
# include public chain if present (never pack private key)
if [[ -f certs/go-mmt/fullchain.pem ]]; then
  zip -j "$OUT" certs/go-mmt/fullchain.pem
fi
ls -lh "$OUT"
echo
echo "Mac:"
echo "  scp $OUT mmtadmin@172.16.229.10:/home/mmtadmin/"
echo "VM: see scripts/VM-HTTPS-STEPS.txt (printed below)"
cat <<'EOF'

# === ON VM ===
cd /home/mmtadmin
unzip -o mycareer-https-bundle.zip -d https-bundle
cd https-bundle
chmod +x vm-*.sh

# A) App must listen HTTP :80 (no SSL_* in mycareer/.env)
#    nginx does NOT bind :80 — app owns it; nginx only :443
ss -lntp | grep ':80'

# B) Fix "Welcome to nginx" NOW (HTTP proxy):
sudo bash -c 'install -m 644 nginx-http-proxy.conf /etc/nginx/sites-available/mycareercompass
ln -sfn /etc/nginx/sites-available/mycareercompass /etc/nginx/sites-enabled/mycareercompass
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx'
# Test: http://mycareercompass.mmt.com/app/login

# C) HTTPS when both files exist under certs/go-mmt/:
#    fullchain.pem + privkey.pem
sudo bash vm-install-certs-system.sh \
  /home/mmtadmin/mycareer/certs/go-mmt/fullchain.pem \
  /home/mmtadmin/mycareer/certs/go-mmt/privkey.pem
sudo bash vm-enable-nginx-https.sh \
  /home/mmtadmin/https-bundle/nginx-https.conf
# Test: https://mycareercompass.mmt.com/app/login

EOF
