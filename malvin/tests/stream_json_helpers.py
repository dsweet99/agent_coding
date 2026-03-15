from __future__ import annotations

import json


def assistant_partial(text: str, timestamp: int = 1) -> str:
    payload = {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
        "timestamp_ms": timestamp,
    }
    return f"{json.dumps(payload)}\n"


def assistant_final(text: str) -> str:
    payload = {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }
    return f"{json.dumps(payload)}\n"
