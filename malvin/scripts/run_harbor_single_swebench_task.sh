#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Run one swebench-verified task with MalvinHarborAgent.

Usage:
  scripts/run_harbor_single_swebench_task.sh [TASK_NAME]

Examples:
  scripts/run_harbor_single_swebench_task.sh
  scripts/run_harbor_single_swebench_task.sh sympy__sympy-16792

Environment overrides:
  HARBOR_BIN                  Harbor executable (default: harbor)
  HARBOR_MODEL                Model in provider/name format (default: anthropic/opus-4.5)
  HARBOR_DATASET              Dataset identifier (default: swebench-verified@1.0)
  HARBOR_TASK                 Task name (default: sympy__sympy-11618)
  HARBOR_AGENT_TIMEOUT_MULT   Agent timeout multiplier (default: 20)
  HARBOR_N_ATTEMPTS           Attempts per task (default: 1)
  HARBOR_N_CONCURRENT         Number of concurrent trials (default: 1)
  HARBOR_JOB_NAME             Explicit job name (optional)

Required environment:
  CURSOR_API_KEY
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

HARBOR_BIN="${HARBOR_BIN:-harbor}"
HARBOR_MODEL="${HARBOR_MODEL:-anthropic/opus-4.5}"
HARBOR_DATASET="${HARBOR_DATASET:-swebench-verified@1.0}"
HARBOR_TASK="${HARBOR_TASK:-${1:-sympy__sympy-11618}}"
HARBOR_AGENT_TIMEOUT_MULT="${HARBOR_AGENT_TIMEOUT_MULT:-20}"
HARBOR_N_ATTEMPTS="${HARBOR_N_ATTEMPTS:-1}"
HARBOR_N_CONCURRENT="${HARBOR_N_CONCURRENT:-1}"

if [[ -z "${CURSOR_API_KEY:-}" ]]; then
  echo "CURSOR_API_KEY is required." >&2
  exit 1
fi

if ! command -v "${HARBOR_BIN}" >/dev/null 2>&1; then
  echo "Harbor executable not found: ${HARBOR_BIN}" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required but not found in PATH." >&2
  exit 1
fi

SAFE_TASK="${HARBOR_TASK//[^a-zA-Z0-9._-]/-}"
JOB_NAME="${HARBOR_JOB_NAME:-malvin-${SAFE_TASK}-$(date +%Y%m%d-%H%M%S)}"

echo "Running Harbor single-task benchmark"
echo "  job:      ${JOB_NAME}"
echo "  dataset:  ${HARBOR_DATASET}"
echo "  task:     ${HARBOR_TASK}"
echo "  model:    ${HARBOR_MODEL}"
echo "  repo:     ${ROOT_DIR}"
echo

"${HARBOR_BIN}" run \
  --job-name "${JOB_NAME}" \
  --agent-import-path malvin.harbor_agent:MalvinHarborAgent \
  --model "${HARBOR_MODEL}" \
  --dataset "${HARBOR_DATASET}" \
  --task-name "${HARBOR_TASK}" \
  --n-tasks 1 \
  --agent-timeout-multiplier "${HARBOR_AGENT_TIMEOUT_MULT}" \
  --ak "repo_root=${ROOT_DIR}" \
  --ae "CURSOR_API_KEY=${CURSOR_API_KEY}" \
  --n-concurrent "${HARBOR_N_CONCURRENT}" \
  --n-attempts "${HARBOR_N_ATTEMPTS}"
