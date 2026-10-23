"""Local privacy guard for calls.

The guard only inspects the title and executable of the foreground window. It
never records, transcribes, or stores call audio.  Its single purpose is to
tell the live-audio loop when microphone data must not leave the PC.
"""

from __future__ import annotations

import ctypes
import threading
import time
from dataclasses import dataclass

try:
    import psutil
except Exception:  # pragma: no cover - optional at import time
    psutil = None


POLL_SECONDS = 0.8

# App names alone are deliberately not enough for Discord/WhatsApp: both are
# often open without a call.  A call needs a call-specific window title.
CALL_TITLE_MARKERS = (
    "google meet",
    "meet.google.com",
    "zoom meeting",
    "zoom workplace",
    "microsoft teams meeting",
    "teams meeting",
    "webex meeting",
    "jitsi meet",
    "voice connected",
    "in a call",
    "call in progress",
    "incoming call",
    "outgoing call",
    "em chamada",
    "em uma chamada",
    "chamada em andamento",
    "reuniao",
    "reunião",
)


@dataclass(frozen=True)
class CallContext:
    active: bool
    reason: str = ""
    title: str = ""
    process: str = ""


class _CallPrivacyGuard:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._enabled = False
        self._manual_call = False
        self._context = CallContext(False)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @staticmethod
    def _foreground() -> tuple[str, str]:
        """Return title/process for only the current foreground window."""
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return "", ""
            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(max(1, length + 1))
            user32.GetWindowTextW(hwnd, buffer, len(buffer))
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            process = ""
            if psutil is not None and pid.value:
                try:
                    process = psutil.Process(pid.value).name() or ""
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return buffer.value.strip(), process.strip()
        except Exception:
            return "", ""

    def _detect(self) -> CallContext:
        with self._lock:
            manual = self._manual_call
        if manual:
            return CallContext(True, "modo call manual")

        title, process = self._foreground()
        haystack = f"{title} {process}".casefold()
        marker = next((item for item in CALL_TITLE_MARKERS if item in haystack), "")
        if marker:
            return CallContext(True, f"janela de chamada: {marker}", title, process)
        return CallContext(False, "", title, process)

    def _run(self) -> None:
        while not self._stop.wait(POLL_SECONDS):
            context = self._detect()
            with self._lock:
                self._context = context

    def start(self) -> None:
        with self._lock:
            self._enabled = True
            self._stop.clear()
            alive = self._thread is not None and self._thread.is_alive()
        if not alive:
            self._thread = threading.Thread(target=self._run, name="JarvisCallPrivacy", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._enabled = False
            self._manual_call = False
            self._context = CallContext(False)
            self._stop.set()

    def set_manual(self, active: bool) -> None:
        self.start()
        with self._lock:
            self._manual_call = bool(active)
            self._context = CallContext(bool(active), "modo call manual" if active else "")

    def context(self) -> CallContext:
        with self._lock:
            if not self._enabled:
                return CallContext(False)
            return self._context

    def status(self) -> dict:
        context = self.context()
        with self._lock:
            return {
                "enabled": self._enabled,
                "active": context.active,
                "reason": context.reason,
                "title": context.title,
                "process": context.process,
                "manual_call": self._manual_call,
            }


_GUARD = _CallPrivacyGuard()


def is_call_privacy_active() -> bool:
    return _GUARD.context().active


def call_privacy(parameters=None, response=None, player=None, speak=None):
    """Tool entrypoint: start/stop/status/call_on/call_off."""
    del response, speak
    parameters = parameters or {}
    action = str(parameters.get("action") or "status").strip().casefold()

    if action in {"start", "on", "enable", "enabled", "monitor"}:
        _GUARD.start()
        message = "Proteção de chamadas ativa. Áudio é bloqueado em janelas de reunião detectadas."
    elif action in {"stop", "off", "disable", "disabled"}:
        _GUARD.stop()
        message = "Proteção de chamadas desativada."
    elif action in {"call_on", "manual_on", "modo_call", "call"}:
        _GUARD.set_manual(True)
        message = "Modo call ativo. O microfone do JARVIS está isolado até você encerrar o modo call."
    elif action in {"call_off", "manual_off", "fim_call", "end_call"}:
        _GUARD.set_manual(False)
        message = "Modo call encerrado. Proteção automática continua ativa."
    elif action in {"status", "info"}:
        data = _GUARD.status()
        state = "BLOQUEANDO ÁUDIO" if data["active"] else "em espera"
        message = f"Proteção de chamadas: {state}. Motivo: {data['reason'] or 'nenhuma chamada detectada'}"
    else:
        return "Ação inválida. Use start, stop, status, call_on ou call_off."

    if player and hasattr(player, "write_log"):
        player.write_log(f"SYS: {message}")
    return message
