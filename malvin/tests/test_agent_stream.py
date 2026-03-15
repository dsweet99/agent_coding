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
    monkeypatch.setattr("builtins.print", lambda text, end, flush: print_calls.append(text))

    output, exit_code = stream_module.stream_command(
        command=["cursor-agent", "--trust", "--print", "--output-format", "stream-json"],
        prompt="Hello",
        cwd=tmp_path,
        log_path=tmp_path / "tee.log",
        tee=True,
    )

    assert exit_code == 0
    assert output == "Hi"
    assert print_calls == ["Hi"]


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
