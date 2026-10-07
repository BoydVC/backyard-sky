#!/usr/bin/env python3
"""Serve web/ on 0.0.0.0:4268 (Backyard Sky Tonight)."""
import http.server, functools, os
H = os.path.dirname(os.path.abspath(__file__))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self): self.send_header("Cache-Control", "no-store"); super().end_headers()
http.server.ThreadingHTTPServer(("0.0.0.0", 4268), functools.partial(Q, directory=os.path.join(H, "web"))).serve_forever()
