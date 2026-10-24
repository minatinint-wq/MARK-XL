"""One-shot localhost receiver for the Spotify OAuth callback.

The server accepts only the configured local callback path, passes the full callback
URL to the existing token handler, then stops. It never writes or logs the auth code.
"""
from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import sys
from threading import Event
from time import monotonic
from urllib.parse import urlsplit


# This file is launched directly by Windows. Make the project root importable so
# the existing actions.smart_home token handler is resolved reliably.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def receive_callback(timeout_seconds: int = 180, ready: Event | None = None) -> str:
    done = Event()
    outcome = {"message": "Tempo esgotado aguardando a autorização do Spotify."}

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, _format, *_args):
            pass

        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path != "/callback":
                self.send_error(404)
                return
            try:
                from actions.smart_home import _spotify_process_callback

                callback_url = f"http://127.0.0.1:8888{self.path}"
                outcome["message"] = _spotify_process_callback(callback_url)
                ok = not str(outcome["message"]).casefold().startswith("erro")
            except Exception as exc:
                outcome["message"] = (
                    "Não foi possível concluir a autorização do Spotify: "
                    f"{type(exc).__name__}: {exc}"
                )
                ok = False
            detail = str(outcome["message"])
            # The provider's error is useful for fixing configuration, but a callback
            # code must never be rendered back into the browser page.
            detail = re.sub(r"(?i)(code=)[^&\s<]+", r"\1[oculto]", detail)
            detail = escape(detail[:700])
            body = (
                "<html><body style='background:#07141b;color:#c9f8ff;font-family:Segoe UI;padding:42px'>"
                f"<h2>{'Spotify conectado' if ok else 'Spotify não conectado'}</h2>"
                f"<p style='color:{'#7dffbd' if ok else '#ffbd7d'}'>{detail}</p>"
                "<p>Você já pode fechar esta página e voltar ao Jarvis.</p>"
                "</body></html>"
            ).encode("utf-8")
            self.send_response(200 if ok else 400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            done.set()

    server = ThreadingHTTPServer(("127.0.0.1", 8888), CallbackHandler)
    server.timeout = 0.25
    try:
        if ready is not None:
            ready.set()
        deadline = monotonic() + max(15, int(timeout_seconds))
        while not done.is_set() and monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    return str(outcome["message"])


if __name__ == "__main__":
    receive_callback()
