"""Understand how tool.Root.get_default_container works and how to set it."""
import json, socket

def send(cmd, params=None, timeout=30):
    s = socket.socket(); s.connect(("localhost", 9876))
    s.sendall(json.dumps({"type": cmd, "params": params or {}}).encode())
    buf = bytearray(); s.settimeout(timeout)
    while True:
        try:
            chunk = s.recv(65536)
            if not chunk: break
            buf.extend(chunk)
            try: json.loads(buf.decode()); break
            except: pass
        except: break
    s.close(); return json.loads(buf.decode())

code = (
    "import bpy, bonsai.tool as tool, inspect\n"
    "src = inspect.getsource(tool.Root.get_default_container)\n"
    "print(src[:800])\n"
)
r = send("execute_code", {"code": code})
print(r.get("result", {}).get("output", r))
