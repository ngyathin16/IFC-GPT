"""Minimal helper: send one MCP socket command and return parsed result dict."""
import json
import socket
import sys


def mcp(cmd: str, params: dict = None, timeout: int = 60) -> dict:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("localhost", 9876))
    s.sendall(json.dumps({"type": cmd, "params": params or {}}).encode("utf-8"))
    buf = bytearray()
    s.settimeout(timeout)
    while True:
        try:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf.extend(chunk)
            try:
                json.loads(buf.decode("utf-8"))
                break
            except json.JSONDecodeError:
                pass
        except TimeoutError:
            break
    s.close()
    return json.loads(buf.decode("utf-8"))
