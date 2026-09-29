from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Any, Callable, Dict, List, Optional

SAFE_NAME = re.compile(r"^[A-Za-z0-9._ -]{1,128}$")
SAFE_APP = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class ActionError(RuntimeError):
    pass


class ActionDispatcher:
    def __init__(self, rc_path: str = "auto", timeout: int = 8,
                 runner: Optional[Callable[[List[str]], Dict[str, Any]]] = None):
        self.timeout = int(timeout)
        self.rc_path = self._find_rc(rc_path)
        self._runner = runner
        self._actions = {
            "system.ping": self._ping,
            "system.status": self._status,
            "system.capabilities": self._capabilities,
            "ui.home": self._home,
            "ui.lock": self._lock,
            "ui.open": self._open,
            "ui.type": self._type,
            "notify.toast": self._toast,
            "device.brightness": self._brightness,
            "device.volume": self._volume,
            "device.flashlight": self._flashlight,
            "device.wifi": self._wifi,
            "device.bluetooth": self._bluetooth,
            "device.dnd": self._dnd,
            "device.low_power": self._low_power,
            "shortcut.run": self._shortcut,
            "query.foreground_app": self._foreground_app,
            "query.locked": self._locked,
        }

    @staticmethod
    def _find_rc(configured: str) -> Optional[str]:
        if configured and configured != "auto":
            return configured
        found = shutil.which("rc")
        if found:
            return found
        for path in (
            "/var/jb/usr/local/bin/rc",
            "/var/jb/usr/bin/rc",
            "/usr/local/bin/rc",
            "/usr/bin/rc",
        ):
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return None

    def manifest(self) -> List[Dict[str, Any]]:
        return [
            {"action": "system.ping", "risk": "read"},
            {"action": "system.status", "risk": "read"},
            {"action": "system.capabilities", "risk": "read"},
            {"action": "ui.home", "risk": "low"},
            {"action": "ui.lock", "risk": "low"},
            {"action": "ui.open", "risk": "low", "args": {"app": "string"}},
            {"action": "ui.type", "risk": "foreground", "args": {"text": "string<=2000"}},
            {"action": "notify.toast", "risk": "low", "args": {"title": "string", "subtitle": "string?"}},
            {"action": "device.brightness", "risk": "low", "args": {"value": "0..100"}},
            {"action": "device.volume", "risk": "low", "args": {"value": "0..100"}},
            {"action": "device.flashlight", "risk": "low", "args": {"state": "on|off|toggle"}},
            {"action": "device.wifi", "risk": "connectivity", "args": {"state": "on|off|toggle"}},
            {"action": "device.bluetooth", "risk": "connectivity", "args": {"state": "on|off|toggle"}},
            {"action": "device.dnd", "risk": "low", "args": {"state": "on|off|toggle"}},
            {"action": "device.low_power", "risk": "low", "args": {"state": "on|off|toggle"}},
            {"action": "shortcut.run", "risk": "delegated", "args": {"name": "string", "input": "string?"}},
            {"action": "query.foreground_app", "risk": "read"},
            {"action": "query.locked", "risk": "read"},
        ]

    def dispatch(self, action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        handler = self._actions.get(action)
        if not handler:
            raise ActionError("unknown_action")
        return handler(args)

    def _run(self, argv: List[str]) -> Dict[str, Any]:
        if self._runner:
            return self._runner(argv)
        if not self.rc_path:
            raise ActionError("remotecompanion_rc_not_found")
        try:
            proc = subprocess.run(
                [self.rc_path] + argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            raise ActionError("rc_timeout")
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[:500]
            raise ActionError("rc_failed:%s:%s" % (proc.returncode, detail))
        return {"stdout": (proc.stdout or "").strip()[:4000]}

    @staticmethod
    def _state(args: Dict[str, Any]) -> str:
        value = args.get("state")
        if value not in ("on", "off", "toggle"):
            raise ActionError("state_must_be_on_off_toggle")
        return value

    @staticmethod
    def _percent(args: Dict[str, Any]) -> int:
        value = args.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ActionError("value_must_be_number")
        value = int(value)
        if value < 0 or value > 100:
            raise ActionError("value_out_of_range")
        return value

    def _ping(self, _: Dict[str, Any]) -> Dict[str, Any]:
        return {"pong": True}

    def _status(self, _: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {"rc_available": bool(self.rc_path), "rootless": os.path.exists("/var/jb")}
        if self.rc_path:
            for key, command in (("foreground_app", ["app"]), ("lock_state", ["is-locked"])):
                try:
                    result[key] = self._run(command).get("stdout")
                except Exception as exc:
                    result[key + "_error"] = str(exc)
        return result

    def _capabilities(self, _: Dict[str, Any]) -> Dict[str, Any]:
        return {"capabilities": self.manifest()}

    def _home(self, _: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(["button", "home"])

    def _lock(self, _: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(["lock"])

    def _open(self, args: Dict[str, Any]) -> Dict[str, Any]:
        app = args.get("app")
        if not isinstance(app, str) or not SAFE_APP.fullmatch(app):
            raise ActionError("invalid_app")
        return self._run(["open", app])

    def _type(self, args: Dict[str, Any]) -> Dict[str, Any]:
        text = args.get("text")
        if not isinstance(text, str) or len(text) > 2000:
            raise ActionError("invalid_text")
        return self._run(["type", text])

    def _toast(self, args: Dict[str, Any]) -> Dict[str, Any]:
        title = args.get("title")
        subtitle = args.get("subtitle", "")
        if not isinstance(title, str) or not title or len(title) > 160:
            raise ActionError("invalid_title")
        if not isinstance(subtitle, str) or len(subtitle) > 240:
            raise ActionError("invalid_subtitle")
        argv = ["toast", title]
        if subtitle:
            argv.append(subtitle)
        return self._run(argv)

    def _brightness(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(["brightness", str(self._percent(args))])

    def _volume(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(["volume", str(self._percent(args))])

    def _flashlight(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(["flashlight", self._state(args)])

    def _wifi(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(["wifi", self._state(args)])

    def _bluetooth(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(["bluetooth", self._state(args)])

    def _dnd(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(["dnd", self._state(args)])

    def _low_power(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(["lpm", self._state(args)])

    def _shortcut(self, args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("name")
        value = args.get("input")
        if not isinstance(name, str) or not SAFE_NAME.fullmatch(name):
            raise ActionError("invalid_shortcut_name")
        argv = ["shortcut", "-r", name]
        if value is not None:
            if not isinstance(value, str) or len(value) > 2000:
                raise ActionError("invalid_shortcut_input")
            argv += ["-p", value]
        return self._run(argv)

    def _foreground_app(self, _: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(["app"])

    def _locked(self, _: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(["is-locked"])
