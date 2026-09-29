from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, Tuple

ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
ACTION_RE = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
FINAL_STATUSES = {"ok", "error", "expired"}


class ProtocolError(ValueError):
    pass


def decode_command(payload: bytes) -> Dict[str, Any]:
    try:
        obj = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise ProtocolError(f"invalid_json: {exc}")
    if not isinstance(obj, dict):
        raise ProtocolError("command_must_be_object")
    return obj


def validate_command(cmd: Dict[str, Any], now: float | None = None) -> Tuple[Dict[str, Any], bool]:
    now = time.time() if now is None else now
    if cmd.get("v") != 1:
        raise ProtocolError("unsupported_version")

    command_id = cmd.get("id")
    if not isinstance(command_id, str) or not ID_RE.fullmatch(command_id):
        raise ProtocolError("invalid_id")

    action = cmd.get("action")
    if not isinstance(action, str) or not ACTION_RE.fullmatch(action):
        raise ProtocolError("invalid_action")

    args = cmd.get("args", {})
    if not isinstance(args, dict):
        raise ProtocolError("args_must_be_object")

    sent_at = cmd.get("sent_at")
    if not isinstance(sent_at, (int, float)):
        raise ProtocolError("invalid_sent_at")

    ttl = cmd.get("ttl", 30)
    if not isinstance(ttl, (int, float)) or ttl < 1 or ttl > 300:
        raise ProtocolError("invalid_ttl")

    source = cmd.get("source", "unknown")
    if not isinstance(source, str) or len(source) > 128:
        raise ProtocolError("invalid_source")

    normalized = {
        "v": 1,
        "id": command_id,
        "action": action,
        "args": args,
        "sent_at": float(sent_at),
        "ttl": float(ttl),
        "source": source,
    }
    expired = now > normalized["sent_at"] + normalized["ttl"]
    return normalized, expired


def ack(command_id: str, action: str, status: str, *, result: Any = None, error: str | None = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "v": 1,
        "id": command_id,
        "status": status,
        "action": action,
        "result": result,
        "error": error,
        "finished_at": time.time() if status in FINAL_STATUSES else None,
    }
    return body


def dumps(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
