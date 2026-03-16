from __future__ import annotations

import base64
import shlex


def normalize_harbor_model_name(model_name: str | None) -> str:
    if not model_name:
        return "opus-4.5"
    if "/" in model_name:
        return model_name.split("/", maxsplit=1)[1]
    return model_name


def build_plan_write_command(
    plan_path: str, instruction: str, *, python_bin: str = "python"
) -> str:
    encoded_instruction = base64.b64encode(instruction.encode("utf-8")).decode("ascii")
    escaped_python = shlex.quote(python_bin)
    return f"{escaped_python} -c " + shlex.quote(
        "import base64\n"
        "from pathlib import Path\n"
        f"Path({plan_path!r}).write_text("
        f"base64.b64decode({encoded_instruction!r}).decode('utf-8'), "
        "encoding='utf-8')\n"
    )


def build_malvin_run_command(*, plan_path: str, model_name: str, log_path: str) -> str:
    escaped_model = shlex.quote(model_name)
    escaped_plan_path = shlex.quote(plan_path)
    escaped_log_path = shlex.quote(log_path)
    return (
        'export PATH="/opt/malvin-venv/bin:$HOME/.local/bin:$PATH"; '
        "kiss clamp; "
        f"malvin {escaped_plan_path} --model {escaped_model} --tee "
        f"2>&1 | stdbuf -oL tee {escaped_log_path}"
    )
