#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v python >/dev/null 2>&1; then
  echo "python is required but was not found in PATH" >&2
  exit 1
fi
if ! command -v harbor >/dev/null 2>&1; then
  echo "harbor is required but was not found in PATH" >&2
  exit 1
fi

if [[ $# -ne 0 ]]; then
  echo "This script takes no arguments." >&2
  echo "Usage: scripts/run_matched_harbor_swebench.sh" >&2
  exit 2
fi

if [[ -z "${CURSOR_API_KEY:-}" ]]; then
  echo "CURSOR_API_KEY is required." >&2
  exit 1
fi

# Fixed benchmark settings: exactly what was requested.
MODEL="composer-1.5"
DATASET_NAME="swebench-verified"
DATASET_VERSION="1.0"
N_TASKS="100"
SEED="20260315"
JOBS_DIR="jobs"
JOB_PREFIX="swebench-verified-composer15-100"
REGISTRY_URL="https://raw.githubusercontent.com/laude-institute/harbor/main/registry.json"
RUN_DIR="${ROOT_DIR}/${JOBS_DIR}/${JOB_PREFIX}"
TASK_LIST_PATH="${RUN_DIR}/task_names.json"
CURSOR_CONFIG_PATH="${RUN_DIR}/cursor_cli_config.json"
MALVIN_CONFIG_PATH="${RUN_DIR}/malvin_config.json"
REPO_ROOT="${ROOT_DIR}"

AGENT_ENV_JSON="$(python - <<'PY'
import json
import os
print(json.dumps({"CURSOR_API_KEY": os.environ["CURSOR_API_KEY"]}))
PY
)"

echo "Running fixed matched Harbor workflow..."
echo "  dataset: ${DATASET_NAME} (${DATASET_VERSION})"
echo "  tasks: ${N_TASKS} (seed ${SEED})"
echo "  model: ${MODEL}"
echo "  agents: cursor-cli, malvin"

RUN_DIR="${RUN_DIR}" \
TASK_LIST_PATH="${TASK_LIST_PATH}" \
CURSOR_CONFIG_PATH="${CURSOR_CONFIG_PATH}" \
MALVIN_CONFIG_PATH="${MALVIN_CONFIG_PATH}" \
REGISTRY_URL="${REGISTRY_URL}" \
DATASET_NAME="${DATASET_NAME}" \
DATASET_VERSION="${DATASET_VERSION}" \
N_TASKS="${N_TASKS}" \
SEED="${SEED}" \
MODEL="${MODEL}" \
JOBS_DIR="${JOBS_DIR}" \
JOB_PREFIX="${JOB_PREFIX}" \
REPO_ROOT="${REPO_ROOT}" \
AGENT_ENV_JSON="${AGENT_ENV_JSON}" \
python - <<'PY'
import json
import os
import random
import urllib.request
from pathlib import Path

run_dir = Path(os.environ["RUN_DIR"])
task_list_path = Path(os.environ["TASK_LIST_PATH"])
cursor_config_path = Path(os.environ["CURSOR_CONFIG_PATH"])
malvin_config_path = Path(os.environ["MALVIN_CONFIG_PATH"])
registry_url = os.environ["REGISTRY_URL"]
dataset_name = os.environ["DATASET_NAME"]
dataset_version = os.environ["DATASET_VERSION"]
n_tasks = int(os.environ["N_TASKS"])
seed = int(os.environ["SEED"])
model = os.environ["MODEL"]
jobs_dir = os.environ["JOBS_DIR"]
job_prefix = os.environ["JOB_PREFIX"]
repo_root = os.environ["REPO_ROOT"]
agent_env = json.loads(os.environ["AGENT_ENV_JSON"])

with urllib.request.urlopen(registry_url, timeout=30) as response:
    registry = json.load(response)

dataset = None
for entry in registry:
    if entry.get("name") == dataset_name and str(entry.get("version")) == dataset_version:
        dataset = entry
        break
if dataset is None:
    raise RuntimeError(f"Dataset {dataset_name} {dataset_version} not found")

task_names = sorted({task["name"] for task in dataset.get("tasks", []) if "name" in task})
if len(task_names) < n_tasks:
    raise RuntimeError(f"Requested {n_tasks} tasks, found only {len(task_names)}")

rng = random.Random(seed)
sampled = sorted(rng.sample(task_names, n_tasks))

run_dir.mkdir(parents=True, exist_ok=True)
task_list_path.write_text(json.dumps(sampled, indent=2) + "\n", encoding="utf-8")

base = {
    "jobs_dir": jobs_dir,
    "n_attempts": 1,
    "timeout_multiplier": 1.0,
    "agent_timeout_multiplier": 20.0,
    "verifier_timeout_multiplier": None,
    "agent_setup_timeout_multiplier": None,
    "environment_build_timeout_multiplier": None,
    "debug": False,
    "orchestrator": {
        "type": "local",
        "n_concurrent_trials": 1,
        "quiet": False,
        "retry": {
            "max_retries": 0,
            "include_exceptions": None,
            "exclude_exceptions": [
                "AgentTimeoutError",
                "RewardFileNotFoundError",
                "VerifierOutputParseError",
                "RewardFileEmptyError",
                "VerifierTimeoutError",
            ],
            "wait_multiplier": 1.0,
            "min_wait_sec": 1.0,
            "max_wait_sec": 60.0,
        },
        "kwargs": {},
    },
    "environment": {
        "type": "docker",
        "import_path": None,
        "force_build": False,
        "delete": True,
        "override_cpus": None,
        "override_memory_mb": None,
        "override_storage_mb": None,
        "override_gpus": None,
        "suppress_override_warnings": False,
        "kwargs": {},
    },
    "verifier": {"override_timeout_sec": None, "max_timeout_sec": None, "disable": False},
    "metrics": [],
    "datasets": [
        {
            "task_names": sampled,
            "exclude_task_names": None,
            "n_tasks": n_tasks,
            "registry": {"name": None, "url": registry_url},
            "name": dataset_name,
            "version": dataset_version,
            "overwrite": False,
            "download_dir": None,
        }
    ],
    "tasks": [],
    "artifacts": [],
}

cursor_config = dict(base)
cursor_config["job_name"] = f"{job_prefix}-cursor-cli"
cursor_config["agents"] = [
    {
        "name": "cursor-cli",
        "import_path": None,
        "model_name": model,
        "override_timeout_sec": None,
        "override_setup_timeout_sec": None,
        "max_timeout_sec": None,
        "kwargs": {},
        "env": agent_env,
    }
]

malvin_config = dict(base)
malvin_config["job_name"] = f"{job_prefix}-malvin"
malvin_config["agents"] = [
    {
        "name": None,
        "import_path": "malvin.harbor_agent:MalvinHarborAgent",
        "model_name": model,
        "override_timeout_sec": None,
        "override_setup_timeout_sec": None,
        "max_timeout_sec": None,
        "kwargs": {"repo_root": repo_root},
        "env": agent_env,
    }
]

cursor_config_path.write_text(json.dumps(cursor_config, indent=2) + "\n", encoding="utf-8")
malvin_config_path.write_text(json.dumps(malvin_config, indent=2) + "\n", encoding="utf-8")

print(f"Wrote shared task list: {task_list_path}")
print(f"Wrote cursor config: {cursor_config_path}")
print(f"Wrote malvin config: {malvin_config_path}")
PY

harbor run "${CURSOR_CONFIG_PATH}"
harbor run "${MALVIN_CONFIG_PATH}"
