#!/usr/bin/env bash
# Build MyCareer Compass image + export tar for VM deploy (no git on server).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="/Applications/Docker.app/Contents/Resources/bin:${PATH}"

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon not running. Open Docker Desktop, wait until it is green, then re-run:"
  echo "  ./scripts/build-docker-image.sh"
  exit 1
fi

TAG="${1:-mycareer-compass:latest}"
TAR="${2:-mycareer-compass.tar}"

echo "Building ${TAG} ..."
docker build -t "${TAG}" .

echo "Saving ${TAR} ..."
docker save "${TAG}" -o "${TAR}"
ls -lh "${TAR}"
echo "Done. SCP to VM:"
echo "  scp ${TAR} docker-compose.deploy.yml user@172.16.229.10:~/"
echo "On VM:"
echo "  docker load -i mycareer-compass.tar"
echo "  docker compose -f docker-compose.deploy.yml --env-file .env up -d"
