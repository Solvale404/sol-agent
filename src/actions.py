from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional

from ios_mcp import IOSMCPClient

SAFE_NAME = re.compile(r"^[A-Za-z0-9._ -]{1,128}$")
SAFE_APP = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

APP_ALIASES = {
    "calculator": "com.apple.calculator",
    "camera": "com.apple.camera",
    "files": "com.apple.DocumentsApp",
    "home": "com.apple.Home",
    "mail": "com.apple.mobilemail",
    "maps": "com.apple.Maps",
    "messages": "com.apple.MobileSMS",
    "music": "com.apple.Music",
    "notes": "com.apple.mobilenotes",
    "photos": "com.apple.mobileslideshow",
    "reminders": "com.apple.reminders",
    "safari": "com.apple.mobilesafari",
    "settings": "com.apple.Preferences",
    "shortcuts": "com.apple.shortcuts",
}

ACTION_META: Dict[str, Dict[str, Any]] = {
    "system.ping": {"risk": "read"},
    "system.status": {"risk": "read"},
    "system.capabilities": {"risk": "read"},
    "ui.home": {"risk": "low"},
    "ui.lock": {"risk": "low"},
    "ui.open": {"risk": "low", "args": {"app": "alias|bundle_id"}},
    "ui.type": {"risk": "foreground", "args": {"text": "string<=2000"}},
    "notify.toast": {"risk": "low", "args": {"title": "string", "subtitle": "string?"}},
    "device.brightness": {"risk": "low", "args": {"value": "0..100"}},
    "device.volume": {"risk": "low", "args": {"value": "0..100"}},
    "device.flashlight": {"risk": "low", "args": {"state": "on|off|toggle"}},
    "device.wifi": {"risk": "connectivity", "args": {"state": "on|off|toggle"}},
    "device.bluetooth": {"risk": "connectivity", "args": {"state": "on|off|toggle"}},
    "device.dnd": {"risk": "low", "args": {"state": "on|off|toggle"}},
    "device.low_power": {"risk": "low", "args": {"state": "on|off|toggle"}},
    "shortcut.run": {"risk": "delegated", "args": {"name": "string", "input": "string?"}},
    "query.foreground_app": {"risk": "read"},
    "query.locked": {"risk": "read"},
}


class ActionError(RuntimeError):
    pass


