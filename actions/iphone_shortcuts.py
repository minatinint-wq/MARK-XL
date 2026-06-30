from __future__ import annotations

import base64
import json
import os
import secrets
import socket
import sys
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from actions.operation_memory import record_operation


BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "iphone_shortcuts.json"
EVENTS_PATH = BASE_DIR / "memory" / "iphone_shortcuts_events.json"
FILES_DIR = BASE_DIR / "memory" / "iphone_shortcuts_files"
DEFAULT_PORT = 8765
MAX_EVENTS = 300

_SERVER: ThreadingHTTPServer | None = None
_THREAD: threading.Thread | None = None
_LOCK = threading.Lock()


SHORTCUT_TEMPLATES: dict[str, dict[str, str]] = {
    "battery": {
        "title": "Enviar bateria",
        "event": "battery",
        "body": '{"type":"battery","battery":"[Battery Level]","charging":"[Is Charging]"}',
    },
    "location": {
        "title": "Enviar localizacao",
        "event": "location",
        "body": '{"type":"location","latitude":"[Latitude]","longitude":"[Longitude]","address":"[Street Address]"}',
    },
    "clipboard": {
        "title": "Enviar clipboard",
        "event": "clipboard",
        "body": '{"type":"clipboard","text":"[Clipboard]"}',
    },
    "focus": {
        "title": "Modo foco",
        "event": "focus",
        "body": '{"type":"focus","mode":"trabalho","state":"on"}',
    },
    "photo": {
        "title": "Enviar foto/print",
        "event": "photo",
        "body": '{"type":"photo","filename":"iphone-photo.jpg","base64":"[Base64 Encoded File]"}',
    },
    "audio": {
        "title": "Enviar audio",
        "event": "audio",
        "body": '{"type":"audio","filename":"iphone-audio.m4a","base64":"[Base64 Encoded File]"}',
    },
    "emergency": {
        "title": "Emergencia",
        "event": "emergency",
        "body": '{"type":"emergency","message":"preciso de ajuda","latitude":"[Latitude]","longitude":"[Longitude]"}',
    },
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load_config() -> dict[str, Any]:
    data: dict[str, Any] = {
        "host": "0.0.0.0",
        "port": DEFAULT_PORT,
        "token": secrets.token_urlsafe(12),
    }
    try:
        if CONFIG_PATH.exists():
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update(raw)
    except Exception:
        pass
    if not data.get("token"):
        data["token"] = secrets.token_urlsafe(12)
    _save_config(data)
    return data


def _save_config(data: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def _public_base_url() -> str:
    cfg = _load_config()
    return f"http://{_local_ip()}:{int(cfg.get('port', DEFAULT_PORT))}"


def _read_events() -> list[dict[str, Any]]:
    try:
        if EVENTS_PATH.exists():
            data = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
    except Exception:
        pass
    return []


def _write_events(events: list[dict[str, Any]]) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVENTS_PATH.write_text(json.dumps(events[-MAX_EVENTS:], indent=2, ensure_ascii=False), encoding="utf-8")


def _safe_filename(name: str, fallback: str = "iphone-file.bin") -> str:
    name = Path(str(name or fallback)).name
    clean = "".join(ch for ch in name if ch.isalnum() or ch in "._- ")
    return clean[:120].strip() or fallback


def _save_attachment(payload: dict[str, Any], event_type: str) -> str | None:
    raw = payload.get("base64") or payload.get("file_base64") or payload.get("data_base64")
    if not raw:
        return None
    if not isinstance(raw, str):
        return None
    if "," in raw and raw.strip().lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        blob = base64.b64decode(raw, validate=False)
    except Exception:
        return None
    if not blob:
        return None
    if len(blob) > 30 * 1024 * 1024:
        return None
    folder = FILES_DIR / _safe_filename(event_type, "event")
    folder.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(str(payload.get("filename") or payload.get("name") or f"{event_type}-{int(time.time())}.bin"))
    path = folder / filename
    if path.exists():
        path = folder / f"{path.stem}-{int(time.time())}{path.suffix}"
    path.write_bytes(blob)
    return str(path)


def _store_event(payload: dict[str, Any], source: str = "shortcut") -> dict[str, Any]:
    event_type = str(payload.get("type") or payload.get("event") or "generic").lower().strip()
    event = {
        "id": f"ios-{int(time.time() * 1000)}",
        "time": _now(),
        "source": source,
        "type": event_type,
        "payload": {k: v for k, v in payload.items() if k not in {"base64", "file_base64", "data_base64"}},
    }
    saved_file = _save_attachment(payload, event_type)
    if saved_file:
        event["file"] = saved_file
    with _LOCK:
        events = _read_events()
        events.append(event)
        _write_events(events)
    record_operation("iphone_shortcuts", event_type, event.get("payload", {}), sensitive=event_type in {"clipboard", "photo", "audio"})
    return event


def _json_response(handler: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, X-JARVIS-Token")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


def _authorized(handler: BaseHTTPRequestHandler, query: dict[str, list[str]]) -> bool:
    token = str(_load_config().get("token") or "")
    if not token:
        return True
    got = handler.headers.get("X-JARVIS-Token") or (query.get("token") or [""])[0]
    return secrets.compare_digest(str(got), token)


class _ShortcutHandler(BaseHTTPRequestHandler):
    server_version = "JarvisIPhoneShortcuts/1.0"

    def log_message(self, *_args) -> None:
        return

    def do_OPTIONS(self) -> None:
        _json_response(self, {"ok": True})

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        path = parsed.path.rstrip("/") or "/"

        if path in {"/", "/health"}:
            _json_response(self, {
                "ok": True,
                "service": "jarvis_iphone_shortcuts",
                "time": _now(),
                "events": len(_read_events()),
            })
            return

        if not _authorized(self, query):
            _json_response(self, {"ok": False, "error": "unauthorized"}, 401)
            return

        if path == "/events":
            limit = int((query.get("limit") or ["30"])[0] or 30)
            _json_response(self, {"ok": True, "events": _read_events()[-max(1, min(limit, 100)):][::-1]})
            return

        if path == "/latest":
            events = _read_events()
            _json_response(self, {"ok": True, "event": events[-1] if events else None})
            return

        if path == "/templates":
            _json_response(self, {"ok": True, "templates": _template_payload()})
            return

        if path == "/event":
            payload = {key: values[-1] if values else "" for key, values in query.items() if key != "token"}
            event = _store_event(payload, source="shortcut_get")
            _json_response(self, {"ok": True, "event": event})
            return

        _json_response(self, {"ok": False, "error": "not_found"}, 404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        path = parsed.path.rstrip("/") or "/"

        if not _authorized(self, query):
            _json_response(self, {"ok": False, "error": "unauthorized"}, 401)
            return

        if path not in {"/event", "/shortcut", "/ios"}:
            _json_response(self, {"ok": False, "error": "not_found"}, 404)
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(min(length, 35 * 1024 * 1024)) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8", errors="replace") or "{}")
        except Exception:
            payload = {"type": "text", "text": raw.decode("utf-8", errors="replace")}
        if not isinstance(payload, dict):
            payload = {"type": "value", "value": payload}
        event = _store_event(payload, source="shortcut_post")
        _json_response(self, {"ok": True, "event": event})


def _template_payload() -> dict[str, Any]:
    cfg = _load_config()
    base = _public_base_url()
    token = urllib.parse.quote(str(cfg.get("token") or ""))
    items = {}
    for key, template in SHORTCUT_TEMPLATES.items():
        items[key] = {
            **template,
            "method": "POST",
            "url": f"{base}/event?token={token}",
            "headers": {"Content-Type": "application/json"},
        }
    return {
        "base_url": base,
        "token": cfg.get("token"),
        "items": items,
    }


def _is_running() -> bool:
    return _SERVER is not None and _THREAD is not None and _THREAD.is_alive()


def _start_server(port: int | None = None) -> str:
    global _SERVER, _THREAD
    with _LOCK:
        if _is_running():
            return f"iPhone Shortcuts Bridge ja esta rodando em {_public_base_url()}."
        cfg = _load_config()
        if port:
            cfg["port"] = int(port)
            _save_config(cfg)
        host = str(cfg.get("host") or "0.0.0.0")
        bind_port = int(cfg.get("port") or DEFAULT_PORT)
        _SERVER = ThreadingHTTPServer((host, bind_port), _ShortcutHandler)
        _THREAD = threading.Thread(target=_SERVER.serve_forever, name="IPhoneShortcutsBridge", daemon=True)
        _THREAD.start()
    return f"iPhone Shortcuts Bridge iniciado em {_public_base_url()}."


def _stop_server() -> str:
    global _SERVER, _THREAD
    with _LOCK:
        server = _SERVER
        _SERVER = None
        _THREAD = None
    if server is None:
        return "iPhone Shortcuts Bridge ja estava parado."
    try:
        server.shutdown()
        server.server_close()
    except Exception:
        pass
    return "iPhone Shortcuts Bridge parado."


def _open_config_html() -> str:
    path = BASE_DIR / "config" / "iphone_social_config.html"
    if not path.exists():
        return f"HTML de config nao encontrado: {path}"
    webbrowser.open(path.as_uri())
    return f"Config local aberto: {path}"


def _status_text() -> str:
    cfg = _load_config()
    status = "rodando" if _is_running() else "parado"
    lines = [
        f"iPhone Shortcuts Bridge: {status}",
        f"URL: {_public_base_url()}",
        f"Token: {cfg.get('token')}",
        f"Eventos salvos: {len(_read_events())}",
        f"Arquivo: {EVENTS_PATH}",
    ]
    return "\n".join(lines)


def _events_text(limit: int = 10) -> str:
    events = _read_events()[-max(1, min(limit, 50)):][::-1]
    if not events:
        return "Nenhum evento do iPhone recebido ainda."
    lines = [f"Ultimos eventos do iPhone ({len(events)}):"]
    for event in events:
        payload = event.get("payload") or {}
        label = payload.get("message") or payload.get("text") or payload.get("battery") or payload.get("mode") or ""
        if isinstance(label, str) and len(label) > 70:
            label = label[:67] + "..."
        lines.append(f"- {event.get('time')} | {event.get('type')} | {label}")
    return "\n".join(lines)


def _templates_text() -> str:
    payload = _template_payload()
    lines = [
        "Templates para Atalhos do iPhone:",
        f"URL: {payload['base_url']}/event?token={payload['token']}",
        "Metodo: POST",
        "Header: Content-Type = application/json",
    ]
    for key, item in payload["items"].items():
        lines.append(f"\n{key}: {item['title']}")
        lines.append(item["body"])
    return "\n".join(lines)


def iphone_shortcuts(parameters: dict[str, Any] | None = None, player=None, speak=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action") or "status").lower().strip()

    try:
        if player:
            player.write_log(f"[iPhoneShortcuts] {action}")
    except Exception:
        pass

    if action in {"start", "iniciar", "run", "server"}:
        return _start_server(params.get("port"))
    if action in {"stop", "parar"}:
        return _stop_server()
    if action in {"restart", "reiniciar"}:
        stopped = _stop_server()
        started = _start_server(params.get("port"))
        return f"{stopped}\n{started}"
    if action in {"status", "info"}:
        return _status_text()
    if action in {"url", "link"}:
        cfg = _load_config()
        return f"{_public_base_url()}/event?token={cfg.get('token')}"
    if action in {"templates", "modelos", "atalhos", "guide", "guia"}:
        return _templates_text()
    if action in {"events", "list", "listar"}:
        return _events_text(int(params.get("limit") or 10))
    if action in {"latest", "ultimo", "last"}:
        events = _read_events()
        return json.dumps(events[-1] if events else {"message": "Nenhum evento recebido."}, indent=2, ensure_ascii=False)
    if action in {"clear", "limpar"}:
        _write_events([])
        return "Eventos do iPhone limpos."
    if action in {"test", "fake"}:
        event = _store_event({"type": params.get("type") or "test", "message": params.get("message") or "evento de teste"}, "local_test")
        return f"Evento de teste salvo: {event['id']}"
    if action in {"config", "html", "open_config"}:
        return _open_config_html()
    return "Acao desconhecida. Use start, status, url, templates, events, latest, clear, config ou stop."
