#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_TAG="${1:-malvin-harbor:py313}"

docker build \
  --file "${ROOT_DIR}/docker/Dockerfile.harbor-malvin" \
  --tag "${IMAGE_TAG}" \
  "${ROOT_DIR}"

printf 'Built image: %s\n' "${IMAGE_TAG}"
