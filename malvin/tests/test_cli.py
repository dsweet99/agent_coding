from __future__ import annotations

from pathlib import Path

import malvin.cli as cli_module
import pytest
from click.testing import CliRunner
from malvin.artifacts import RunArtifacts
from malvin.prompts import PromptError


class DummyStore:
    def __init__(self, should_fail: bool = False, missing_learn: bool = False) -> None:
        self.should_fail = should_fail
        self.missing_learn = missing_learn

    def ensure_defaults(self) -> None:
        return None

    def validate_required(self) -> None:
        if self.should_fail:
            raise PromptError("missing prompts")

    def validate_exists(self, filename: str) -> None:
        if filename == "learn.md" and self.missing_learn:
            raise PromptError("missing learn")


class DummyClient:
    instances: list[DummyClient] = []

    def __init__(self, model: str, force: bool, tee: bool, tee_json: bool = False) -> None:
        self.model = model
        self.force = force
        self.tee = tee
        self.tee_json = tee_json
        self.auth_checked = False
        self.__class__.instances.append(self)

    def ensure_authenticated(self) -> None:
        self.auth_checked = True


class DummyOrchestrator:
    instances: list[DummyOrchestrator] = []

    def __init__(self, client, prompts, artifacts, config, progress_callback=None) -> None:
        self.client = client
        self.prompts = prompts
        self.artifacts = artifacts
        self.config = config
        self.progress_callback = progress_callback
        self.ran = False
        self.__class__.instances.append(self)

    def run(self) -> None:
        self.ran = True


def _fake_artifacts(tmp_path: Path) -> RunArtifacts:
    run_dir = tmp_path / "_malvin" / "run_123"
    run_dir.mkdir(parents=True)
    plan = run_dir / "plan.md"
    plan.write_text("copied", encoding="utf-8")
    return RunArtifacts(run_dir=run_dir, plan_path=plan, work_dir=tmp_path)


def test_cli_uses_defaults_and_prints_run_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts = _fake_artifacts(tmp_path)
    monkeypatch.setattr(cli_module.PromptStore, "default", classmethod(lambda cls: DummyStore()))
    monkeypatch.setattr(cli_module, "create_run_artifacts", lambda _: artifacts)
    monkeypatch.setattr(cli_module, "AgentClient", DummyClient)
    monkeypatch.setattr(cli_module, "Orchestrator", DummyOrchestrator)
    runner = CliRunner()
    plan_file = tmp_path / "input_plan.md"
    plan_file.write_text("plan", encoding="utf-8")

    result = runner.invoke(cli_module.main, [str(plan_file), "--tee"])

    assert result.exit_code == 0
    output_lines = [line for line in result.output.splitlines() if line]
    assert output_lines[0] == "copied"
    assert output_lines[1].startswith("Logs: ")
    assert str(artifacts.run_dir) in output_lines[1]
    assert output_lines[-1] == "DONE"
    assert DummyClient.instances[-1].model == "opus-4.5"
    assert DummyClient.instances[-1].force is True
    assert DummyClient.instances[-1].tee is True
    assert DummyClient.instances[-1].tee_json is False
    assert DummyClient.instances[-1].auth_checked is True
    assert DummyOrchestrator.instances[-1].config.max_loops == 5
    assert DummyOrchestrator.instances[-1].config.run_learn is False
    assert DummyOrchestrator.instances[-1].ran is True


def test_cli_passes_learn_flag_to_workflow_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts = _fake_artifacts(tmp_path)
    monkeypatch.setattr(cli_module.PromptStore, "default", classmethod(lambda cls: DummyStore()))
    monkeypatch.setattr(cli_module, "create_run_artifacts", lambda _: artifacts)
    monkeypatch.setattr(cli_module, "AgentClient", DummyClient)
    monkeypatch.setattr(cli_module, "Orchestrator", DummyOrchestrator)
    runner = CliRunner()
    plan_file = tmp_path / "input_plan.md"
    plan_file.write_text("plan", encoding="utf-8")

    result = runner.invoke(cli_module.main, [str(plan_file), "--learn"])

    assert result.exit_code == 0
    assert DummyOrchestrator.instances[-1].config.run_learn is True


def test_cli_passes_tee_json_to_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    artifacts = _fake_artifacts(tmp_path)
    monkeypatch.setattr(cli_module.PromptStore, "default", classmethod(lambda cls: DummyStore()))
    monkeypatch.setattr(cli_module, "create_run_artifacts", lambda _: artifacts)
    monkeypatch.setattr(cli_module, "AgentClient", DummyClient)
    monkeypatch.setattr(cli_module, "Orchestrator", DummyOrchestrator)
    runner = CliRunner()
    plan_file = tmp_path / "input_plan.md"
    plan_file.write_text("plan", encoding="utf-8")

    result = runner.invoke(cli_module.main, [str(plan_file), "--tee-json"])

    assert result.exit_code == 0
    assert DummyClient.instances[-1].tee is True
    assert DummyClient.instances[-1].tee_json is True
    output_lines = [line for line in result.output.splitlines() if line]
    assert output_lines[0].startswith("Logs: ")
    assert output_lines[-1] == "DONE"


def test_cli_returns_click_error_for_missing_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cli_module.PromptStore, "default", classmethod(lambda cls: DummyStore(should_fail=True))
    )
    runner = CliRunner()
    plan_file = tmp_path / "input_plan.md"
    plan_file.write_text("plan", encoding="utf-8")

    result = runner.invoke(cli_module.main, [str(plan_file)])

    assert result.exit_code != 0
    assert "missing prompts" in result.output


def test_cli_fails_auth_before_creating_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_called = {"value": False}

    class AuthFailClient:
        def __init__(self, model: str, force: bool, tee: bool, tee_json: bool = False) -> None:
            self.model = model
            self.force = force
            self.tee = tee
            self.tee_json = tee_json

        def ensure_authenticated(self) -> None:
            raise cli_module.AuthError("not authenticated")

    def fail_if_called(_plan_path: Path) -> RunArtifacts:
        create_called["value"] = True
        raise AssertionError("create_run_artifacts should not be called before auth")

    monkeypatch.setattr(cli_module.PromptStore, "default", classmethod(lambda cls: DummyStore()))
    monkeypatch.setattr(cli_module, "AgentClient", AuthFailClient)
    monkeypatch.setattr(cli_module, "create_run_artifacts", fail_if_called)
    runner = CliRunner()
    plan_file = tmp_path / "input_plan.md"
    plan_file.write_text("plan", encoding="utf-8")

    result = runner.invoke(cli_module.main, [str(plan_file)])

    assert result.exit_code != 0
    assert "not authenticated" in result.output
    assert create_called["value"] is False


def test_cli_fails_when_learn_prompt_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_called = {"value": False}
    monkeypatch.setattr(
        cli_module.PromptStore,
        "default",
        classmethod(lambda cls: DummyStore(missing_learn=True)),
    )
    monkeypatch.setattr(cli_module, "AgentClient", DummyClient)
    monkeypatch.setattr(
        cli_module,
        "create_run_artifacts",
        lambda _plan_path: create_called.__setitem__("value", True),
    )
    runner = CliRunner()
    plan_file = tmp_path / "input_plan.md"
    plan_file.write_text("plan", encoding="utf-8")

    result = runner.invoke(cli_module.main, [str(plan_file), "--learn"])

    assert result.exit_code != 0
    assert "missing learn" in result.output
    assert create_called["value"] is False
