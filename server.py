"""
server.py
=========
Runs the Beauty Advisor as ONE functional website: it serves storefront.html
AND exposes the Gemini-powered advisor at POST /api/advise, so the in-page chat
assistant is driven by the real RAG + Gemini brain (app/advisor.py) instead of
the offline rule-based fallback.

The GEMINI_API_KEY stays HERE on the server — it is never sent to the browser.

Run:
    export GEMINI_API_KEY=...        # optional; without it the advisor returns mock output
    python server.py                 # then open http://localhost:8000

No extra dependencies — built on Python's standard-library http.server.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.advisor import advise  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8000"))


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html", "/storefront.html"):
            with open(os.path.join(HERE, "storefront.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path != "/api/advise":
            self._send(404, json.dumps({"error": "not found"}))
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            query = (payload.get("query") or "").strip()
            if not query:
                self._send(400, json.dumps({"error": "empty query"}))
                return
            result = advise(query, history=payload.get("history", ""),
                            max_price=payload.get("max_price"))
            self._send(200, json.dumps(result, ensure_ascii=False))
        except Exception as e:  # never let one bad request kill the server
            self._send(500, json.dumps({"error": f"{type(e).__name__}: {e}"}))

    def log_message(self, *args):
        pass  # keep the console quiet


if __name__ == "__main__":
    mode = "LIVE (Gemini)" if os.environ.get("GEMINI_API_KEY") else "MOCK (no GEMINI_API_KEY set)"
    print(f"Beauty Advisor storefront  ->  http://localhost:{PORT}   [{mode}]", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
