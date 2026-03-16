#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LIST_FILES=0
if [[ "${1:-}" == "--list-files" ]]; then
  LIST_FILES=1
fi

OUTPUT="$(
  REPO_ROOT="$ROOT_DIR" LIST_FILES="$LIST_FILES" python - <<'PY'
import os
from pathlib import Path

from malvin.harbor_bundle import create_harbor_bundle

repo_root = Path(os.environ["REPO_ROOT"])
list_files = os.environ["LIST_FILES"] == "1"
result = create_harbor_bundle(repo_root=repo_root)

print(f"BUNDLE_PATH={result.bundle_path}")
print(f"METADATA_PATH={result.metadata_path}")
print(f"BUNDLE_SIZE_BYTES={result.bundle_path.stat().st_size}")
if list_files:
    for rel_path in result.metadata.included_files:
        print(f"FILE={rel_path}")
PY
)"

BUNDLE_PATH="$(printf '%s\n' "$OUTPUT" | sed -n 's/^BUNDLE_PATH=//p')"
METADATA_PATH="$(printf '%s\n' "$OUTPUT" | sed -n 's/^METADATA_PATH=//p')"
BUNDLE_SIZE_BYTES="$(printf '%s\n' "$OUTPUT" | sed -n 's/^BUNDLE_SIZE_BYTES=//p')"

printf 'Bundle: %s\n' "${BUNDLE_PATH}"
printf 'Metadata: %s\n' "${METADATA_PATH}"
printf 'Size (bytes): %s\n' "${BUNDLE_SIZE_BYTES}"

if [[ "$LIST_FILES" -eq 1 ]]; then
  printf 'Included files:\n'
  printf '%s\n' "$OUTPUT" | sed -n 's/^FILE=//p'
fi
