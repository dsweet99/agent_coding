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
        self.concerns_reviews: list[str] = []

    def run_session_prompt(
        self,
        *,
        session: str,
        prompt: str,
        cwd: Path,
        log_path: Path,
    ) -> AgentResult:
        self.calls.append((session, log_path.name))
        if session == "coder" and "concerns" in log_path.name:
            review_path = cwd / "review.md"
            if review_path.exists():
                self.concerns_reviews.append(review_path.read_text(encoding="utf-8"))
            else:
                self.concerns_reviews.append("__MISSING__")
        if not session.startswith("reviewer"):
            return AgentResult(output="ok", exit_code=0)
        if log_path.name.startswith("reviewer_review_1_"):
            self._write_maybe(cwd, self.review_1_outputs)
        if log_path.name.startswith("reviewer_review_2_"):
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
    run_learn: bool = False,
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
        config=WorkflowConfig(max_loops=max_loops, run_learn=run_learn),
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
    assert any("reviewer_kpop_review_2_attempt_1" in name for name in log_names)
    assert any("coder_concerns_review_2_attempt_1" in name for name in log_names)


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
    assert any("reviewer_kpop_review_2_attempt_1" in name for name in log_names)
    assert any("coder_concerns_review_2_attempt_1" in name for name in log_names)


def test_orchestrator_keeps_workspace_review_for_concerns(tmp_path: Path) -> None:
    orchestrator = _build_orchestrator(
        tmp_path,
        review_1_outputs=["Needs fixes", "LGTM"],
        review_2_outputs=["LGTM"],
    )
    client = orchestrator.client  # type: ignore[assignment]

    orchestrator.run()

    assert client.concerns_reviews
    assert client.concerns_reviews[0] == "Needs fixes"


def test_orchestrator_uses_fresh_reviewer_session_per_phase(tmp_path: Path) -> None:
    orchestrator = _build_orchestrator(
        tmp_path,
        review_1_outputs=["LGTM"],
        review_2_outputs=["Needs second-pass fixes", "LGTM"],
        max_loops=3,
    )
    client = orchestrator.client  # type: ignore[assignment]

    orchestrator.run()

    sessions_by_log = {log_name: session for session, log_name in client.calls}
    assert sessions_by_log["reviewer_review_1_attempt_1.log"] == "reviewer_review_1"
    assert sessions_by_log["reviewer_review_2_attempt_1.log"] == "reviewer_review_2"
    assert sessions_by_log["reviewer_kpop_review_2_attempt_1.log"] == "reviewer_review_2"
    assert sessions_by_log["reviewer_review_2_attempt_2.log"] == "reviewer_review_2"


def test_orchestrator_separates_phase_logs_for_kpop_and_concerns(tmp_path: Path) -> None:
    orchestrator = _build_orchestrator(
        tmp_path,
        review_1_outputs=["Needs fixes", "LGTM"],
        review_2_outputs=["Needs more fixes", "LGTM"],
        max_loops=3,
    )
    client = orchestrator.client  # type: ignore[assignment]

    orchestrator.run()

    log_names = {name for _, name in client.calls}
    assert "reviewer_kpop_review_1_attempt_1.log" in log_names
    assert "reviewer_kpop_review_2_attempt_1.log" in log_names
    assert "coder_concerns_review_1_attempt_1.log" in log_names
    assert "coder_concerns_review_2_attempt_1.log" in log_names


def test_orchestrator_runs_learn_last_on_success(tmp_path: Path) -> None:
    orchestrator = _build_orchestrator(
        tmp_path,
        review_1_outputs=["LGTM"],
        review_2_outputs=["LGTM"],
        run_learn=True,
    )
    client = orchestrator.client  # type: ignore[assignment]

    orchestrator.run()

    log_names = [name for _, name in client.calls]
    assert any("coder_learn_final" in name for name in log_names)
    assert log_names[-1] == "coder_learn_final.log"


def test_orchestrator_does_not_run_learn_when_disabled(tmp_path: Path) -> None:
    orchestrator = _build_orchestrator(
        tmp_path,
        review_1_outputs=["LGTM"],
        review_2_outputs=["LGTM"],
        run_learn=False,
    )
    client = orchestrator.client  # type: ignore[assignment]

    orchestrator.run()

    log_names = [name for _, name in client.calls]
    assert not any("coder_learn_" in name for name in log_names)


def test_orchestrator_does_not_run_learn_after_failed_review(tmp_path: Path) -> None:
    orchestrator = _build_orchestrator(
        tmp_path,
        review_1_outputs=["No", "Still no"],
        review_2_outputs=["LGTM"],
        max_loops=2,
        run_learn=True,
    )
    client = orchestrator.client  # type: ignore[assignment]

    with pytest.raises(WorkflowError):
        orchestrator.run()

    log_names = [name for _, name in client.calls]
    assert not any("coder_learn_" in name for name in log_names)
