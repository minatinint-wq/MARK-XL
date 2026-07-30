"""Private PWA gateway for the MARK-XL JARVIS Bridge beta.

It deliberately exposes a small, allow-listed set of actions. This is not a
remote shell: every command has a named purpose and sensitive data stays local.
"""
from __future__ import annotations

import json
import mimetypes
import secrets
import sys
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from actions.operation_memory import record_operation
from actions.jarvis_relay_connector import pair_code as relay_pair_code, start as start_relay

BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
# The Bridge was split into its own deployable repository. Prefer that source
# locally, while retaining the former folder as a compatibility fallback.
WEB_ROOT = BASE_DIR.parent / "jarvis-bridge" / "public"
if not WEB_ROOT.is_dir():
    WEB_ROOT = BASE_DIR.parent / "JARVIS Bridge"
CONFIG_PATH = BASE_DIR / "config" / "jarvis_bridge.json"
EVENTS_PATH = BASE_DIR / "memory" / "iphone_shortcuts_events.json"
DEFAULT_PORT = 8796
PAIR_TTL_SECONDS = 10 * 60
MAX_TEXT = 2000

_SERVER: ThreadingHTTPServer | None = None
_THREAD: threading.Thread | None = None
_LOCK = threading.Lock()
_PAIR_CODE = ""
_PAIR_EXPIRES = 0.0


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_config() -> dict[str, Any]:
    data: dict[str, Any] = {"host": "127.0.0.1", "port": DEFAULT_PORT, "token": secrets.token_urlsafe(32)}
    try:
        if CONFIG_PATH.exists():
            value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                data.update(value)
    except Exception:
        pass
    if not str(data.get("token") or ""):
        data["token"] = secrets.token_urlsafe(32)
    _save_config(data)
    return data


