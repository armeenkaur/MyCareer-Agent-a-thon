#!/usr/bin/env bash
# Wire GoDaddy *.go-mmt.com cert IT sent + matching private key (must obtain separately).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERT_DIR="$ROOT/certs/go-mmt"
FULLCHAIN="$CERT_DIR/fullchain.pem"
KEY="${1:-$CERT_DIR/privkey.pem}"

if [[ ! -f "$FULLCHAIN" ]]; then
  mkdir -p "$CERT_DIR"
  ZIP="${HOME}/Downloads/go-mmt.com_pem"
  if [[ -f "$ZIP/f4c2f167959f8132.crt" ]]; then
    cat "$ZIP/f4c2f167959f8132.crt" "$ZIP/gd_bundle-g2.crt" > "$FULLCHAIN"
  else
    echo "Missing $FULLCHAIN — unpack IT zip first." >&2
    exit 1
  fi
fi

if [[ ! -f "$KEY" ]]; then
  echo "UTILIZED public cert → $FULLCHAIN" >&2
  echo "BLOCKED: no private key at $KEY" >&2
  echo "IT zip has ZERO private key blocks (openssl confirmed)." >&2
  echo "Drop matching *.go-mmt.com key as: $CERT_DIR/privkey.pem" >&2
  echo "Then re-run: $0" >&2
  exit 2
fi

# Key must match leaf cert
cert_mod=$(openssl x509 -in "$FULLCHAIN" -noout -modulus | openssl md5)
key_mod=$(openssl rsa -in "$KEY" -noout -modulus 2>/dev/null | openssl md5 || openssl pkey -in "$KEY" -noout -modulus | openssl md5)
if [[ "$cert_mod" != "$key_mod" ]]; then
  echo "Key does not match leaf cert (modulus mismatch)." >&2
  exit 3
fi

echo "OK cert+key match."
echo "Add to VM .env:"
echo "  SSL_CERTFILE=$FULLCHAIN"
echo "  SSL_KEYFILE=$KEY"
echo "Open (cert SAN is *.go-mmt.com — NOT .mmt.com):"
echo "  https://MyCareerCompass.go-mmt.com:5050/app/login"
