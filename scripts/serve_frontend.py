"""Serve the frontend for local development without browser caching.

Usage: python scripts/serve_frontend.py [port]     (default port 5500)

Plain `python -m http.server` lets browsers (Safari especially) keep old
JavaScript and CSS, so changes don't show up without clearing the cache.
This server tells the browser to revalidate every file on each load.
"""

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


class NoCacheHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".svg": "image/svg+xml",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5500
    handler = partial(NoCacheHandler, directory=str(FRONTEND))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"Eysto frontend: http://localhost:{port}  (Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
