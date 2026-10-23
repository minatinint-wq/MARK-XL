"""Offline wake phrase detector used only while Call Privacy is active.

Audio is kept in RAM for a few seconds, transcribed locally with the already
cached faster-whisper model and immediately discarded. Nothing is written to
disk or sent to a network service.
"""

from __future__ import annotations

import queue
import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import Callable

import numpy as np


SAMPLE_RATE = 16_000
WINDOW_SECONDS = 3.0
MIN_WINDOW_SECONDS = 1.25
SCAN_INTERVAL_SECONDS = 1.1
COOLDOWN_SECONDS = 8.0


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", value.casefold())).strip()


def _model_path() -> Path | None:
    cache = Path.home() / ".cache" / "huggingface" / "hub" / "models--Systran--faster-whisper-base" / "snapshots"
    if not cache.is_dir():
        return None
    snapshots = sorted((item for item in cache.iterdir() if item.is_dir()), key=lambda item: item.stat().st_mtime, reverse=True)
    return snapshots[0] if snapshots else None


class _CallWake:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._callback: Callable[[], None] | None = None
        self._buffer = bytearray()
        self._last_scan = 0.0
        self._last_trigger = 0.0
        self._jobs: queue.Queue[bytes] = queue.Queue(maxsize=1)
        self._worker: threading.Thread | None = None
        self._model = None
        self._ready = False
        self._error = ""

    def start(self, callback: Callable[[], None]) -> None:
        with self._lock:
            self._callback = callback
            self._ready = True
            alive = self._worker is not None and self._worker.is_alive()
        if not alive:
            self._worker = threading.Thread(target=self._run, name="JarvisCallWake", daemon=True)
            self._worker.start()

    def ingest(self, data: bytes, sample_rate: int) -> None:
        if not data or int(sample_rate or 0) != SAMPLE_RATE:
            return
        with self._lock:
            if not self._ready:
                return
            self._buffer.extend(data)
            max_bytes = int(SAMPLE_RATE * WINDOW_SECONDS * 2)
            if len(self._buffer) > max_bytes:
                del self._buffer[:-max_bytes]
            now = time.monotonic()
            min_bytes = int(SAMPLE_RATE * MIN_WINDOW_SECONDS * 2)
            if len(self._buffer) < min_bytes or now - self._last_scan < SCAN_INTERVAL_SECONDS or self._jobs.full():
                return
            self._last_scan = now
            chunk = bytes(self._buffer)
        try:
            self._jobs.put_nowait(chunk)
        except queue.Full:
            pass

    def _load_model(self):
        if self._model is not None:
            return self._model
        path = _model_path()
        if path is None:
            self._error = "Modelo local faster-whisper-base não encontrado."
            return None
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(str(path), device="cpu", compute_type="int8")
            return self._model
        except Exception as exc:
            self._error = str(exc)[:180]
            return None

    def _run(self) -> None:
        while True:
            audio = self._jobs.get()
            model = self._load_model()
            if model is None:
                continue
            try:
                pcm = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
                segments, _ = model.transcribe(
                    pcm,
                    language="pt",
                    beam_size=1,
                    vad_filter=True,
                    condition_on_previous_text=False,
                )
                text = _normalize(" ".join(segment.text for segment in segments))
                if "jarvis" not in text or not any(fragment in text for fragment in ("ta ai", "esta ai", "ta aqui", "esta aqui")):
                    continue
                now = time.monotonic()
                with self._lock:
                    if now - self._last_trigger < COOLDOWN_SECONDS:
                        continue
                    self._last_trigger = now
                    callback = self._callback
                if callback:
                    callback()
            except Exception as exc:
                self._error = str(exc)[:180]

    def status(self) -> dict:
        with self._lock:
            return {
                "enabled": self._ready,
                "model_loaded": self._model is not None,
                "model_path": str(_model_path() or ""),
                "error": self._error,
            }


_WAKE = _CallWake()


def start_call_wake(callback: Callable[[], None]) -> None:
    _WAKE.start(callback)


def ingest_call_wake_audio(data: bytes, sample_rate: int = SAMPLE_RATE) -> None:
    _WAKE.ingest(data, sample_rate)


def call_wake_status() -> dict:
    return _WAKE.status()
