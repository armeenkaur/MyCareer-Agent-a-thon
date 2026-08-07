#!/usr/bin/env bash
# Run ON VM as root.
# Copies certs from app tree → system locations nginx expects.
set -euo pipefail

SRC_CHAIN="${1:-/home/mmtadmin/mycareer/certs/go-mmt/fullchain.pem}"
SRC_KEY="${2:-/home/mmtadmin/mycareer/certs/go-mmt/privkey.pem}"

DST_CHAIN=/etc/ssl/certs/mycareercompass.fullchain.pem
DST_KEY=/etc/ssl/private/mycareercompass.key

if [[ ! -f "$SRC_CHAIN" ]]; then
  echo "ERROR: missing chain: $SRC_CHAIN" >&2
  exit 1
fi
if [[ ! -f "$SRC_KEY" ]]; then
  echo "ERROR: missing key file: $SRC_KEY" >&2
  echo "Place it there, then re-run." >&2
  exit 1
fi

install -m 644 "$SRC_CHAIN" "$DST_CHAIN"
install -m 600 "$SRC_KEY" "$DST_KEY"
chown root:root "$DST_CHAIN" "$DST_KEY"

if getent group ssl-cert >/dev/null; then
  chown root:ssl-cert "$DST_KEY"
  chmod 640 "$DST_KEY"
fi

echo "Installed:"
ls -la "$DST_CHAIN" "$DST_KEY"
