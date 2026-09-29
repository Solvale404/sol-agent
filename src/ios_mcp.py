from __future__ import annotations

import http.client
import json
import threading
from typing import Any, Dict, Optional
from urllib.parse import urlsplit


class IOSMCPError(RuntimeError):
    pass


class IOSMCPClient:
    """Small stdlib MCP client for the phone-local iOS-MCP server."""

    def __init__(self, base_url: str = "http://127.0.0.1:8090", timeout: int = 8):
        parsed = urlsplit(base_url)
        if parsed.scheme != "http" or not parsed.hostname:
            raise IOSMCPError("ios_mcp_url_must_be_http")
        self.host = parsed.hostname
        self.port = parsed.port or 80
        self.base_path = parsed.path.rstrip("/")
        self.timeout = int(timeout)
        self.session_id: Optional[str] = None
        self.request_id = 0
        self.lock = threading.Lock()
        self.conn: Optional[http.client.HTTPConnection] = None

    def _new_connection(self) -> http.client.HTTPConnection:
        self.conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        return self.conn

    def _close(self) -> None:
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
        self.conn = None
        self.session_id = None

    def _request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None,
                 session: bool = False) -> Dict[str, Any]:
        headers = {"Accept": "application/json, text/event-stream"}
        payload: Optional[str] = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        if session and self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        last_error: Optional[Exception] = None
        for attempt in range(2):
            try:
                conn = self.conn or self._new_connection()
                conn.request(method, self.base_path + path, body=payload, headers=headers)
                response = conn.getresponse()
                raw = response.read()
                sid = response.getheader("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                if response.status not in (200, 202):
                    raise IOSMCPError("ios_mcp_http_%s:%s" % (
                        response.status, raw.decode("utf-8", "replace")[:500]))
                if not raw:
                    return {}
                parsed = json.loads(raw.decode("utf-8"))
                if not isinstance(parsed, dict):
                    raise IOSMCPError("ios_mcp_invalid_response")
                return parsed
            except (OSError, http.client.HTTPException, ValueError, IOSMCPError) as exc:
                last_error = exc
                self._close()
                if attempt == 0:
                    continue
        raise IOSMCPError("ios_mcp_request_failed:%s" % last_error)

    def health(self) -> Dict[str, Any]:
        with self.lock:
            result = self._request("GET", "/health")
            if result.get("status") != "ok":
                raise IOSMCPError("ios_mcp_unhealthy")
            return result

    def _initialize_locked(self) -> None:
        if self.session_id:
            return
        self.request_id += 1
        response = self._request("POST", "/mcp", {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "sol-agent", "version": "0.2.0"},
            },
        })
        if response.get("error"):
            raise IOSMCPError("ios_mcp_initialize:%s" % response["error"])
        if not self.session_id:
            raise IOSMCPError("ios_mcp_missing_session")
        self._request("POST", "/mcp", {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }, session=True)

    def call_tool(self, name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        with self.lock:
            for attempt in range(2):
                try:
                    self._initialize_locked()
                    self.request_id += 1
                    response = self._request("POST", "/mcp", {
                        "jsonrpc": "2.0",
                        "id": self.request_id,
                        "method": "tools/call",
                        "params": {"name": name, "arguments": args or {}},
                    }, session=True)
                    if response.get("error"):
                        raise IOSMCPError("ios_mcp_tool:%s" % response["error"])
                    result = response.get("result")
                    if not isinstance(result, dict):
                        return result
                    if result.get("isError"):
                        text = self._text_result(result)
                        raise IOSMCPError("ios_mcp_tool_error:%s" % text[:500])
                    if "structuredContent" in result:
                        return result["structuredContent"]
                    text = self._text_result(result)
                    if text:
                        try:
                            return json.loads(text)
                        except Exception:
                            return {"text": text}
                    return result
                except IOSMCPError:
                    if attempt == 0:
                        self._close()
                        continue
                    raise
        raise IOSMCPError("ios_mcp_tool_failed")

    @staticmethod
    def _text_result(result: Dict[str, Any]) -> str:
        chunks = []
        for item in result.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                chunks.append(item["text"])
        return "\n".join(chunks)
