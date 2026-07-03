"""
Bridge Server v3 — Fixed timeout + robust response handling
"""
import socket, json, threading, os, sys, time
from http.server import HTTPServer, BaseHTTPRequestHandler

BRIDGE = None
BRIDGE_LOCK = threading.Lock()
bridge_connected = threading.Event()

def bridge_listener(port=5099):
    global BRIDGE
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(1)
    print(f"🔵 Bridge listening on port {port}")
    conn, addr = server.accept()
    with BRIDGE_LOCK:
        BRIDGE = conn
        BRIDGE.settimeout(None)  # No timeout on recv
    bridge_connected.set()
    print(f"✅ Windows connected from {addr}!")
    
    # Read responses - one JSON per line
    buf = b""
    while True:
        try:
            c = conn.recv(1)
            if not c:
                break
            if c == b"\n":
                try:
                    resp = json.loads(buf.decode())
                    cid = resp.pop("_cid", None)
                    if cid is not None:
                        with _results_lock:
                            _results[cid] = resp
                except:
                    pass
                buf = b""
            else:
                buf += c
        except:
            break
    print("❌ Windows disconnected")
    with BRIDGE_LOCK:
        BRIDGE = None

_results = {}
_results_lock = threading.Lock()

def send_cmd(cmd, timeout=120):
    global _cid_counter
    bridge_connected.wait(timeout=10)
    with BRIDGE_LOCK:
        if not BRIDGE:
            return {"error": "No bridge"}
        cid = int(time.time() * 1000000) % 10000000
        cmd["_cid"] = cid
        try:
            BRIDGE.sendall((json.dumps(cmd) + "\n").encode())
        except:
            return {"error": "Send failed"}
    
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _results_lock:
            if cid in _results:
                return _results.pop(cid)
        time.sleep(0.05)
    return {"error": "Timeout"}

class Handler(BaseHTTPRequestHandler):
    def _json(self, data, status=200):
        data_str = json.dumps(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data_str.encode())))
        self.end_headers()
        try:
            self.wfile.write(data_str.encode())
            self.wfile.flush()
        except:
            pass
    
    def do_GET(self):
        if self.path == "/status":
            self._json({"bridge": bridge_connected.is_set()})
        elif self.path == "/screenshot":
            result = send_cmd({"action": "screenshot"}, timeout=60)
            self._json(result)
        else:
            self._json({"error": "?"}, 404)
    
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            self._json({"error": "No body"}, 400)
            return
        data = json.loads(self.rfile.read(length))
        action = data.pop("action", "")
        result = send_cmd({"action": action, **data}, timeout=120)
        self._json(result)
    
    def log_message(self, *a): pass

if __name__ == "__main__":
    t = threading.Thread(target=bridge_listener, daemon=True)
    t.start()
    
    time.sleep(0.5)
    http_port = 5100
    server = HTTPServer(("0.0.0.0", http_port), Handler)
    print(f"🚀 HTTP API on port {http_port}")
    print(f"   Windows → 76.13.18.146:5099")
    print(f"   Hermes  → localhost:{http_port}")
    print(f"")
    print(f"Lo jalanin: python bridge_client.py")
    print(f"Kalo udah connect, gue test...")
    
    try:
        server.serve_forever()
    except:
        pass
