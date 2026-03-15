from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import malvin.harbor_agent as harbor_agent
import pytest
from malvin.harbor_agent import (
    MalvinHarborAgent,
    build_malvin_run_command,
    build_plan_write_command,
    normalize_harbor_model_name,
)
from malvin.harbor_bundle import BundleMetadata, BundleResult


def test_normalize_harbor_model_name_provider_prefixed() -> None:
    assert normalize_harbor_model_name("anthropic/opus-4.5") == "opus-4.5"


def test_normalize_harbor_model_name_without_provider() -> None:
    assert normalize_harbor_model_name("gpt-5") == "gpt-5"


def test_normalize_harbor_model_name_defaults_when_missing() -> None:
    assert normalize_harbor_model_name(None) == "opus-4.5"


def test_build_plan_write_command_writes_exact_instruction(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.md"
    instruction = "Line one\nLine two with 'quotes' and /slashes/"
    command = build_plan_write_command(str(plan_path), instruction)

    completed = subprocess.run(
        ["bash", "-lc", command],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert plan_path.read_text(encoding="utf-8") == instruction


def test_build_malvin_run_command_contains_expected_invocation() -> None:
    command = build_malvin_run_command(
        plan_path="/tmp/malvin_plan.md",
        model_name="opus-4.5",
        log_path="/logs/agent/malvin.txt",
    )

    assert "cp /opt/malvin/.kissconfig ./.kissconfig;" in command
    assert "kiss clamp;" in command
    assert "malvin /tmp/malvin_plan.md --model opus-4.5 --tee" in command
    assert "tee /logs/agent/malvin.txt" in command


def test_fallback_exec_input_and_base_installed_agent_units(tmp_path: Path) -> None:
    exec_input = harbor_agent.ExecInput(command="echo hi")
    assert exec_input.command == "echo hi"
    assert exec_input.cwd is None
    assert exec_input.env is None
    assert exec_input.timeout_sec is None

    if harbor_agent._HARBOR_IMPORT_ERROR is None:
        base = harbor_agent.MalvinHarborAgent(logs_dir=tmp_path, model_name="m")
        assert base.logs_dir == tmp_path
        assert base.model_name == "m"
        assert base._setup_env()["DEBIAN_FRONTEND"] == "noninteractive"
        return

    base = harbor_agent.BaseInstalledAgent(logs_dir=tmp_path, model_name="m")
    assert base.logs_dir == tmp_path
    assert base.model_name == "m"
    assert base._setup_env()["DEBIAN_FRONTEND"] == "noninteractive"
    assert isinstance(harbor_agent.BaseEnvironment(), harbor_agent.BaseEnvironment)
    assert isinstance(harbor_agent.AgentContext(), harbor_agent.AgentContext)


def test_create_run_agent_commands_uses_normalized_model(tmp_path: Path) -> None:
    agent = MalvinHarborAgent(logs_dir=tmp_path, model_name="anthropic/opus-4.5")
    commands = agent.create_run_agent_commands("implement now")

    assert len(commands) == 2
    assert "/tmp/malvin_plan.md" in commands[0].command
    assert "--model opus-4.5" in commands[1].command


def test_populate_context_post_run_is_noop(tmp_path: Path) -> None:
    agent = MalvinHarborAgent(logs_dir=tmp_path, model_name="anthropic/opus-4.5")
    context = {"ok": True}
    agent.populate_context_post_run(context)
    assert context == {"ok": True}


def test_setup_uploads_bundle_and_writes_setup_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle_path = tmp_path / "bundle.tar.gz"
    bundle_path.write_bytes(b"bundle")
    metadata_path = tmp_path / "bundle.tar.gz.metadata.json"
    metadata = BundleMetadata(
        created_at_utc="2026-03-15T00:00:00Z",
        git_sha="abc123",
        source_tree_sha256="1" * 64,
        bundle_sha256="2" * 64,
        included_files=("src/malvin/cli.py",),
        included_count=1,
        repo_root=str(tmp_path),
    )
    metadata_path.write_text(json.dumps(metadata.__dict__), encoding="utf-8")
    bundle_result = BundleResult(
        bundle_path=bundle_path, metadata_path=metadata_path, metadata=metadata
    )
    monkeypatch.setattr(harbor_agent, "create_harbor_bundle", lambda **_kwargs: bundle_result)

    class FakeEnvironment:
        def __init__(self) -> None:
            self.uploads: list[tuple[Path, str]] = []
            self.exec_calls: list[tuple[str, dict[str, str] | None]] = []

        async def upload_file(self, source_path: Path, target_path: str) -> None:
            self.uploads.append((source_path, target_path))

        async def exec(self, command: str, cwd=None, env=None, timeout_sec=None):  # noqa: ANN001
            _ = cwd
            _ = timeout_sec
            self.exec_calls.append((command, env))
            return SimpleNamespace(return_code=0, stdout="ok", stderr="")

    env = FakeEnvironment()
    agent = MalvinHarborAgent(logs_dir=tmp_path / "logs", model_name="anthropic/opus-4.5")
    asyncio.run(agent.setup(env))

    assert [target for _, target in env.uploads] == [
        "/installed-agent/malvin.tar.gz",
        "/installed-agent/malvin.tar.gz.metadata.json",
        "/installed-agent/install.sh",
    ]
    assert (tmp_path / "logs" / "setup" / "return-code.txt").read_text(encoding="utf-8") == "0"
    assert (tmp_path / "logs" / "bundle-metadata.json").exists()


def test_setup_raises_on_nonzero_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = tmp_path / "bundle.tar.gz"
    bundle_path.write_bytes(b"bundle")
    metadata_path = tmp_path / "bundle.tar.gz.metadata.json"
    metadata = BundleMetadata(
        created_at_utc="2026-03-15T00:00:00Z",
        git_sha="abc123",
        source_tree_sha256="1" * 64,
        bundle_sha256="2" * 64,
        included_files=("src/malvin/cli.py",),
        included_count=1,
        repo_root=str(tmp_path),
    )
    metadata_path.write_text(json.dumps(metadata.__dict__), encoding="utf-8")
    bundle_result = BundleResult(
        bundle_path=bundle_path, metadata_path=metadata_path, metadata=metadata
    )
    monkeypatch.setattr(harbor_agent, "create_harbor_bundle", lambda **_kwargs: bundle_result)

    class FakeEnvironment:
        def __init__(self) -> None:
            self._calls = 0

        async def upload_file(self, source_path: Path, target_path: str) -> None:
            _ = source_path
            _ = target_path

        async def exec(self, command: str, cwd=None, env=None, timeout_sec=None):  # noqa: ANN001
            _ = command
            _ = cwd
            _ = env
            _ = timeout_sec
            self._calls += 1
            return SimpleNamespace(
                return_code=1 if self._calls > 1 else 0, stdout="", stderr="fail"
            )

    agent = MalvinHarborAgent(logs_dir=tmp_path / "logs", model_name="anthropic/opus-4.5")
    with pytest.raises(RuntimeError):
        asyncio.run(agent.setup(FakeEnvironment()))


def test_setup_fails_fast_when_initial_mkdir_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle_path = tmp_path / "bundle.tar.gz"
    bundle_path.write_bytes(b"bundle")
    metadata_path = tmp_path / "bundle.tar.gz.metadata.json"
    metadata = BundleMetadata(
        created_at_utc="2026-03-15T00:00:00Z",
        git_sha="abc123",
        source_tree_sha256="1" * 64,
        bundle_sha256="2" * 64,
        included_files=("src/malvin/cli.py",),
        included_count=1,
        repo_root=str(tmp_path),
    )
    metadata_path.write_text(json.dumps(metadata.__dict__), encoding="utf-8")
    bundle_result = BundleResult(
        bundle_path=bundle_path, metadata_path=metadata_path, metadata=metadata
    )
    monkeypatch.setattr(harbor_agent, "create_harbor_bundle", lambda **_kwargs: bundle_result)

    class FakeEnvironment:
        async def upload_file(self, source_path: Path, target_path: str) -> None:
            raise AssertionError("upload_file should not run when mkdir fails")

        async def exec(self, command: str, cwd=None, env=None, timeout_sec=None):  # noqa: ANN001
            _ = command
            _ = cwd
            _ = env
            _ = timeout_sec
            return SimpleNamespace(return_code=12, stdout="", stderr="mkdir failure")

    agent = MalvinHarborAgent(logs_dir=tmp_path / "logs", model_name="anthropic/opus-4.5")
    with pytest.raises(RuntimeError, match="before install script"):
        asyncio.run(agent.setup(FakeEnvironment()))