class ActionDispatcher:
    def __init__(self, rc_path: str = "auto", timeout: int = 8,
                 runner: Optional[Callable[[List[str]], Dict[str, Any]]] = None,
                 driver: str = "auto", ios_mcp_url: str = "http://127.0.0.1:8090",
                 mcp_client: Optional[Any] = None):
        self.timeout = int(timeout)
        self._runner = runner
        if driver == "auto":
            driver = "remotecompanion" if runner is not None else "ios_mcp"
        if driver not in ("ios_mcp", "remotecompanion"):
            raise ActionError("unsupported_device_driver")
        self.driver = driver
        self.rc_path = self._find_rc(rc_path) if driver == "remotecompanion" else None
        self.mcp = (mcp_client or IOSMCPClient(ios_mcp_url, timeout=self.timeout)) if driver == "ios_mcp" else None

        common = {
            "system.ping": self._ping,
            "system.status": self._status,
            "system.capabilities": self._capabilities,
        }
        if driver == "ios_mcp":
            specific = {
                "ui.home": self._home,
                "ui.lock": self._lock,
                "ui.open": self._open,
                "ui.type": self._type,
                "device.brightness": self._brightness,
                "device.volume": self._volume,
                "query.foreground_app": self._foreground_app,
                "query.locked": self._locked,
            }
        else:
            specific = {
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
        self._actions = dict(common)
        self._actions.update(specific)

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
        manifest = []
        for name in self._actions:
            meta = dict(ACTION_META[name])
            meta["action"] = name
            meta["driver"] = self.driver if name not in ("system.ping", "system.capabilities") else "agent"
            manifest.append(meta)
        return manifest

    def available(self) -> bool:
        if self.driver == "ios_mcp":
            try:
                return bool(self.mcp and self.mcp.health().get("status") == "ok")
            except Exception:
                return False
        return bool(self._runner or self.rc_path)

    def dispatch(self, action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        handler = self._actions.get(action)
        if not handler:
            raise ActionError("unknown_action")
        return handler(args)

    def _run_rc(self, argv: List[str]) -> Dict[str, Any]:
        if self._runner:
            return self._runner(argv)
        if not self.rc_path:
            raise ActionError("remotecompanion_rc_not_found")
        env = os.environ.copy()
        if os.path.exists("/var/jb"):
            env.setdefault("RC_IPHONE_IP", "127.0.0.1")
        try:
            proc = subprocess.run(
                [self.rc_path] + argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout,
                shell=False,
                env=env,
            )
        except subprocess.TimeoutExpired:
            raise ActionError("rc_timeout")
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[:500]
            raise ActionError("rc_failed:%s:%s" % (proc.returncode, detail))
        return {"stdout": (proc.stdout or "").strip()[:4000]}

    def _mcp(self, tool: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.mcp:
            raise ActionError("ios_mcp_not_configured")
        try:
            return {"tool": tool, "result": self.mcp.call_tool(tool, args or {})}
        except Exception as exc:
            raise ActionError("ios_mcp_failed:%s" % str(exc)[:500])

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

    @staticmethod
    def _bundle_id(app: Any) -> str:
        if not isinstance(app, str) or not SAFE_APP.fullmatch(app):
            raise ActionError("invalid_app")
        if "." in app:
            return app
        bundle = APP_ALIASES.get(app.lower())
        if not bundle:
            raise ActionError("unknown_app_alias")
        return bundle

    def _ping(self, _: Dict[str, Any]) -> Dict[str, Any]:
        return {"pong": True}

    def _status(self, _: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "driver": self.driver,
            "control_available": self.available(),
            "rootless": os.path.exists("/var/jb"),
        }
        if self.driver == "ios_mcp" and self.mcp:
            try:
                result["ios_mcp"] = self.mcp.health()
                result["foreground_app"] = self.mcp.call_tool("get_frontmost_app", {})
                result["screen"] = self.mcp.call_tool("get_screen_info", {})
            except Exception as exc:
                result["control_error"] = str(exc)
        elif self.driver == "remotecompanion" and (self._runner or self.rc_path):
            for key, command in (("foreground_app", ["app"]), ("lock_state", ["is-locked"])):
                try:
                    result[key] = self._run_rc(command).get("stdout")
                except Exception as exc:
                    result[key + "_error"] = str(exc)
        return result

    def _capabilities(self, _: Dict[str, Any]) -> Dict[str, Any]:
        return {"capabilities": self.manifest()}

    def _home(self, _: Dict[str, Any]) -> Dict[str, Any]:
        if self.driver == "ios_mcp":
            return self._mcp("press_home", {"duration": 100})
        return self._run_rc(["button", "home"])

    def _lock(self, _: Dict[str, Any]) -> Dict[str, Any]:
        if self.driver == "ios_mcp":
            if not self.mcp:
                raise ActionError("ios_mcp_not_configured")
            before = self.mcp.call_tool("get_screen_info", {})
            if isinstance(before, dict) and before.get("locked") is True:
                return {"already_locked": True, "screen": before}
            self.mcp.call_tool("press_power", {"duration": 100})
            time.sleep(0.2)
            after = self.mcp.call_tool("get_screen_info", {})
            if not isinstance(after, dict) or after.get("locked") is not True:
                raise ActionError("lock_verification_failed")
            return {"locked": True, "screen": after}
        return self._run_rc(["lock"])

    def _open(self, args: Dict[str, Any]) -> Dict[str, Any]:
        app = args.get("app")
        if self.driver == "ios_mcp":
            return self._mcp("launch_app", {"bundle_id": self._bundle_id(app)})
        if not isinstance(app, str) or not SAFE_APP.fullmatch(app):
            raise ActionError("invalid_app")
        return self._run_rc(["open", app])

    def _type(self, args: Dict[str, Any]) -> Dict[str, Any]:
        text = args.get("text")
        if not isinstance(text, str) or len(text) > 2000:
            raise ActionError("invalid_text")
        if self.driver == "ios_mcp":
            return self._mcp("input_text", {"text": text})
        return self._run_rc(["type", text])

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
        return self._run_rc(argv)

    def _brightness(self, args: Dict[str, Any]) -> Dict[str, Any]:
        value = self._percent(args)
        if self.driver == "ios_mcp":
            return self._mcp("set_brightness", {"level": value / 100.0})
        return self._run_rc(["brightness", str(value)])

    def _volume(self, args: Dict[str, Any]) -> Dict[str, Any]:
        value = self._percent(args)
        if self.driver == "ios_mcp":
            return self._mcp("set_volume", {"level": value / 100.0})
        return self._run_rc(["volume", str(value)])

    def _flashlight(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._run_rc(["flashlight", self._state(args)])

    def _wifi(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._run_rc(["wifi", self._state(args)])

    def _bluetooth(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._run_rc(["bluetooth", self._state(args)])

    def _dnd(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._run_rc(["dnd", self._state(args)])

    def _low_power(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._run_rc(["lpm", self._state(args)])

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
        return self._run_rc(argv)

    def _foreground_app(self, _: Dict[str, Any]) -> Dict[str, Any]:
        if self.driver == "ios_mcp":
            return self._mcp("get_frontmost_app", {})
        return self._run_rc(["app"])

    def _locked(self, _: Dict[str, Any]) -> Dict[str, Any]:
        if self.driver == "ios_mcp":
            return self._mcp("get_screen_info", {})
        return self._run_rc(["is-locked"])
