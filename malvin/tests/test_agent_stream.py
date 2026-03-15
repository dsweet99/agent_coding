from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import malvin.agent_stream as stream_module
import pytest
from stream_json_helpers import assistant_final, assistant_partial


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
    monkeypatch.setattr(stream_module.subprocess, "Popen", lambda *args, **kwargs: fake_process)
    log_path = tmp_path / "stream.log"

    output, exit_code = stream_module.stream_command(
        command=["cursor-agent", "--trust", "--print", "--output-format", "stream-json"],
        prompt="Hello",
        cwd=tmp_path,
        log_path=log_path,
    )

    assert exit_code == 0
    assert output == "Hello there"
    assert fake_stdin.write.call_args.args[0] == "Hello\n"
    log_text = log_path.read_text(encoding="utf-8")
    assert "Hello there" in log_text
    assert '{"type":' not in log_text


def test_stream_command_tees_text_to_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_stdin = Mock()
    fake_stdout = iter([assistant_partial("Hi"), assistant_final("Hi")])
    fake_process = Mock(stdin=fake_stdin, stdout=fake_stdout)
    fake_process.wait.return_value = 0
    monkeypatch.setattr(stream_module.subprocess, "Popen", lambda *args, **kwargs: fake_process)
    print_calls: list[str] = []
    monkeypatch.setattr(
        "builtins.print", lambda text="", end="\n", flush=False: print_calls.append(text)
    )

    output, exit_code = stream_module.stream_command(
        command=["cursor-agent", "--trust", "--print", "--output-format", "stream-json"],
        prompt="Hello",
        cwd=tmp_path,
        log_path=tmp_path / "tee.log",
        tee_mode="text",
    )

    assert exit_code == 0
    assert output == "Hi"
    assert print_calls == ["Hi", ""]


def test_stream_command_tees_raw_json_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_stdin = Mock()
    raw_lines = [
        assistant_partial("Hi"),
        assistant_final("Hi"),
        '{"type":"result","subtype":"success","result":"Hi"}\n',
    ]
    fake_stdout = iter(raw_lines)
    fake_process = Mock(stdin=fake_stdin, stdout=fake_stdout)
    fake_process.wait.return_value = 0
    monkeypatch.setattr(stream_module.subprocess, "Popen", lambda *args, **kwargs: fake_process)
    print_calls: list[str] = []
    monkeypatch.setattr(
        "builtins.print", lambda text="", end="\n", flush=False: print_calls.append(text)
    )

    output, exit_code = stream_module.stream_command(
        command=["cursor-agent", "--trust", "--print", "--output-format", "stream-json"],
        prompt="Hello",
        cwd=tmp_path,
        log_path=tmp_path / "tee_json.log",
        tee_mode="json",
    )

    assert exit_code == 0
    assert output == "Hi"
    assert print_calls == raw_lines


def test_stream_command_dedupes_cumulative_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_stdin = Mock()
    fake_stdout = iter(
        [
            assistant_partial("Let me check"),
            assistant_partial("Let me check the project"),
            assistant_partial("Let me check the project"),
            assistant_final("Let me check the project"),
        ]
    )
    fake_process = Mock(stdin=fake_stdin, stdout=fake_stdout)
    fake_process.wait.return_value = 0
    monkeypatch.setattr(stream_module.subprocess, "Popen", lambda *args, **kwargs: fake_process)

    output, exit_code = stream_module.stream_command(
        command=["cursor-agent", "--trust", "--print", "--output-format", "stream-json"],
        prompt="Hello",
        cwd=tmp_path,
        log_path=tmp_path / "dedupe.log",
    )

    assert exit_code == 0
    assert output == "Let me check the project"


def test_stream_command_dedupes_repeated_partial_retransmits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_stdin = Mock()
    fake_stdout = iter(
        [
            assistant_partial("ha"),
            assistant_partial("ha", timestamp=2),
            assistant_final("haha"),
        ]
    )
    fake_process = Mock(stdin=fake_stdin, stdout=fake_stdout)
    fake_process.wait.return_value = 0
    monkeypatch.setattr(stream_module.subprocess, "Popen", lambda *args, **kwargs: fake_process)

    output, exit_code = stream_module.stream_command(
        command=["cursor-agent", "--trust", "--print", "--output-format", "stream-json"],
        prompt="Hello",
        cwd=tmp_path,
        log_path=tmp_path / "delta_repeat.log",
    )

    assert exit_code == 0
    assert output == "ha"


def test_stream_command_dedupes_delta_stream_followed_by_full_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_stdin = Mock()
    fake_stdout = iter(
        [
            assistant_partial("Now"),
            assistant_partial(" I"),
            assistant_partial(" understand"),
            assistant_partial("."),
            assistant_partial("Now I understand.", timestamp=99),
            assistant_final("Now I understand."),
        ]
    )
    fake_process = Mock(stdin=fake_stdin, stdout=fake_stdout)
    fake_process.wait.return_value = 0
    monkeypatch.setattr(stream_module.subprocess, "Popen", lambda *args, **kwargs: fake_process)

    output, exit_code = stream_module.stream_command(
        command=["cursor-agent", "--trust", "--print", "--output-format", "stream-json"],
        prompt="Hello",
        cwd=tmp_path,
        log_path=tmp_path / "delta_then_full.log",
    )

    assert exit_code == 0
    assert output == "Now I understand."


def test_stream_command_preserves_tee_text_without_heuristics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_stdin = Mock()
    fake_stdout = iter([assistant_partial("One.Two"), assistant_final("One.Two")])
    fake_process = Mock(stdin=fake_stdin, stdout=fake_stdout)
    fake_process.wait.return_value = 0
    monkeypatch.setattr(stream_module.subprocess, "Popen", lambda *args, **kwargs: fake_process)
    print_calls: list[str] = []
    monkeypatch.setattr(
        "builtins.print", lambda text="", end="\n", flush=False: print_calls.append(text)
    )

    output, exit_code = stream_module.stream_command(
        command=["cursor-agent", "--trust", "--print", "--output-format", "stream-json"],
        prompt="Hello",
        cwd=tmp_path,
        log_path=tmp_path / "tee_breaks.log",
        tee_mode="text",
    )

    assert exit_code == 0
    assert output == "One.Two"
    assert print_calls == ["One.Two", ""]


def test_parse_stream_line_handles_non_json_and_ignored_events() -> None:
    text, is_partial = stream_module.parse_stream_line("plain text\n", saw_partial_assistant=False)
    assert text == "plain text\n"
    assert is_partial is False

    text, is_partial = stream_module.parse_stream_line(
        '{"type":"tool_call","name":"x"}\n',
        saw_partial_assistant=False,
    )
    assert text == ""
    assert is_partial is False


def test_parse_stream_line_handles_assistant_and_result_branches() -> None:
    assistant_final = '{"type":"assistant","message":{"content":[{"type":"text","text":"done"}]}}\n'
    text, is_partial = stream_module.parse_stream_line(assistant_final, saw_partial_assistant=False)
    assert text == "done\n"
    assert is_partial is False

    result_event = '{"type":"result","result":"final"}\n'
    text, is_partial = stream_module.parse_stream_line(result_event, saw_partial_assistant=True)
    assert text == ""
    assert is_partial is False
