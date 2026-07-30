"""Outbound WebSocket connector between MARK-XL and the Render JARVIS relay."""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "jarvis_relay.json"
DEFAULT_URL = "https://leadio-evolution.onrender.com"
_THREAD: threading.Thread | None = None
_STOP = threading.Event()
_LOCK = threading.Lock()


def _config() -> dict[str, str]:
    data = {"url": os.environ.get("JARVIS_RELAY_URL", DEFAULT_URL), "desktop_token": os.environ.get("JARVIS_DESKTOP_TOKEN", "")}
    try:
        saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            data.update({key: str(value or "") for key, value in saved.items() if key in data})
    except Exception:
        pass
    data["url"] = data["url"].rstrip("/")
    return data


def _websocket_url(url: str, token: str) -> str:
    scheme = "wss" if url.startswith("https://") else "ws"
    host = url.split("://", 1)[-1]
    return f"{scheme}://{host}/ws/desktop?token={token}"


async def _run(dispatch: Callable[[dict[str, Any]], tuple[bool, str, dict[str, Any]]], log: Callable[[str], Any] | None) -> None:
    import websockets
    delay = 2.0
    while not _STOP.is_set():
        cfg = _config()
        token = cfg.get("desktop_token", "")
        if not token:
            return
        try:
            async with websockets.connect(_websocket_url(cfg["url"], token), ping_interval=20, ping_timeout=20) as ws:
                delay = 2.0
                if log: log("SYS: JARVIS Relay conectado ao Render.")
                async for raw in ws:
                    message = json.loads(raw)
                    if message.get("type") != "command":
                        continue
                    ok, result, extras = dispatch(dict(message.get("command") or {}))
                    await ws.send(json.dumps({"type": "result", "id": message.get("id"), "ok": ok, "message": result, **extras}, ensure_ascii=False))
        except Exception as exc:
            if log: log(f"SYS: Relay reconectando: {str(exc)[:100]}")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)


def start(dispatch: Callable[[dict[str, Any]], tuple[bool, str, dict[str, Any]]], log: Callable[[str], Any] | None = None) -> str:
    global _THREAD
    cfg = _config()
    if not cfg.get("desktop_token"):
        return f"Relay aguardando token em {CONFIG_PATH}."
    with _LOCK:
        if _THREAD and _THREAD.is_alive():
            return "JARVIS Relay já está conectado."
        _STOP.clear()
        _THREAD = threading.Thread(target=lambda: asyncio.run(_run(dispatch, log)), name="JarvisRelay", daemon=True)
        _THREAD.start()
    return f"JARVIS Relay conectando em {cfg['url']}."


def pair_code() -> str:
    cfg = _config()
    token = cfg.get("desktop_token", "")
    if not token:
        return f"Configure desktop_token em {CONFIG_PATH} com o mesmo valor de JARVIS_DESKTOP_TOKEN no Render."
    response = requests.post(f"{cfg['url']}/api/pair/start", headers={"Authorization": f"Bearer {token}"}, timeout=20)
    data = response.json()
    if not response.ok or not data.get("ok"):
        return f"Não consegui gerar o código remoto: {data.get('error', response.status_code)}"
    return f"Código do Render: {data['code']} (expira em {data.get('expires_in', 600) // 60} min). Abra {cfg['url']} no iPhone e conecte."
