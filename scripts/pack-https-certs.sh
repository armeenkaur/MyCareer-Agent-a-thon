#!/usr/bin/env bash
# Pack cert files for SCP to VM + Mac Keychain trust helper text.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
./scripts/make-self-signed-cert.sh "${1:-172.16.229.10}"
zip -j certs-https.zip certs/cert.pem certs/key.pem certs/openssl-lan.cnf
ls -lh certs-https.zip certs/cert.pem
echo
echo "SCP to VM:"
echo "  scp certs-https.zip mmtadmin@172.16.229.10:~/"
echo "On VM: unzip and set SSL_* in .env, restart app"
echo
echo "On Mac — trust cert so Chrome Proceed works:"
echo "  open certs/cert.pem"
echo "  Keychain Access → login → find cert → Trust → Always Trust"
