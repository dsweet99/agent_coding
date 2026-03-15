from __future__ import annotations

from pathlib import Path

import malvin.agent_client as agent_module
import pytest
from malvin.agent_client import AgentClient, AgentError, AgentResult, AuthError


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

    def fake_stream_command(*, command, prompt, cwd, log_path, tee):  # noqa: ANN001
        assert tee is False
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

    def fake_stream_command(*, command, prompt, cwd, log_path, tee):  # noqa: ANN001
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


def test_stream_command_wraps_oserror_as_agent_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agent_module,
        "_stream_command_raw",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("missing executable")),
    )

    with pytest.raises(AgentError):
        agent_module._stream_command(
            command=["cursor-agent"],
            prompt="hello",
            cwd=Path("."),
            log_path=Path("run.log"),
        )


def test_run_session_prompt_prepends_style_once_per_new_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent_prompts: list[str] = []

    def fake_stream_command(*, command, prompt, cwd, log_path, tee):  # noqa: ANN001
        sent_prompts.append(prompt)
        return AgentResult(output="ok", exit_code=0)

    style_path = tmp_path / "style.md"
    style_path.write_text("STYLE", encoding="utf-8")
    monkeypatch.setattr(agent_module, "_create_chat", lambda _session_id: "chat-123")
    monkeypatch.setattr(agent_module, "_stream_command", fake_stream_command)
    client = AgentClient(model="m", retries=0, run_suffix="abc123", style_prompt_path=style_path)

    client.run_session_prompt(
        session="coder",
        prompt="first coder",
        cwd=tmp_path,
        log_path=tmp_path / "coder1.log",
    )
    client.run_session_prompt(
        session="coder",
        prompt="second coder",
        cwd=tmp_path,
        log_path=tmp_path / "coder2.log",
    )
    client.run_session_prompt(
        session="reviewer",
        prompt="first reviewer",
        cwd=tmp_path,
        log_path=tmp_path / "reviewer1.log",
    )
    client.run_session_prompt(
        session="reviewer",
        prompt="second reviewer",
        cwd=tmp_path,
        log_path=tmp_path / "reviewer2.log",
    )

    assert sent_prompts == [
        "STYLE\n\nfirst coder",
        "second coder",
        "STYLE\n\nfirst reviewer",
        "second reviewer",
    ]
