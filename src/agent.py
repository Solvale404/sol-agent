#!/var/jb/usr/bin/python3
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sqlite3
import sys
import threading
import time
from typing import Any, Dict, Optional

from actions import ActionDispatcher
from mqtt_client import MQTTClient, MQTTError
from protocol import ProtocolError, ack, decode_command, dumps, validate_command

VERSION = "0.1.0"


class CommandStore:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS commands ("
            "id TEXT PRIMARY KEY, action TEXT NOT NULL, status TEXT NOT NULL, "
            "ack_json TEXT NOT NULL, updated_at REAL NOT NULL)"
        )
        self.db.commit()

    def get(self, command_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            row = self.db.execute("SELECT ack_json FROM commands WHERE id=?", (command_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, body: Dict[str, Any]) -> None:
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO commands(id,action,status,ack_json,updated_at) VALUES(?,?,?,?,?)",
                (body["id"], body.get("action", "unknown"), body["status"], dumps(body), time.time()),
            )
            self.db.commit()

    def recover_inflight(self) -> int:
        with self.lock:
            rows = self.db.execute(
                "SELECT id,action FROM commands WHERE status IN ('accepted','running')"
            ).fetchall()
            for command_id, action in rows:
                body = ack(command_id, action, "error", error="agent_restarted_before_completion")
                self.db.execute(
                    "UPDATE commands SET status='error',ack_json=?,updated_at=? WHERE id=?",
                    (dumps(body), time.time(), command_id),
                )
            self.db.commit()
        return len(rows)

    def prune(self, max_age: int = 86400) -> None:
        with self.lock:
            self.db.execute("DELETE FROM commands WHERE updated_at < ?", (time.time() - max_age,))
            self.db.commit()


class SolAgent:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.started_at = time.time()
        self.stop_event = threading.Event()
        self.action_lock = threading.Lock()
        self.mqtt: Optional[MQTTClient] = None
        self.last_command_id: Optional[str] = None
        self.last_error: Optional[str] = None

        self.data_dir = config["data_dir"]
        self.socket_path = config["socket_path"]
        os.makedirs(self.data_dir, exist_ok=True)
        self.store = CommandStore(os.path.join(self.data_dir, "commands.db"))
        self.store.recover_inflight()
        self.store.prune()

        self.dispatcher = ActionDispatcher(
            config.get("rc_path", "auto"),
            int(config.get("action_timeout", 8)),
        )
        self.audit_path = os.path.join(self.data_dir, "audit.jsonl")
        self.audit_enabled = bool(config.get("audit_log", True))

        mqtt_cfg = config["mqtt"]
        self.prefix = mqtt_cfg.get("topic_prefix", "sol/v1").rstrip("/")
        self.cmd_topic = self.prefix + "/cmd"
        self.availability_topic = self.prefix + "/availability"
        self.status_topic = self.prefix + "/status"
        self.capabilities_topic = self.prefix + "/capabilities"
        self.events_topic = self.prefix + "/events"

    def audit(self, event: str, **fields: Any) -> None:
        if not self.audit_enabled:
            return
        record = {"ts": time.time(), "event": event}
        record.update(fields)
        try:
            with open(self.audit_path, "a", encoding="utf-8") as handle:
                handle.write(dumps(record) + "\n")
        except Exception:
            pass

    def status(self) -> Dict[str, Any]:
        return {
            "v": 1,
            "name": self.config.get("device_name", "Sol"),
            "agent_version": VERSION,
            "online": True,
            "uptime_s": int(time.time() - self.started_at),
            "pid": os.getpid(),
            "python": sys.version.split()[0],
            "rootless": os.path.exists("/var/jb"),
            "rc_available": bool(self.dispatcher.rc_path),
            "mqtt_connected": bool(self.mqtt and self.mqtt.connected),
            "last_command_id": self.last_command_id,
            "last_error": self.last_error,
        }

    def capabilities(self) -> Dict[str, Any]:
        return {
            "v": 1,
            "agent_version": VERSION,
            "generated_at": time.time(),
            "actions": self.dispatcher.manifest(),
        }

    def publish(self, topic: str, body: Any, retain: bool = False) -> bool:
        client = self.mqtt
        if not client or not client.connected:
            return False
        try:
            payload = body if isinstance(body, str) else dumps(body)
            client.publish(topic, payload, retain=retain)
            return True
        except Exception as exc:
            self.last_error = "publish:%s" % exc
            return False

    def publish_ack(self, body: Dict[str, Any]) -> None:
        self.publish(self.prefix + "/ack/" + body["id"], body, retain=False)

    def reject_event(self, error: str) -> None:
        self.publish(self.events_topic, {"v": 1, "type": "command_rejected", "error": error, "ts": time.time()})
        self.audit("command_rejected", error=error)

    def handle_command(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        try:
            cmd, expired = validate_command(raw)
        except ProtocolError as exc:
            self.reject_event(str(exc))
            return {"v": 1, "status": "error", "error": str(exc)}

        command_id = cmd["id"]
        action = cmd["action"]
        self.last_command_id = command_id

        prior = self.store.get(command_id)
        if prior:
            self.publish_ack(prior)
            self.audit("command_duplicate", id=command_id, action=action, prior_status=prior.get("status"))
            return prior

        if expired:
            final = ack(command_id, action, "expired", error="command_ttl_expired")
            self.store.put(final)
            self.publish_ack(final)
            self.audit("command_expired", id=command_id, action=action, source=cmd["source"])
            return final

        accepted = ack(command_id, action, "accepted")
        self.store.put(accepted)
        self.publish_ack(accepted)
        running = ack(command_id, action, "running")
        self.store.put(running)
        self.publish_ack(running)
        self.audit("command_running", id=command_id, action=action, source=cmd["source"])

        try:
            with self.action_lock:
                result = self.dispatcher.dispatch(action, cmd["args"])
            final = ack(command_id, action, "ok", result=result)
            self.last_error = None
        except Exception as exc:
            error = str(exc)[:1000]
            final = ack(command_id, action, "error", error=error)
            self.last_error = "%s:%s" % (action, error)

        self.store.put(final)
        self.publish_ack(final)
        self.audit("command_final", id=command_id, action=action, status=final["status"], source=cmd["source"])
        return final

    def _read_local_request(self, conn: socket.socket) -> bytes:
        data = bytearray()
        while len(data) < 65536:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in chunk:
                break
        return bytes(data).split(b"\n", 1)[0]

    def _serve_local_connection(self, conn: socket.socket) -> None:
        try:
            payload = self._read_local_request(conn)
            raw = json.loads(payload.decode("utf-8"))
            response = self.handle_command(raw)
        except Exception as exc:
            response = {"v": 1, "status": "error", "error": "local_request:%s" % exc}
        try:
            conn.sendall((dumps(response) + "\n").encode("utf-8"))
        finally:
            conn.close()

    def local_socket_loop(self) -> None:
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(self.socket_path)
            os.chmod(self.socket_path, 0o600)
            server.listen(4)
            server.settimeout(1.0)
        except Exception as exc:
            self.last_error = "local_socket:%s" % exc
            self.audit("local_socket_failed", error=str(exc))
            return

        self.audit("local_socket_ready", path=self.socket_path)
        while not self.stop_event.is_set():
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._serve_local_connection, args=(conn,), daemon=True).start()
        server.close()
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except Exception:
            pass

    def mqtt_loop(self) -> None:
        cfg = self.config["mqtt"]
        reconnect_delay = max(1, int(cfg.get("reconnect_delay", 3)))
        status_interval = max(5, int(self.config.get("status_interval", 30)))

        while not self.stop_event.is_set():
            client = MQTTClient(
                cfg["host"],
                int(cfg.get("port", 1883)),
                cfg.get("client_id", "sol-phone-agent"),
                cfg.get("username"),
                cfg.get("password"),
                int(cfg.get("keepalive", 30)),
                will_topic=self.availability_topic,
                will_payload="offline",
            )
            self.mqtt = client
            try:
                client.connect()
                client.subscribe(self.cmd_topic)
                client.publish(self.availability_topic, "online", retain=True)
                client.publish(self.capabilities_topic, dumps(self.capabilities()), retain=True)
                client.publish(self.status_topic, dumps(self.status()), retain=True)
                self.audit("mqtt_connected", host=cfg["host"])
                self.last_error = None
                last_status = 0.0

                while not self.stop_event.is_set():
                    now = time.time()
                    if now - last_status >= status_interval:
                        client.publish(self.status_topic, dumps(self.status()), retain=True)
                        last_status = now
                    if now - client.last_io >= max(5, client.keepalive // 2):
                        client.ping()

                    try:
                        packet_type, body = client.read_packet(timeout=1.0)
                    except socket.timeout:
                        continue

                    if packet_type == 3:
                        topic, payload = client.decode_publish(body)
                        if topic == self.cmd_topic:
                            try:
                                self.handle_command(decode_command(payload))
                            except ProtocolError as exc:
                                self.reject_event(str(exc))
                    elif packet_type in (13,):
                        pass
            except (OSError, MQTTError, ValueError) as exc:
                self.last_error = "mqtt:%s" % exc
                self.audit("mqtt_disconnected", error=str(exc))
            except Exception as exc:
                self.last_error = "mqtt_unexpected:%s" % exc
                self.audit("mqtt_unexpected", error=str(exc))
            finally:
                client.close()
                self.mqtt = None

            if not self.stop_event.wait(reconnect_delay):
                continue

    def run(self) -> None:
        threading.Thread(target=self.local_socket_loop, name="sol-local", daemon=True).start()
        self.audit("agent_started", version=VERSION)
        self.mqtt_loop()

    def stop(self) -> None:
        self.stop_event.set()
        client = self.mqtt
        if client and client.connected:
            try:
                client.publish(self.availability_topic, "offline", retain=True)
            except Exception:
                pass
            client.close()
        self.audit("agent_stopped")


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        config = json.load(handle)
    required = ("data_dir", "socket_path", "mqtt")
    for key in required:
        if key not in config:
            raise ValueError("missing_config:%s" % key)
    for key in ("host",):
        if key not in config["mqtt"]:
            raise ValueError("missing_mqtt_config:%s" % key)
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description="Sol phone resident control agent")
    parser.add_argument("--config", default=os.environ.get("SOL_AGENT_CONFIG", "/var/jb/var/mobile/SolAgentNext/config.json"))
    args = parser.parse_args()

    agent = SolAgent(load_config(args.config))

    def shutdown(_signum: int, _frame: Any) -> None:
        agent.stop()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    agent.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
