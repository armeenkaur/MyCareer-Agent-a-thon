#!/usr/bin/env bash
# Generate self-signed cert WITH IP SAN (Chrome requires this).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IP="${1:-172.16.229.10}"
DIR="$ROOT/certs"
mkdir -p "$DIR"
CNF="$DIR/openssl-lan.cnf"
# Rewrite CNF for this IP
cat > "$CNF" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
CN = ${IP}
O = MyCareer Compass
C = IN

[v3_req]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
IP.1 = ${IP}
DNS.1 = localhost
DNS.2 = GL-DEV-229-10
EOF

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$DIR/key.pem" \
  -out "$DIR/cert.pem" \
  -days 825 \
  -config "$CNF" \
  -extensions v3_req

echo "Verify SAN (must list IP):"
openssl x509 -in "$DIR/cert.pem" -noout -text | grep -A3 "Subject Alternative Name" || true
echo
echo "Files: $DIR/cert.pem $DIR/key.pem"
