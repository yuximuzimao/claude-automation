from __future__ import annotations

import base64
import os
import json
import socket
import struct
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


CHROME_PORT = 9222
EVAL_TIMEOUT_SECONDS = 125


class CdpError(RuntimeError):
    pass


def list_targets(chrome_port: int = CHROME_PORT) -> list[dict[str, Any]]:
    return _request_json(f"http://localhost:{chrome_port}/json")


def eval_js(
    target_id: str,
    js_code: str,
    chrome_port: int = CHROME_PORT,
    timeout: int = EVAL_TIMEOUT_SECONDS,
) -> Any:
    data = cdp_call(
        target_id,
        "Runtime.evaluate",
        {
            "expression": js_code,
            "awaitPromise": True,
            "returnByValue": True,
        },
        chrome_port=chrome_port,
        timeout=timeout,
    )
    return _extract_eval_value(data)


def cdp_call(
    target_id: str,
    method: str,
    params: dict[str, Any] | None = None,
    chrome_port: int = CHROME_PORT,
    timeout: int = 30,
) -> dict[str, Any]:
    command_id = int.from_bytes(os.urandom(4), "big") % 100000
    payload = {"id": command_id, "method": method, "params": params or {}}
    with socket.create_connection(("localhost", chrome_port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        _websocket_handshake(sock, chrome_port, f"/devtools/page/{target_id}")
        _send_ws_json(sock, payload)
        while True:
            message = _recv_ws_json(sock)
            if message.get("id") != command_id:
                continue
            if message.get("error"):
                raise CdpError(message["error"].get("message") or json.dumps(message["error"], ensure_ascii=False))
            return message.get("result", {})


def _extract_eval_value(data: dict[str, Any]) -> Any:
    if data.get("exceptionDetails"):
        raise CdpError(json.dumps(data["exceptionDetails"], ensure_ascii=False))
    remote_object = data.get("result", {})
    raw = remote_object.get("value", remote_object)
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def _request_json(url: str, data: bytes | None = None) -> Any:
    request = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=10) as response:
            text = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise CdpError(f"Chrome DevTools HTTP request failed: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise CdpError(f"Chrome DevTools HTTP returned non-JSON response: {text[:200]}") from exc


def _websocket_handshake(sock: socket.socket, chrome_port: int, path: str) -> None:
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: localhost:{chrome_port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    sock.sendall(request.encode("ascii"))
    response = b""
    while b"\r\n\r\n" not in response:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk
    if not response.startswith(b"HTTP/1.1 101"):
        raise CdpError(f"CDP WebSocket handshake failed: {response[:200]!r}")


def _send_ws_json(sock: socket.socket, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    header = bytearray([0x81])
    length = len(body)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", length))
    mask = os.urandom(4)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(body))
    sock.sendall(bytes(header) + mask + masked)


def _recv_ws_json(sock: socket.socket) -> dict[str, Any]:
    first = _recv_exact(sock, 2)
    opcode = first[0] & 0x0F
    if opcode == 0x8:
        raise CdpError("CDP WebSocket closed")
    length = first[1] & 0x7F
    masked = bool(first[1] & 0x80)
    if length == 126:
        length = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(sock, 8))[0]
    mask = _recv_exact(sock, 4) if masked else b""
    body = _recv_exact(sock, length)
    if masked:
        body = bytes(byte ^ mask[index % 4] for index, byte in enumerate(body))
    if opcode not in (0x1, 0x2):
        return {}
    return json.loads(body.decode("utf-8"))


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise CdpError("CDP WebSocket disconnected")
        chunks.extend(chunk)
    return bytes(chunks)
