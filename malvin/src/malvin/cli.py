from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import click

from .agent_client import AgentClient, AgentError, AuthError
from .artifacts import create_run_artifacts
from .orchestrator import Orchestrator, WorkflowConfig, WorkflowError
from .prompts import PromptError, PromptStore


def _format_logs_dir(run_dir: Path) -> str:
    try:
        relative = run_dir.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return str(run_dir)
    return f"./{relative.as_posix()}"


def _echo_plan_for_tee(plan_path: Path) -> None:
    plan_text = plan_path.read_text(encoding="utf-8")
    click.echo(plan_text, nl=False)
    if not plan_text.endswith("\n"):
        click.echo()


@dataclass(frozen=True)
class WorkflowRunOptions:
    plan_path: Path
    model: str
    force: bool
    max_loops: int
    tee: bool
    tee_json: bool
    learn: bool


def _workflow_flags(function):  # noqa: ANN001
    function = click.option(
        "--tee-json/--no-tee-json",
        default=False,
        show_default=True,
        help="When teeing output, print raw stream-json lines.",
    )(function)
    function = click.option(
        "--learn/--no-learn",
        default=False,
        show_default=True,
        help="Run learn.md with coder agent at end of workflow.",
    )(function)
    function = click.option(
        "--tee/--no-tee",
        default=False,
        show_default=True,
        help="Stream agent output to stdout while writing logs.",
    )(function)
    return function


@click.command()
@click.argument("plan_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--model", default="opus-4.5", show_default=True, help="Model for cursor-agent.")
@click.option(
    "--force/--no-force",
    default=True,
    show_default=True,
    help="Pass --force to cursor-agent.",
)
@click.option(
    "--max-loops",
    default=5,
    show_default=True,
    type=click.IntRange(min=1),
    help="Maximum attempts per review phase.",
)
@_workflow_flags
def main(
    plan_path: Path,
    model: str,
    force: bool,
    max_loops: int,
    *,
    tee: bool,
    tee_json: bool,
    learn: bool,
) -> None:
    """Run the malvin implementation and review workflow."""
    options = WorkflowRunOptions(
        plan_path=plan_path,
        model=model,
        force=force,
        max_loops=max_loops,
        tee=tee,
        tee_json=tee_json,
        learn=learn,
    )
    try:
        _run_workflow(options)
        click.echo("DONE")
    except (PromptError, AuthError, AgentError, WorkflowError) as exc:
        raise click.ClickException(str(exc)) from exc


def _run_workflow(options: WorkflowRunOptions) -> None:
    store = PromptStore.default()
    store.ensure_defaults()
    store.validate_required()
    if options.learn:
        store.validate_exists("learn.md")
    client = AgentClient(
        model=options.model,
        force=options.force,
        tee=options.tee or options.tee_json,
        tee_json=options.tee_json,
    )
    client.ensure_authenticated()
    artifacts = create_run_artifacts(options.plan_path)
    if options.tee and not options.tee_json:
        _echo_plan_for_tee(artifacts.plan_path)
    click.echo(f"Logs: {_format_logs_dir(artifacts.run_dir)}")
    orchestrator = Orchestrator(
        client=client,
        prompts=store,
        artifacts=artifacts,
        config=WorkflowConfig(max_loops=options.max_loops, run_learn=options.learn),
        progress_callback=click.echo,
    )
    orchestrator.run()


if __name__ == "__main__":
    main()
