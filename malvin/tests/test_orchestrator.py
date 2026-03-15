from __future__ import annotations

from pathlib import Path

import pytest
from malvin.agent_client import AgentResult
from malvin.artifacts import RunArtifacts
from malvin.orchestrator import Orchestrator, WorkflowConfig, WorkflowError

from malvin.prompts import PromptStore


class StubAgentClient:
    def __init__(
        self,
        review_1_outputs: list[str] | None = None,
        review_2_outputs: list[str] | None = None,
    ) -> None:
        self.review_1_outputs = list(review_1_outputs or [])
        self.review_2_outputs = list(review_2_outputs or [])
        self.calls: list[tuple[str, str]] = []

    def run_session_prompt(
        self,
        *,
        session: str,
        prompt: str,
        cwd: Path,
        log_path: Path,
    ) -> AgentResult:
        self.calls.append((session, log_path.name))
        if session != "reviewer":
            return AgentResult(output="ok", exit_code=0)
        if "review_1" in log_path.name:
            self._write_maybe(cwd, self.review_1_outputs)
        if "review_2" in log_path.name:
            self._write_maybe(cwd, self.review_2_outputs)
        return AgentResult(output="ok", exit_code=0)

    @staticmethod
    def _write_review(run_dir: Path, content: str) -> None:
        (run_dir / "review.md").write_text(content, encoding="utf-8")

    def _write_maybe(self, run_dir: Path, outputs: list[str]) -> None:
        content = outputs.pop(0)
        if content != "__NO_WRITE__":
            self._write_review(run_dir, content)


def _build_orchestrator(
    tmp_path: Path,
    review_1_outputs: list[str] | None = None,
    review_2_outputs: list[str] | None = None,
    max_loops: int = 3,
) -> Orchestrator:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    plan_path = run_dir / "plan.md"
    plan_path.write_text("plan", encoding="utf-8")
    artifacts = RunArtifacts(run_dir=run_dir, plan_path=plan_path, work_dir=tmp_path)
    prompts = PromptStore(root=tmp_path / "prompts")
    prompts.ensure_defaults()
    client = StubAgentClient(review_1_outputs=review_1_outputs, review_2_outputs=review_2_outputs)
    return Orchestrator(
        client=client,  # type: ignore[arg-type]
        prompts=prompts,
        artifacts=artifacts,
        config=WorkflowConfig(max_loops=max_loops),
    )


def test_orchestrator_runs_happy_path_without_concerns(tmp_path: Path) -> None:
    orchestrator = _build_orchestrator(
        tmp_path,
        review_1_outputs=["LGTM"],
        review_2_outputs=["LGTM"],
    )
    client = orchestrator.client  # type: ignore[assignment]

    orchestrator.run()

    log_names = [name for _, name in client.calls]
    assert any("coder_implement" in name for name in log_names)
    assert not any("concerns" in name for name in log_names)
    assert not any("kpop" in name for name in log_names)


def test_orchestrator_runs_kpop_and_concerns_when_not_lgtm(tmp_path: Path) -> None:
    orchestrator = _build_orchestrator(
        tmp_path,
        review_1_outputs=["Needs fixes", "LGTM"],
        review_2_outputs=["LGTM"],
    )
    client = orchestrator.client  # type: ignore[assignment]

    orchestrator.run()

    log_names = [name for _, name in client.calls]
    assert any("reviewer_kpop" in name for name in log_names)
    assert any("coder_concerns" in name for name in log_names)


def test_orchestrator_respects_max_loops(tmp_path: Path) -> None:
    orchestrator = _build_orchestrator(
        tmp_path,
        review_1_outputs=["Not yet", "Still no"],
        review_2_outputs=["LGTM"],
        max_loops=2,
    )

    with pytest.raises(WorkflowError):
        orchestrator.run()


def test_orchestrator_ignores_stale_lgtm_if_review_not_updated(tmp_path: Path) -> None:
    orchestrator = _build_orchestrator(
        tmp_path,
        review_1_outputs=["LGTM"],
        review_2_outputs=["__NO_WRITE__", "LGTM"],
        max_loops=2,
    )
    client = orchestrator.client  # type: ignore[assignment]

    orchestrator.run()

    log_names = [name for _, name in client.calls]
    assert any("reviewer_kpop" in name and "attempt_1" in name for name in log_names)
    assert any("coder_concerns" in name and "attempt_1" in name for name in log_names)


def test_orchestrator_runs_review_2_retry_cycle_before_lgtm(tmp_path: Path) -> None:
    orchestrator = _build_orchestrator(
        tmp_path,
        review_1_outputs=["LGTM"],
        review_2_outputs=["Needs second-pass fixes", "LGTM"],
        max_loops=3,
    )
    client = orchestrator.client  # type: ignore[assignment]

    orchestrator.run()

    log_names = [name for _, name in client.calls]
    assert any("reviewer_review_2_attempt_1" in name for name in log_names)
    assert any("reviewer_kpop_attempt_1" in name for name in log_names)
    assert any("coder_concerns_attempt_1" in name for name in log_names)
