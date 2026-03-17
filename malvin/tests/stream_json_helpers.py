from __future__ import annotations

import json


def _assistant_message(text: str, timestamp: int | None = None) -> str:
    payload: dict = {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }
    if timestamp is not None:
        payload["timestamp_ms"] = timestamp
    return f"{json.dumps(payload)}\n"


def assistant_partial(text: str, timestamp: int = 1) -> str:
    return _assistant_message(text, timestamp)


def assistant_final(text: str) -> str:
    return _assistant_message(text)
