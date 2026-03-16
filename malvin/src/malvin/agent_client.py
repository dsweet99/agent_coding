from __future__ import annotations

import os
import random
import string
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .agent_stream import stream_command as _stream_command_raw

CREATE_CHAT_TIMEOUT_SECONDS = 30.0


class AgentError(RuntimeError):
    pass


class AuthError(AgentError):
    pass


@dataclass(frozen=True)
class AgentResult:
    output: str
    exit_code: int


@dataclass(frozen=True)
class AgentClient:
    model: str
    force: bool = True
    tee: bool = False
    tee_json: bool = False
    retries: int = 3
    style_prompt_path: Path = field(default_factory=lambda: Path(".style") / "main.md")
    run_suffix: str = field(default_factory=lambda: _random_suffix())
    session_chats: dict[str, str] = field(default_factory=dict)

    def ensure_authenticated(self) -> None:
        if _has_api_key():
            return
        if _auth_probe(["cursor-agent", "auth", "status"]):
            return
        if _auth_probe(["agent", "whoami"]):
            return
        raise AuthError(
            "cursor-agent is not authenticated. Run `agent login` or set CURSOR_AGENT_API_KEY."
        )

    def run_session_prompt(
        self,
        *,
        session: str,
        prompt: str,
        cwd: Path,
        log_path: Path,
    ) -> AgentResult:
        scoped_session = f"{session}_{self.run_suffix}"
        chat_id = self.session_chats.get(scoped_session)
        first_prompt = chat_id is None
        if chat_id is None:
            chat_id = _create_chat(scoped_session)
            self.session_chats[scoped_session] = chat_id
        if first_prompt:
            try:
                style_text = self.style_prompt_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                style_text = ""
            except OSError as exc:
                raise AgentError(
                    f"Failed to read style prompt file {self.style_prompt_path}: {exc}"
                ) from exc
            style_text = style_text.strip()
            if style_text:
                prompt = f"{style_text}\n\n{prompt}"
        command = _build_command(model=self.model, force=self.force, chat_id=chat_id)
        return self._run_with_retries(
            command=command,
            prompt=prompt,
            cwd=cwd,
            log_path=log_path,
        )

    def _run_with_retries(
        self,
        *,
        command: list[str],
        prompt: str,
        cwd: Path,
        log_path: Path,
    ) -> AgentResult:
        attempt = 0
        delay = 1.0
        last_error = ""
        tee_mode = "json" if self.tee_json else ("text" if self.tee else "off")
        while attempt <= self.retries:
            attempt += 1
            result = _stream_command(
                command=command,
                prompt=prompt,
                cwd=cwd,
                log_path=log_path,
                tee_mode=tee_mode,
            )
            if result.exit_code == 0:
                return result
            last_error = result.output
            if attempt > self.retries:
                break
            time.sleep(delay)
            delay = min(delay * 2, 8.0)
        raise AgentError(f"cursor-agent failed after retries. Last output:\n{last_error}")


def _build_command(*, model: str, force: bool, chat_id: str) -> list[str]:
    command = [
        "cursor-agent",
        "--model",
        model,
        "--resume",
        chat_id,
        "--trust",
        "--print",
        "--output-format",
        "stream-json",
        "--stream-partial-output",
    ]
    if force:
        command.append("--force")
    return command


def _random_suffix(length: int = 6) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def _create_chat(session_id: str) -> str:
    def first_non_empty_line(raw_output: str | bytes | None) -> str:
        if raw_output is None:
            return ""
        if isinstance(raw_output, bytes):
            text = raw_output.decode("utf-8", errors="ignore")
        else:
            text = raw_output
        for line in text.splitlines():
            candidate = line.strip()
            if candidate:
                return candidate
        return ""

    try:
        completed = subprocess.run(
            ["cursor-agent", "create-chat"],
            capture_output=True,
            text=True,
            check=False,
            timeout=CREATE_CHAT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        chat_id = first_non_empty_line(exc.stdout)
        if chat_id:
            return chat_id
        raise AgentError(
            f"Failed to initialize cursor-agent chat for {session_id}: timed out after "
            f"{CREATE_CHAT_TIMEOUT_SECONDS:.0f}s."
        ) from exc
    except OSError as exc:
        raise AgentError(f"Failed to initialize cursor-agent chat for {session_id}: {exc}") from exc
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout).strip()
        if not message:
            message = "Unknown error."
        raise AgentError(f"Failed to initialize cursor-agent chat for {session_id}: {message}")
    chat_id = first_non_empty_line(completed.stdout)
    if not chat_id:
        raise AgentError(f"Failed to initialize cursor-agent chat for {session_id}: empty chat id.")
    return chat_id


def _has_api_key() -> bool:
    keys = ("CURSOR_AGENT_API_KEY", "CURSOR_API_KEY", "AGENT_API_KEY")
    return any(os.getenv(key) for key in keys)


def _auth_probe(command: list[str]) -> bool:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return completed.returncode == 0


def _stream_command(
    *,
    command: list[str],
    prompt: str,
    cwd: Path,
    log_path: Path,
    tee_mode: str = "off",
) -> AgentResult:
    try:
        output, exit_code = _stream_command_raw(
            command=command,
            prompt=prompt,
            cwd=cwd,
            log_path=log_path,
            tee_mode=tee_mode,
        )
    except OSError as exc:
        raise AgentError(f"cursor-agent execution failed: {exc}") from exc
    return AgentResult(output=output, exit_code=exit_code)
