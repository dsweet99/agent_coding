from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path


def stream_command(
    *,
    command: list[str],
    prompt: str,
    cwd: Path,
    log_path: Path,
    tee_mode: str = "off",
) -> tuple[str, int]:
    last_fsync_at = 0.0
    prompt_payload = prompt if prompt.endswith("\n") else f"{prompt}\n"
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"$ {' '.join(command)}\n")
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert process.stdin is not None
        process.stdin.write(prompt_payload)
        process.stdin.close()
        output_chunks, last_fsync_at = _collect_stream_output(
            process=process,
            log_file=log_file,
            tee_mode=tee_mode,
            last_fsync_at=last_fsync_at,
        )
        exit_code = process.wait()
        if tee_mode == "text" and output_chunks and not output_chunks[-1].endswith("\n"):
            print("", flush=True)
        _finalize_log(
            log_file=log_file,
            output_chunks=output_chunks,
            exit_code=exit_code,
            last_fsync_at=last_fsync_at,
        )
    return "".join(output_chunks), exit_code


def _collect_stream_output(
    *,
    process: subprocess.Popen[str],
    log_file,
    tee_mode: str,
    last_fsync_at: float,
) -> tuple[list[str], float]:
    output_chunks: list[str] = []
    saw_partial_assistant = False
    partial_state = ("", "", "unknown")
    assert process.stdout is not None
    for line in process.stdout:
        if tee_mode == "json":
            print(line, end="", flush=True)
        text, is_partial = parse_stream_line(line, saw_partial_assistant=saw_partial_assistant)
        if is_partial:
            saw_partial_assistant = True
            text, partial_state = _dedupe_partial_text(
                text,
                partial_state=partial_state,
            )
        else:
            partial_state = ("", "", "unknown")
        if not text:
            continue
        log_file.write(text)
        if tee_mode == "text":
            print(text, end="", flush=True)
        log_file.flush()
        now = time.monotonic()
        if now - last_fsync_at >= 1.0:
            os.fsync(log_file.fileno())
            last_fsync_at = now
        output_chunks.append(text)
    return output_chunks, last_fsync_at


def _finalize_log(
    *,
    log_file,
    output_chunks: list[str],
    exit_code: int,
    last_fsync_at: float,
) -> None:
    if output_chunks and not output_chunks[-1].endswith("\n"):
        log_file.write("\n")
    log_file.write(f"\n[exit_code={exit_code}]\n")
    log_file.flush()
    _ = last_fsync_at
    os.fsync(log_file.fileno())


def parse_stream_line(line: str, *, saw_partial_assistant: bool) -> tuple[str, bool]:
    stripped = line.strip()
    if not stripped:
        return "", False
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return line, False
    if not isinstance(payload, dict):
        payload = {}
    event_type = payload.get("type")
    if event_type == "assistant":
        return _parse_assistant_event(payload, saw_partial_assistant=saw_partial_assistant)
    if event_type == "result":
        return _parse_result_event(payload, saw_partial_assistant=saw_partial_assistant)
    return "", False


def _extract_text(payload: dict[str, object]) -> str:
    message = payload.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if not isinstance(content, list):
        return ""
    return "".join(
        part.get("text", "")
        for part in content
        if isinstance(part, dict) and part.get("type") == "text"
    )


def _dedupe_partial_text(
    text: str,
    *,
    partial_state: tuple[str, str, str],
) -> tuple[str, tuple[str, str, str]]:
    if not text:
        return "", partial_state
    emitted_text, last_chunk, partial_mode = partial_state
    if not emitted_text:
        return text, (text, text, "unknown")
    return _dedupe_known_partial_text(
        text,
        emitted_text=emitted_text,
        last_chunk=last_chunk,
        partial_mode=partial_mode,
    )


def _dedupe_known_partial_text(
    text: str, *, emitted_text: str, last_chunk: str, partial_mode: str
) -> tuple[str, tuple[str, str, str]]:
    if text == emitted_text:
        return "", (emitted_text, last_chunk, "cumulative")
    if text.startswith(emitted_text):
        delta = text[len(emitted_text) :]
        return delta, (text, delta or last_chunk, "cumulative")
    if emitted_text.startswith(text):
        return "", (text, last_chunk, "cumulative")
    if partial_mode == "delta" and text == last_chunk:
        return "", (emitted_text, last_chunk, "delta")
    return text, (f"{emitted_text}{text}", text, "delta")


def _parse_assistant_event(
    payload: dict[str, object], *, saw_partial_assistant: bool
) -> tuple[str, bool]:
    text = _extract_text(payload)
    if not text:
        return "", False
    if payload.get("timestamp_ms") is not None:
        return text, True
    if saw_partial_assistant:
        return "", False
    return f"{text}\n", False


def _parse_result_event(
    payload: dict[str, object], *, saw_partial_assistant: bool
) -> tuple[str, bool]:
    result = payload.get("result")
    if not isinstance(result, str):
        return "", False
    if saw_partial_assistant:
        return "", False
    return f"{result}\n", False