def _save_config(data: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _base_url() -> str:
    cfg = _load_config()
    return f"http://127.0.0.1:{int(cfg.get('port') or DEFAULT_PORT)}"


def _refresh_pair_code() -> None:
    global _PAIR_CODE, _PAIR_EXPIRES
    _PAIR_CODE = f"{secrets.randbelow(1_000_000):06d}"
    _PAIR_EXPIRES = time.time() + PAIR_TTL_SECONDS


def _pair_code_valid(code: str) -> bool:
    return bool(_PAIR_CODE and time.time() < _PAIR_EXPIRES and secrets.compare_digest(str(code or ""), _PAIR_CODE))


def _read_events(limit: int = 30) -> list[dict[str, Any]]:
    try:
        raw = json.loads(EVENTS_PATH.read_text(encoding="utf-8")) if EVENTS_PATH.exists() else []
        return [event for event in raw if isinstance(event, dict)][-max(1, min(limit, 100)):][::-1] if isinstance(raw, list) else []
    except Exception:
        return []


def _is_running() -> bool:
    return bool(_SERVER and _THREAD and _THREAD.is_alive())


def _safe_web_file(request_path: str) -> Path | None:
    relative = "index.html" if request_path in {"", "/"} else unquote(request_path).lstrip("/")
    candidate = (WEB_ROOT / relative).resolve()
    try:
        candidate.relative_to(WEB_ROOT.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _clipboard_read() -> str:
    try:
        import pyperclip
        return str(pyperclip.paste() or "")[:MAX_TEXT]
    except Exception:
        return ""


def _clipboard_write(text: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(text[:MAX_TEXT])
        return True
    except Exception:
        return False


def _dispatch(command: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    action = str(command.get("action") or "").lower().strip()
    text = str(command.get("text") or command.get("message") or "").strip()[:MAX_TEXT]
    extras: dict[str, Any] = {}
    if action == "open_phone_link":
        from actions.iphone_bridge import iphone_bridge
        result = iphone_bridge({"action": "phone_link"})
    elif action == "media":
        media = str(command.get("command") or "play_pause").lower().strip()
        if media not in {"play", "pause", "play_pause", "next", "previous", "volume_up", "volume_down", "mute"}:
            return False, "Comando de mídia não permitido.", extras
        from actions.iphone_bridge import iphone_bridge
        result = iphone_bridge({"action": media})
    elif action == "copy_to_pc":
        if not text:
            return False, "Envie um texto para copiar.", extras
        result = "Texto copiado no PC." if _clipboard_write(text) else "Não foi possível acessar o clipboard do PC."
    elif action == "read_pc_clipboard":
        extras["clipboard"] = _clipboard_read()
        result = "Clipboard do PC atualizado."
    elif action == "whatsapp_open":
        import webbrowser
        webbrowser.open("https://web.whatsapp.com/")
        result = "WhatsApp Web aberto no desktop."
    elif action == "whatsapp_send":
        receiver = str(command.get("receiver") or "").strip()[:120]
        if not bool(command.get("confirm")):
            return False, "Confirme o envio antes de mandar uma mensagem.", extras
        if not receiver or not text:
            return False, "Informe contato e mensagem.", extras
        from actions.send_message import send_message
        result = send_message({"platform": "whatsapp", "receiver": receiver, "message_text": text})
    elif action == "phone_shortcut":
        shortcut = str(command.get("shortcut") or "").strip()[:120]
        if not shortcut:
            return False, "Informe o nome do Atalho do iPhone.", extras
        extras["shortcut_url"] = "shortcuts://run-shortcut?name=" + shortcut.replace(" ", "%20")
        result = "Atalho preparado; confirme a abertura no iPhone."
    elif action == "note":
        if not text:
            return False, "Digite uma nota ou comando.", extras
        result = "Comando registrado na atividade da Bridge."
    else:
        return False, "Ação não permitida nesta beta.", extras
    record_operation("jarvis_bridge", action, {"has_text": bool(text)}, sensitive=action in {"copy_to_pc", "read_pc_clipboard", "whatsapp_send"})
    return True, str(result or "Concluído."), extras


class _GatewayHandler(BaseHTTPRequestHandler):
    server_version = "JarvisBridge/0.1"
    def log_message(self, *_args: Any) -> None:
        return
    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
    def _body(self) -> dict[str, Any]:
        try:
            raw = self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 16 * 1024))
            value = json.loads(raw.decode("utf-8", errors="replace") or "{}")
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}
    def _authorized(self) -> bool:
        token = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        expected = str(_load_config().get("token") or "")
        return bool(token and expected and secrets.compare_digest(token, expected))
    def _api_get(self, path: str) -> None:
        if path == "/api/health":
            self._json({"ok": True, "service": "jarvis_bridge", "time": _now()}); return
        if not self._authorized():
            self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED); return
        if path == "/api/status":
            self._json({"ok": True, "service": "jarvis_bridge", "time": _now(), "shortcuts_events": len(_read_events(100)), "allowed_actions": ["open_phone_link", "media", "copy_to_pc", "read_pc_clipboard", "whatsapp_open", "whatsapp_send", "phone_shortcut"]})
        elif path == "/api/events": self._json({"ok": True, "events": _read_events()})
        else: self._json({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            self._api_get(path); return
        file_path = _safe_web_file(path)
        if not file_path:
            self.send_error(HTTPStatus.NOT_FOUND); return
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(str(file_path))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache" if file_path.name == "sw.js" else "public, max-age=300")
        self.end_headers(); self.wfile.write(content)
    def do_POST(self) -> None:
        path, payload = urlparse(self.path).path, self._body()
        if path == "/api/pair":
            if not _pair_code_valid(str(payload.get("code") or "")):
                self._json({"ok": False, "error": "Código de pareamento inválido ou expirado."}, HTTPStatus.UNAUTHORIZED); return
            global _PAIR_CODE
            _PAIR_CODE = ""
            self._json({"ok": True, "token": _load_config()["token"], "message": "iPhone pareado com a Bridge."}); return
        if not self._authorized():
            self._json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED); return
        if path == "/api/command":
            ok, message, extras = _dispatch(payload)
            self._json({"ok": ok, "message": message, **extras}, HTTPStatus.OK if ok else HTTPStatus.BAD_REQUEST); return
        self._json({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)


def _start(port: int | None = None) -> str:
    global _SERVER, _THREAD
    with _LOCK:
        if _is_running(): return f"JARVIS Bridge já está rodando em {_base_url()}."
        if not WEB_ROOT.is_dir(): return f"Pasta do PWA não encontrada: {WEB_ROOT}"
        cfg = _load_config()
        if port:
            cfg["port"] = max(1024, min(int(port), 65535)); _save_config(cfg)
        _refresh_pair_code()
        _SERVER = ThreadingHTTPServer((str(cfg.get("host") or "127.0.0.1"), int(cfg.get("port") or DEFAULT_PORT)), _GatewayHandler)
        _THREAD = threading.Thread(target=_SERVER.serve_forever, name="JarvisBridgeGateway", daemon=True); _THREAD.start()
    relay_status = start_relay(_dispatch)
    return f"JARVIS Bridge beta iniciada em {_base_url()}.\n{relay_status}"


def _stop() -> str:
    global _SERVER, _THREAD
    with _LOCK: server, _SERVER, _THREAD = _SERVER, None, None
    if not server: return "JARVIS Bridge já estava parada."
    server.shutdown(); server.server_close(); return "JARVIS Bridge parada."


def jarvis_bridge_gateway(parameters: dict[str, Any] | None = None, player=None, speak=None, **_: Any) -> str:
    params = parameters or {}; action = str(params.get("action") or "status").lower().strip()
    if action in {"start", "iniciar", "run"}: return _start(params.get("port"))
    if action in {"stop", "parar"}: return _stop()
    if action in {"restart", "reiniciar"}: return _stop() + "\n" + _start(params.get("port"))
    if action in {"pair", "parear", "code", "codigo"}:
        if not _is_running():
            _start(params.get("port"))
        return relay_pair_code()
    if action in {"reset", "reset_pairing"}:
        cfg = _load_config(); cfg["token"] = secrets.token_urlsafe(32); _save_config(cfg); _refresh_pair_code()
        return "Pareamentos revogados. Novo código: " + _PAIR_CODE
    if action in {"status", "info"}:
        code = _PAIR_CODE if _PAIR_CODE and time.time() < _PAIR_EXPIRES else "gere com action=pair"
        return f"JARVIS Bridge: {'rodando' if _is_running() else 'parada'}\nURL local: {_base_url()}\nCódigo atual: {code}\nEventos iPhone: {len(_read_events(100))}\nPara iPhone remoto, use Tailscale Serve com HTTPS."
    return "Ação desconhecida. Use start, stop, restart, status, pair ou reset."
