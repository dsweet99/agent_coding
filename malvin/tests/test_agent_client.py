from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import Mock

import malvin.agent_client as agent_module
import pytest
from malvin.agent_client import AgentClient, AgentError, AgentResult, AuthError
from stream_json_helpers import assistant_final, assistant_partial


@pytest.mark.skipif(
    not os.getenv("MALVIN_RUN_LIVE_AGENT_TEST"),
    reason="Set MALVIN_RUN_LIVE_AGENT_TEST=1 to run live cursor-agent integration test.",
)
def test_run_session_prompt_live_output_longer_than_five(tmp_path: Path) -> None:
    client = AgentClient(model=os.getenv("MALVIN_TEST_MODEL", "opus-4.5"), force=True, retries=0)

    result = client.run_session_prompt(
        session="coder",
        prompt="Hello",
        cwd=tmp_path,
        log_path=tmp_path / "live_agent.log",
    )

    assert len(result.output) > 5


@pytest.mark.skipif(
    not os.getenv("MALVIN_RUN_LIVE_STREAM_AGENT_TEST"),
    reason="Set MALVIN_RUN_LIVE_STREAM_AGENT_TEST=1 to run live stream-json test.",
)
def test_run_session_prompt_live_stream_writes_human_readable_log(tmp_path: Path) -> None:
    client = AgentClient(model=os.getenv("MALVIN_TEST_MODEL", "opus-4.5"), force=True, retries=0)

    result = client.run_session_prompt(
        session="coder",
        prompt="Hello",
        cwd=tmp_path,
        log_path=tmp_path / "live_stream.log",
    )
    log_text = (tmp_path / "live_stream.log").read_text(encoding="utf-8")

    assert len(result.output) > 5
    assert '{"type":' not in log_text
    assert "Hello" in log_text


def test_build_command_includes_trust_print_and_resume() -> None:
    command = agent_module._build_command(model="opus-4.5", force=True, chat_id="chat-123")

    assert command == [
        "cursor-agent",
        "--model",
        "opus-4.5",
        "--resume",
        "chat-123",
        "--trust",
        "--print",
        "--output-format",
        "stream-json",
        "--stream-partial-output",
        "--force",
    ]


def test_build_command_omits_force_when_disabled() -> None:
    command = agent_module._build_command(model="opus-4.5", force=False, chat_id="chat-456")

    assert "--force" not in command


def test_ensure_authenticated_succeeds_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURSOR_AGENT_API_KEY", "abc123")
    client = AgentClient(model="m")

    client.ensure_authenticated()


def test_ensure_authenticated_raises_when_no_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CURSOR_AGENT_API_KEY", raising=False)
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_API_KEY", raising=False)
    monkeypatch.setattr(agent_module, "_auth_probe", lambda _command: False)
    client = AgentClient(model="m")

    with pytest.raises(AuthError):
        client.ensure_authenticated()


def test_run_session_prompt_retries_and_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"count": 0}

    def fake_stream_command(*, command, prompt, cwd, log_path):  # noqa: ANN001
        calls["count"] += 1
        if calls["count"] == 1:
            return AgentResult(output="temporary failure", exit_code=1)
        return AgentResult(output="ok", exit_code=0)

    monkeypatch.setattr(agent_module, "_create_chat", lambda _session_id: "chat-123")
    monkeypatch.setattr(agent_module, "_stream_command", fake_stream_command)
    monkeypatch.setattr(agent_module.time, "sleep", lambda _delay: None)
    client = AgentClient(model="m", retries=2, run_suffix="abc123")

    result = client.run_session_prompt(
        session="coder",
        prompt="hello",
        cwd=tmp_path,
        log_path=tmp_path / "run.log",
    )

    assert result.exit_code == 0
    assert calls["count"] == 2


def test_run_session_prompt_raises_after_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agent_module, "_create_chat", lambda _session_id: "chat-123")
    monkeypatch.setattr(
        agent_module,
        "_stream_command",
        lambda **_kwargs: AgentResult(output="nope", exit_code=1),
    )
    monkeypatch.setattr(agent_module.time, "sleep", lambda _delay: None)
    client = AgentClient(model="m", retries=1, run_suffix="abc123")

    with pytest.raises(AgentError):
        client.run_session_prompt(
            session="reviewer",
            prompt="hello",
            cwd=tmp_path,
            log_path=tmp_path / "run.log",
        )


