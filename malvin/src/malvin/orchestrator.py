from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .agent_client import AgentClient, AgentError
from .artifacts import RunArtifacts
from .prompts import PromptStore


class WorkflowError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkflowConfig:
    max_loops: int = 5
    run_learn: bool = False


@dataclass(frozen=True)
class Orchestrator:
    client: AgentClient
    prompts: PromptStore
    artifacts: RunArtifacts
    config: WorkflowConfig
    progress_callback: Callable[[str], None] = lambda _message: None

    def run(self) -> None:
        context = {
            "plan_path": str(self.artifacts.plan_path),
            "kpop_log_dir": _format_prompt_path(
                self.artifacts.run_dir / "_kpop",
                base_dir=self.artifacts.work_dir,
            ),
        }
        self.progress_callback("Implement")
        self._run_coder_prompt("implement.md", context)
        self._run_review_phase(
            "review_1.md",
            "Review-1",
            "review_1",
            context,
        )
        self._run_review_phase(
            "review_2.md",
            "Review-2",
            "review_2",
            context,
        )
        if self.config.run_learn:
            self.progress_callback("Learn")
            self._run_coder_prompt("learn.md", context, suffix="final")

    def _run_review_phase(
        self,
        review_prompt: str,
        progress_label: str,
        phase_id: str,
        context: dict[str, str],
    ) -> None:
        review_path = self.artifacts.run_dir / "review.md"
        workspace_review_path = self.artifacts.work_dir / "review.md"
        for attempt in range(1, self.config.max_loops + 1):
            reviewer_session = f"{phase_id}_{attempt}"
            self.progress_callback(f"{progress_label} (attempt {attempt})")
            self._run_reviewer_prompt(
                review_prompt,
                context,
                session=reviewer_session,
                suffix=f"attempt_{attempt}",
            )
            _sync_review_file(
                workspace_review_path=workspace_review_path,
                artifact_review_path=review_path,
            )
            if _is_lgtm(review_path):
                return
            self.progress_callback(f"Kpop Review (attempt {attempt})")
            self._run_reviewer_prompt(
                "kpop.md",
                context,
                session=reviewer_session,
                suffix=f"{phase_id}_attempt_{attempt}",
            )
            self.progress_callback(f"Concerns (attempt {attempt})")
            self._run_coder_prompt(
                "concerns.md",
                context,
                suffix=f"{phase_id}_attempt_{attempt}",
            )
        raise WorkflowError(f"Did not receive LGTM for {review_prompt} within max loops.")

    def _run_coder_prompt(
        self,
        filename: str,
        context: dict[str, str],
        *,
        suffix: str = "main",
    ) -> None:
        prompt = self.prompts.render(filename, context)
        log_path = self.artifacts.log_path(f"coder_{filename[:-3]}_{suffix}")
        try:
            self.client.run_session_prompt(
                session="coder",
                prompt=prompt,
                cwd=self.artifacts.work_dir,
                log_path=log_path,
            )
        except AgentError as exc:
            raise WorkflowError(str(exc)) from exc

    def _run_reviewer_prompt(
        self,
        filename: str,
        context: dict[str, str],
        *,
        session: str = "reviewer",
        suffix: str = "main",
    ) -> None:
        if filename.startswith("review_"):
            self._clear_review_files()
        prompt = self.prompts.render(filename, context)
        log_path = self.artifacts.log_path(f"reviewer_{filename[:-3]}_{suffix}")
        try:
            self.client.run_session_prompt(
                session=session,
                prompt=prompt,
                cwd=self.artifacts.work_dir,
                log_path=log_path,
            )
        except AgentError as exc:
            raise WorkflowError(str(exc)) from exc

    def _clear_review_files(self) -> None:
        _clear_review_file(self.artifacts.run_dir / "review.md")
        _clear_review_file(self.artifacts.work_dir / "review.md")


def _is_lgtm(review_path: Path) -> bool:
    if not review_path.exists():
        return False
    return review_path.read_text(encoding="utf-8").strip() == "LGTM"


def _clear_review_file(review_path: Path) -> None:
    if review_path.exists():
        review_path.unlink()


def _sync_review_file(*, workspace_review_path: Path, artifact_review_path: Path) -> None:
    if not workspace_review_path.exists():
        return
    review_text = workspace_review_path.read_text(encoding="utf-8")
    artifact_review_path.write_text(review_text, encoding="utf-8")


def _format_prompt_path(path: Path, *, base_dir: Path) -> str:
    try:
        relative = path.resolve().relative_to(base_dir.resolve())
    except ValueError:
        return str(path)
    return f"./{relative.as_posix()}"
