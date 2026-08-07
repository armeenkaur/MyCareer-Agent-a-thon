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
  -x '.tokensaver/*'
ls -lh "$OUT"
echo
echo "SCP to VM, then on VM:"
echo "  unzip mycareer-deploy.zip -d mycareer && cd mycareer"
echo "  docker build -t mycareer-compass:latest ."
echo "  docker compose -f docker-compose.deploy.yml --env-file .env up -d"
echo "  # first time: copy .env.example → .env and fill keys"