def test_run_session_prompt_reuses_chat_for_same_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_calls = {"count": 0}
    created_session_ids: list[str] = []
    commands: list[list[str]] = []

    def fake_create_chat(session_id: str) -> str:
        create_calls["count"] += 1
        created_session_ids.append(session_id)
        return "chat-xyz"

    def fake_stream_command(*, command, prompt, cwd, log_path):  # noqa: ANN001
        commands.append(command)
        return AgentResult(output="ok", exit_code=0)

    monkeypatch.setattr(agent_module, "_create_chat", fake_create_chat)
    monkeypatch.setattr(agent_module, "_stream_command", fake_stream_command)
    client = AgentClient(model="m", retries=0, run_suffix="xyz789")

    client.run_session_prompt(
        session="coder",
        prompt="hello one",
        cwd=tmp_path,
        log_path=tmp_path / "run1.log",
    )
    client.run_session_prompt(
        session="coder",
        prompt="hello two",
        cwd=tmp_path,
        log_path=tmp_path / "run2.log",
    )

    assert create_calls["count"] == 1
    assert len(commands) == 2
    assert commands[0] == commands[1]
    assert created_session_ids == ["coder_xyz789"]


def test_run_session_prompt_uses_distinct_session_ids_per_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    created_session_ids: list[str] = []

    def fake_create_chat(session_id: str) -> str:
        created_session_ids.append(session_id)
        return f"chat-for-{session_id}"

    monkeypatch.setattr(agent_module, "_create_chat", fake_create_chat)
    monkeypatch.setattr(
        agent_module,
        "_stream_command",
        lambda **_kwargs: AgentResult(output="ok", exit_code=0),
    )
    client = AgentClient(model="m", retries=0, run_suffix="run42")

    client.run_session_prompt(
        session="coder",
        prompt="hello",
        cwd=tmp_path,
        log_path=tmp_path / "coder.log",
    )
    client.run_session_prompt(
        session="reviewer",
        prompt="hello",
        cwd=tmp_path,
        log_path=tmp_path / "reviewer.log",
    )

    assert created_session_ids == ["coder_run42", "reviewer_run42"]


def test_stream_command_writes_newline_terminated_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_stdin = Mock()
    fake_stdout = iter(["ok\n"])
    fake_process = Mock(stdin=fake_stdin, stdout=fake_stdout)
    fake_process.wait.return_value = 0
    monkeypatch.setattr(agent_module.subprocess, "Popen", lambda *args, **kwargs: fake_process)

    agent_module._stream_command(
        command=["cursor-agent", "--trust", "--print"],
        prompt="Implement a hello-world CLI.",
        cwd=tmp_path,
        log_path=tmp_path / "run.log",
    )

    fake_stdin.write.assert_called_once_with("Implement a hello-world CLI.\n")


def test_stream_command_converts_stream_json_to_human_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_stdin = Mock()
    fake_stdout = iter(
        [
            assistant_partial("Hello"),
            assistant_partial(" there", timestamp=2),
            assistant_final("Hello there"),
            '{"type":"result","subtype":"success","result":"Hello there"}\n',
        ]
    )
    fake_process = Mock(stdin=fake_stdin, stdout=fake_stdout)
    fake_process.wait.return_value = 0
    monkeypatch.setattr(agent_module.subprocess, "Popen", lambda *args, **kwargs: fake_process)
    log_path = tmp_path / "run.log"

    result = agent_module._stream_command(
        command=["cursor-agent", "--trust", "--print", "--output-format", "stream-json"],
        prompt="Hi",
        cwd=tmp_path,
        log_path=log_path,
    )

    assert result.output == "Hello there"
    log_text = log_path.read_text(encoding="utf-8")
    assert "Hello there" in log_text
    assert '{"type":' not in log_text
