#!/usr/bin/env python3
"""Run the multi-step Cursor Agent experiment.

Usage:
    python demo/demo.py [plain|malvin] /path/to/source_dir /path/to/working_dir
"""

from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path

import click


def discover_tasks(tasks_dir: Path) -> list[Path]:
    tasks = sorted(tasks_dir.glob("task_*.md"))
    if len(tasks) != 10:
        raise RuntimeError(f"Expected exactly 10 task files in {tasks_dir}, found {len(tasks)}.")
    return tasks


def ensure_workspace(target_dir: Path, grounding_src: Path) -> None:
    if target_dir.exists():
        raise click.ClickException(
            f"Agent coding output directory already exists: {target_dir}. "
            "Please provide a new, non-existent path."
        )
    target_dir.mkdir(parents=True, exist_ok=False)
    grounding_dst = target_dir / "grounding.md"
    shutil.copy2(grounding_src, grounding_dst)

    # Remove any leaked task files so only task.md is visible to the agent.
    for leaked_task in target_dir.glob("task_*.md"):
        leaked_task.unlink()


def run_agent_for_task(target_dir: Path, task_src: Path, task_index: int, mode: str) -> int:
    task_dst = target_dir / "task.md"
    shutil.copy2(task_src, task_dst)

    if mode == "plain":
        prompt = (
            "Read grounding.md and task.md in this directory. "
            "Complete exactly the task in task.md while staying consistent with grounding.md."
        )
        cmd = f"cursor-agent --print --trust --force --model=opus-4.5 {shlex.quote(prompt)}"
    elif mode == "malvin":
        cmd = "malvin task.md"
    else:
        raise ValueError(f"Invalid mode: {mode}")
    print(f"\n[{task_index:02d}/10] Running: {task_src.name}")
    status = os.system(cmd)
    exit_code = os.waitstatus_to_exitcode(status)
    print(f"[{task_index:02d}/10] Exit code: {exit_code}")
    return exit_code


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("mode", type=click.Choice(["plain", "malvin"], case_sensitive=False))
@click.argument("source_dir", type=click.Path(path_type=Path))
@click.argument("agent_coding_output_path", type=click.Path(path_type=Path))
def main(mode: str, source_dir: Path, agent_coding_output_path: Path) -> None:
    mode = mode.lower()
    assert mode in ["plain", "malvin"], f"Invalid mode: {mode}"
    source_dir = source_dir.expanduser().resolve()
    grounding_src = source_dir / "grounding.md"
    tasks_dir = source_dir / "tasks"
    target_dir = agent_coding_output_path.expanduser().resolve()

    if not grounding_src.is_file():
        raise click.ClickException(f"Missing grounding file: {grounding_src}")

    try:
        tasks = discover_tasks(tasks_dir)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    ensure_workspace(target_dir, grounding_src)

    previous_cwd = Path.cwd()
    try:
        os.chdir(target_dir)
        for idx, task in enumerate(tasks, start=1):
            click.echo(f"EXPERIMENT_STEP: {task.name}\n------------------\n")
            try:
                code = run_agent_for_task(target_dir, task, idx, mode)
            finally:
                shutil.rmtree(target_dir / "_malvin", ignore_errors=True)
            if code != 0:
                raise click.ClickException(f"Stopping early after failure on {task.name}.")
    finally:
        os.chdir(previous_cwd)

    click.echo("\nExperiment completed: all 10 tasks executed.")


if __name__ == "__main__":
    main()
