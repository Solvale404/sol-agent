#!/var/jb/usr/bin/python3
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import uuid
from typing import Any, Dict

DEFAULT_SOCKET = "/var/jb/var/mobile/SolAgentNext/runtime/agent.sock"


def command(action: str, args: Dict[str, Any], ttl: int = 30) -> Dict[str, Any]:
    return {
        "v": 1,
        "id": "solctl-%s" % uuid.uuid4().hex,
        "action": action,
        "args": args,
        "sent_at": time.time(),
        "ttl": ttl,
        "source": "solctl",
    }


def send(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(15)
    sock.connect(path)
    sock.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))
    data = bytearray()
    while len(data) < 65536:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
        if b"\n" in chunk:
            break
    sock.close()
    return json.loads(bytes(data).split(b"\n", 1)[0].decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Local/rescue CLI for Sol Agent")
    parser.add_argument("--socket", default=os.environ.get("SOL_AGENT_SOCKET", DEFAULT_SOCKET))
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    sub.add_parser("caps")
    sub.add_parser("home")
    sub.add_parser("lock")

    p_open = sub.add_parser("open")
    p_open.add_argument("app")

    p_type = sub.add_parser("type")
    p_type.add_argument("text")

    p_toast = sub.add_parser("toast")
    p_toast.add_argument("title")
    p_toast.add_argument("subtitle", nargs="?", default="")

    p_flash = sub.add_parser("flashlight")
    p_flash.add_argument("state", choices=("on", "off", "toggle"))

    p_run = sub.add_parser("run")
    p_run.add_argument("action")
    p_run.add_argument("args_json", nargs="?", default="{}")

    args = parser.parse_args()
    if args.cmd == "status":
        payload = command("system.status", {})
    elif args.cmd == "caps":
        payload = command("system.capabilities", {})
    elif args.cmd == "home":
        payload = command("ui.home", {})
    elif args.cmd == "lock":
        payload = command("ui.lock", {})
    elif args.cmd == "open":
        payload = command("ui.open", {"app": args.app})
    elif args.cmd == "type":
        payload = command("ui.type", {"text": args.text})
    elif args.cmd == "toast":
        payload = command("notify.toast", {"title": args.title, "subtitle": args.subtitle})
    elif args.cmd == "flashlight":
        payload = command("device.flashlight", {"state": args.state})
    else:
        parsed = json.loads(args.args_json)
        if not isinstance(parsed, dict):
            raise SystemExit("args_json must decode to an object")
        payload = command(args.action, parsed)

    try:
        response = send(args.socket, payload)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    print(json.dumps(response, indent=2, ensure_ascii=False))
    return 0 if response.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
