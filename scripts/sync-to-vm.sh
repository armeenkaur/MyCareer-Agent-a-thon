#!/usr/bin/env bash
# Sync local MyCareer code → VM and restart python -m skillsync_ai.app
# (no Docker — matches how the VM runs the app).
# Usage:
#   ./scripts/sync-to-vm.sh
#   ./scripts/sync-to-vm.sh mmtadmin@172.16.229.10 /home/mmtadmin/mycareer
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${1:-mmtadmin@172.16.229.10}"
REMOTE="${2:-/home/mmtadmin/mycareer}"

cd "$ROOT"

echo "→ rsync code to ${HOST}:${REMOTE}"
# No --delete: keep VM-only files (.env, logs, uploads, db, custom data).
# Skip deploy/: often root-owned from nginx install (not needed for app runtime).
rsync -avz \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude 'venv/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude '.env' \
  --exclude 'logs/' \
  --exclude 'uploads/' \
  --exclude '*.db' \
  --exclude 'mycareer-deploy/' \
  --exclude 'mycareer-deploy.zip' \
  --exclude 'mycareer-compass.tar' \
  --exclude 'offline-deps.zip' \
  --exclude 'offline-wheels/' \
  --exclude 'certs/' \
  --exclude 'certs-https.zip' \
  --exclude 'mycareer-https-bundle.zip' \
  --exclude 'starmmt-tls.zip' \
  --exclude '.cursor/' \
  --exclude '.tokensaver/' \
  --exclude 'node_modules/' \
  \
  ./skillsync_ai \
  ./stitch_mycareer_compass \
  ./tests \
  ./data \
  ./scripts \
  ./requirements.txt \
  ./Dockerfile \
  ./docker-compose.yml \
  ./docker-compose.deploy.yml \
  ./API.md \
  ./README.md \
  ./render.yaml \
  "${HOST}:${REMOTE}/"

echo
echo "→ restart python app on VM (no Docker)"
ssh "$HOST" bash -s <<EOF
set -euo pipefail
cd "${REMOTE}"
mkdir -p logs

echo "Restarting python -m skillsync_ai.app..."
pkill -f 'skillsync_ai.app' 2>/dev/null || true
sleep 1
if [[ -x .venv/bin/python ]]; then
  nohup .venv/bin/python -m skillsync_ai.app >> logs/skillsync.log 2>&1 &
else
  nohup python3 -m skillsync_ai.app >> logs/skillsync.log 2>&1 &
fi
sleep 2
pgrep -af 'skillsync_ai.app' || echo "(process not listed yet — check logs/skillsync.log)"

echo "Health:"
curl -fsS -m 5 http://127.0.0.1:5050/api/health 2>/dev/null \
  || curl -fsS -k -m 5 https://127.0.0.1:443/api/health 2>/dev/null \
  || curl -fsS -m 5 http://127.0.0.1/api/health 2>/dev/null \
  || echo "(open /api/health in browser if curl missed)"
echo "Tail log:"
tail -n 15 logs/skillsync.log 2>/dev/null || true
EOF

echo
echo "Done. Hard-refresh browser (cache-bust runtime.js)."
