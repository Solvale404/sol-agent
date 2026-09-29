from __future__ import annotations

import socket
import struct
import threading
import time
from typing import Optional, Tuple


class MQTTError(RuntimeError):
    pass


def _pack_str(value: str) -> bytes:
    raw = value.encode("utf-8")
    if len(raw) > 65535:
        raise MQTTError("mqtt_string_too_long")
    return struct.pack("!H", len(raw)) + raw


def _remaining_length(value: int) -> bytes:
    out = bytearray()
    while True:
        digit = value % 128
        value //= 128
        if value:
            digit |= 0x80
        out.append(digit)
        if not value:
            return bytes(out)


class MQTTClient:
    """Tiny MQTT 3.1.1 QoS-0 client using only Python stdlib."""

    def __init__(self, host: str, port: int, client_id: str, username: Optional[str] = None,
                 password: Optional[str] = None, keepalive: int = 30, timeout: float = 5.0,
                 will_topic: Optional[str] = None, will_payload: str = "offline"):
        self.host = host
        self.port = int(port)
        self.client_id = client_id
        self.username = username
        self.password = password
        self.keepalive = int(keepalive)
        self.timeout = float(timeout)
        self.will_topic = will_topic
        self.will_payload = will_payload
        self.sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._packet_id = 0
        self.last_io = 0.0

    @property
    def connected(self) -> bool:
        return self.sock is not None

    def _next_packet_id(self) -> int:
        self._packet_id = (self._packet_id % 65535) + 1
        return self._packet_id

    def connect(self) -> None:
        self.close()
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(1.0)

        flags = 0x02  # clean session
        payload = bytearray(_pack_str(self.client_id))
        if self.will_topic:
            flags |= 0x04 | 0x20  # will flag + retain, QoS 0
            payload += _pack_str(self.will_topic)
            payload += _pack_str(self.will_payload)
        if self.username is not None:
            flags |= 0x80
            payload += _pack_str(self.username)
        if self.password is not None:
            flags |= 0x40
            payload += _pack_str(self.password)

        variable = _pack_str("MQTT") + bytes([4, flags]) + struct.pack("!H", self.keepalive)
        packet = bytes([0x10]) + _remaining_length(len(variable) + len(payload)) + variable + payload
        sock.sendall(packet)
        self.sock = sock
        packet_type, body = self.read_packet(timeout=self.timeout)
        if packet_type != 2 or len(body) != 2 or body[1] != 0:
            code = body[1] if len(body) > 1 else -1
            self.close()
            raise MQTTError("connack_failed_%s" % code)
        self.last_io = time.time()

    def close(self) -> None:
        sock, self.sock = self.sock, None
        if sock:
            try:
                sock.close()
            except Exception:
                pass

    def _recv_exact(self, count: int, timeout: Optional[float] = None) -> bytes:
        if not self.sock:
            raise MQTTError("not_connected")
        if timeout is not None:
            self.sock.settimeout(timeout)
        data = bytearray()
        while len(data) < count:
            chunk = self.sock.recv(count - len(data))
            if not chunk:
                raise MQTTError("connection_closed")
            data += chunk
        self.last_io = time.time()
        return bytes(data)

    def read_packet(self, timeout: float = 1.0) -> Tuple[int, bytes]:
        if not self.sock:
            raise MQTTError("not_connected")
        self.sock.settimeout(timeout)
        first = self._recv_exact(1, timeout)[0]
        multiplier, remaining = 1, 0
        for _ in range(4):
            digit = self._recv_exact(1, timeout)[0]
            remaining += (digit & 0x7F) * multiplier
            if not digit & 0x80:
                break
            multiplier *= 128
        else:
            raise MQTTError("malformed_remaining_length")
        return first >> 4, self._recv_exact(remaining, timeout) if remaining else b""

    def publish(self, topic: str, payload: str, retain: bool = False) -> None:
        if not self.sock:
            raise MQTTError("not_connected")
        body = _pack_str(topic) + payload.encode("utf-8")
        header = 0x30 | (0x01 if retain else 0)
        packet = bytes([header]) + _remaining_length(len(body)) + body
        with self._lock:
            self.sock.sendall(packet)
            self.last_io = time.time()

    def subscribe(self, topic: str) -> None:
        if not self.sock:
            raise MQTTError("not_connected")
        packet_id = self._next_packet_id()
        body = struct.pack("!H", packet_id) + _pack_str(topic) + b"\x00"
        packet = b"\x82" + _remaining_length(len(body)) + body
        with self._lock:
            self.sock.sendall(packet)
            self.last_io = time.time()
        packet_type, response = self.read_packet(timeout=self.timeout)
        if packet_type != 9 or len(response) < 3 or response[:2] != struct.pack("!H", packet_id):
            raise MQTTError("suback_failed")
        if response[2] == 0x80:
            raise MQTTError("subscription_rejected")

    def ping(self) -> None:
        if not self.sock:
            raise MQTTError("not_connected")
        with self._lock:
            self.sock.sendall(b"\xC0\x00")
            self.last_io = time.time()

    @staticmethod
    def decode_publish(body: bytes) -> Tuple[str, bytes]:
        if len(body) < 2:
            raise MQTTError("malformed_publish")
        topic_len = struct.unpack("!H", body[:2])[0]
        if len(body) < 2 + topic_len:
            raise MQTTError("malformed_publish")
        topic = body[2:2 + topic_len].decode("utf-8")
        return topic, body[2 + topic_len:]
