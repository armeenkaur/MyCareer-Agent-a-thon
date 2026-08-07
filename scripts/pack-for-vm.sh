#!/usr/bin/env bash
# Fallback when Mac Docker Desktop is broken:
# pack source for SCP → build image ON the VM (still no git).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/mycareer-deploy.zip}"
cd "$ROOT"
rm -f "$OUT"
zip -r "$OUT" . \
  -x '.git/*' \
  -x '.venv/*' \
  -x 'venv/*' \
  -x '__pycache__/*' \
  -x '*/__pycache__/*' \
  -x '.env' \
  -x 'logs/*' \
  -x 'uploads/*' \
  -x '*.db' \
  -x 'mycareer-compass.tar' \
  -x '.cursor/*' \
  -x '.tokensaver/*' \
  -x 'mycareer-deploy/*' \
  -x 'mycareer-deploy.zip' \
  -x 'offline-deps.zip' \
  -x 'offline-wheels/*' \
  -x 'certs/*' \
  -x 'certs-https.zip' \
  -x 'mycareer-https-bundle.zip' \
  -x 'starmmt-tls.zip'
ls -lh "$OUT"
echo
echo "SCP to VM, then on VM:"
echo "  # keep existing .env — unzip over mycareer, do not overwrite .env"
echo "  unzip -o mycareer-deploy.zip -d mycareer && cd mycareer"
echo "  docker build -t mycareer-compass:latest ."
echo "  docker compose -f docker-compose.deploy.yml --env-file .env up -d"
