"""
Browser API Server — Playwright visible Chromium controlled via REST API
Run on Windows: python browser_api.py
Then SSH tunnel: ssh -R 5001:localhost:5001 root@serverip
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import json, base64, os, sys

from playwright.sync_api import sync_playwright

# Global browser/page
_browser = None
_page = None
_pw = None

def get_browser():
    global _browser, _page, _pw
    if _browser is None:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(headless=False)  # VISIBLE browser!
        _page = _browser.new_page()
        _page.set_viewport_size({"width": 1280, "height": 800})
        print("✅ Browser VISIBLE started")
    return _page

def close_browser():
    global _browser, _page, _pw
    if _browser:
        _browser.close()
        _browser = None
    if _pw:
        _pw.stop()
        _pw = None
    _page = None
    print("❌ Browser closed")

class Handler(BaseHTTPRequestHandler):
    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        if self.path == "/api/status":
            if _page:
                self._json({
                    "browser": True,
                    "url": _page.url,
                    "title": _page.title(),
                    "text": _page.evaluate("document.body.innerText")[:2000]
                })
            else:
                self._json({"browser": False})
        elif self.path == "/api/screenshot":
            if _page:
                b = _page.screenshot(full_page=False)
                self._json({"image_base64": base64.b64encode(b).decode()})
            else:
                self._json({"error": "No browser"}, 400)
        else:
            self._json({"error": "Not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            self._json({"error": "No body"}, 400)
            return
        data = json.loads(self.rfile.read(length))
        action = data.get("action", "")
        
        try:
            p = get_browser()
            result = {"ok": True}
            
            if action == "navigate":
                p.goto(data["url"], wait_until="domcontentloaded", timeout=30000)
                result["url"] = p.url
            elif action == "click_text":
                text = data.get("text", "")
                el = p.get_by_text(text, exact=False)
                if el.count() > 0:
                    el.first.click()
                    result["clicked"] = text
                else:
                    result["error"] = f"Text '{text}' not found"
            elif action == "click_selector":
                sel = data.get("selector", "")
                el = p.locator(sel)
                if el.count() > 0:
                    el.first.click()
                    result["clicked"] = sel
                else:
                    result["error"] = f"Selector '{sel}' not found"
            elif action == "type":
                p.keyboard.type(data.get("text", ""), delay=30)
            elif action == "fill":
                sel = data.get("selector", "input")
                p.locator(sel).first.fill(data.get("text", ""))
            elif action == "press":
                p.keyboard.press(data.get("key", "Enter"))
            elif action == "screenshot":
                b = p.screenshot(full_page=False)
                result["image_base64"] = base64.b64encode(b).decode()
            elif action == "evaluate":
                result["result"] = p.evaluate(data.get("js", ""))
            elif action == "scroll":
                p.evaluate(f"window.scrollBy(0, {data.get('pixels', 300)})")
            elif action == "wait":
                import time; time.sleep(data.get("seconds", 3))
            elif action == "stop":
                close_browser()
                result["closed"] = True
            elif action == "start":
                get_browser()
                result["started"] = True
            else:
                result = {"error": f"Unknown action: {action}"}
            
            self._json(result)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def log_message(self, format, *args):
        print(f"[{self.command}] {self.path} - {args[0]}")

class ThreadedServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    server = ThreadedServer(("0.0.0.0", port), Handler)
    print(f"🚀 Browser API Server on http://0.0.0.0:{port}")
    print("   - Start browser: curl -X POST http://localhost:{port}/api/action -H 'Content-Type:application/json' -d '{\"action\":\"start\"}'")
    print("   - Navigate: curl -X POST ... -d '{\"action\":\"navigate\",\"url\":\"https://example.com\"}'")
    print("   - Screenshot: curl -X POST ... -d '{\"action\":\"screenshot\"}'")
    print("   - Click: curl -X POST ... -d '{\"action\":\"click_text\",\"text\":\"Login\"}'")
    print("   - Status: GET http://localhost:{port}/api/status")
    print("   - Screenshot: GET http://localhost:{port}/api/screenshot")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        close_browser()
        server.shutdown()
