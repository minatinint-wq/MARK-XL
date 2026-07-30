"""Windows toast notification listener for JARVIS."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "windows_notifications.json"
EVENTS_PATH = BASE_DIR / "memory" / "windows_notifications.json"
POLL_SECONDS = 2.5
MAX_EVENTS = 150


def _config() -> dict[str, Any]:
    config: dict[str, Any] = {"speak": True, "muted_apps": []}
    try:
        saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            config.update(saved)
    except Exception:
        pass
    return config


def _save_config(config: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_event(event: dict[str, Any]) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        events = json.loads(EVENTS_PATH.read_text(encoding="utf-8")) if EVENTS_PATH.exists() else []
        events = events if isinstance(events, list) else []
    except Exception:
        events = []
    EVENTS_PATH.write_text(json.dumps((events + [event])[-MAX_EVENTS:], ensure_ascii=False, indent=2), encoding="utf-8")


def _notification_text(item: Any) -> tuple[str, str, str]:
    app = "Windows"
    try:
        app = str(item.app_info.display_info.display_name or app)
    except Exception:
        pass
    parts: list[str] = []
    try:
        for binding in item.notification.visual.bindings:
            for element in binding.get_text_elements():
                value = str(element.text or "").strip()
                if value and value not in parts:
                    parts.append(value)
    except Exception:
        pass
    text = " — ".join(parts)[:600] or "Nova notificação recebida."
    return str(item.id), app[:120], text


class _NotificationMonitor:
    def __init__(self) -> None:
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.seen: set[str] = set()
        self.ready = False
        self.speak: Callable[[str], Any] | None = None
        self.log: Callable[[str], Any] | None = None
        self.lock = threading.Lock()

    def _listener(self):
        from winrt.windows.ui.notifications.management import UserNotificationListener
        return UserNotificationListener.current

    def _items(self):
        from winrt.windows.ui.notifications import NotificationKinds
        return asyncio.run(self._listener().get_notifications_async(NotificationKinds.TOAST))

    def start(self, speak: Callable[[str], Any] | None = None, log: Callable[[str], Any] | None = None) -> str:
        with self.lock:
            self.speak = speak or self.speak
            self.log = log or self.log
            if self.thread and self.thread.is_alive():
                return "Leitor de notificações do Windows já está ativo."
            try:
                from winrt.windows.ui.notifications.management import UserNotificationListenerAccessStatus
                listener = self._listener()
                access = listener.get_access_status()
                if access != UserNotificationListenerAccessStatus.ALLOWED:
                    access = asyncio.run(listener.request_access_async())
                if access != UserNotificationListenerAccessStatus.ALLOWED:
                    return "Permissão para ler notificações não foi concedida no Windows."
            except Exception as exc:
                return f"Não consegui ativar o leitor de notificações: {exc}"
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._run, name="JarvisWindowsNotifications", daemon=True)
            self.thread.start()
        return "Leitor de notificações do Windows ativo."

    def stop(self) -> str:
        self.stop_event.set()
        return "Leitor de notificações do Windows parado."

    def _run(self) -> None:
        # Establish a baseline: existing toasts are history, not new alerts.
        try:
            self.seen = {str(item.id) for item in self._items()}
            self.ready = True
        except Exception as exc:
            if self.log:
                self.log(f"SYS: leitor de notificações indisponível: {exc}")
            return
        while not self.stop_event.wait(POLL_SECONDS):
            try:
                items = self._items()
            except Exception:
                continue
            config = _config()
            muted = {str(name).casefold() for name in config.get("muted_apps", [])}
            for item in items:
                notification_id, app, text = _notification_text(item)
                if notification_id in self.seen:
                    continue
                self.seen.add(notification_id)
                event = {"id": notification_id, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "app": app, "text": text}
                _save_event(event)
                if self.log:
                    self.log(f"NOTIF: {app} — {text}")
                if config.get("speak", True) and app.casefold() not in muted and self.speak:
                    self.speak(f"Leia de forma curta e objetiva: nova notificação de {app}. {text}")

    def status(self) -> str:
        running = bool(self.thread and self.thread.is_alive())
        config = _config()
        return f"Leitor de notificações: {'ativo' if running else 'parado'} | voz: {'ligada' if config.get('speak', True) else 'desligada'} | apps silenciados: {len(config.get('muted_apps', []))}."


_MONITOR = _NotificationMonitor()


def windows_notifications(parameters: dict[str, Any] | None = None, player=None, speak=None, **_: Any) -> str:
    params = parameters or {}
    action = str(params.get("action") or "status").strip().lower()
    if action in {"start", "iniciar", "connect", "conectar"}:
        log = getattr(player, "write_log", None)
        return _MONITOR.start(speak=speak, log=log)
    if action in {"stop", "parar", "disconnect", "desconectar"}:
        return _MONITOR.stop()
    if action in {"mute", "silenciar"}:
        app = str(params.get("app") or "").strip()
        if not app:
            return "Qual aplicativo deve ser silenciado?"
        config = _config()
        muted = list(dict.fromkeys([*config.get("muted_apps", []), app]))
        config["muted_apps"] = muted
        _save_config(config)
        return f"Notificações de {app} serão registradas, mas não faladas."
    if action in {"unmute", "ativar_app"}:
        app = str(params.get("app") or "").strip().casefold()
        config = _config()
        config["muted_apps"] = [name for name in config.get("muted_apps", []) if str(name).casefold() != app]
        _save_config(config)
        return "Aplicativo removido da lista silenciosa."
    if action in {"voice_off", "voz_off"}:
        config = _config(); config["speak"] = False; _save_config(config)
        return "Leitor continua registrando, mas não fala novas notificações."
    if action in {"voice_on", "voz_on"}:
        config = _config(); config["speak"] = True; _save_config(config)
        return "Leitura por voz de notificações ativada."
    return _MONITOR.status()
