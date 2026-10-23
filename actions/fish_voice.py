"""Fish Audio PT-BR speech, restricted to the documented free model."""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
TOKEN_FILE = BASE_DIR / "config" / ".fish-token.dpapi"
SETTINGS_FILE = BASE_DIR / "config" / "fish_voice.json"
VOICE_ID = "a5b93aeddcc948c19ea04f0afe9d178c"
VOICE_NAME = "Jarvis UCM PT-BR"
VOICE_URL = f"https://fish.audio/pt/m/{VOICE_ID}/"
FREE_MODEL = "s2.1-pro-free"
API_KEYS_URL = "https://fish.audio/app/api-keys/"
SAMPLE_RATE = 24000
MAX_AUDIO_BYTES = 24 * 1024 * 1024
TEST_TEXT = "Olá. Sou o Jarvis. A voz em português brasileiro está pronta."


class FishVoiceError(RuntimeError):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


def read_settings() -> dict:
    defaults = {"enabled": True, "speed": 1.0}
    try:
        value = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        speed = float(value.get("speed", 1.0))
        return {"enabled": value.get("enabled", True) is True,
                "speed": max(0.5, min(1.5, speed))}
    except FileNotFoundError:
        return defaults
    except (OSError, ValueError, TypeError, AttributeError):
        return {"enabled": False, "speed": 1.0}


def save_settings(enabled: bool, speed: float = 1.0) -> None:
    value = {"enabled": bool(enabled), "speed": max(0.5, min(1.5, float(speed))),
             "reference_id": VOICE_ID, "voice_name": VOICE_NAME, "model": FREE_MODEL}
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = SETTINGS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(SETTINGS_FILE)


def read_key() -> str:
    if TOKEN_FILE.exists():
        try:
            import win32crypt
            return win32crypt.CryptUnprotectData(TOKEN_FILE.read_bytes(), None, None, None, 0)[1].decode("utf-8")
        except Exception:
            return ""
    return os.environ.get("FISH_API_KEY", "").strip()


def save_key(key: str) -> None:
    key = key.strip()
    if key.startswith("hf_"):
        raise FishVoiceError("Use uma chave Fish Audio. O token Hugging Face não serve aqui.")
    if len(key) < 8 or re.search(r"\s", key):
        raise FishVoiceError("Cole a chave Fish Audio completa, sem espaços.")
    try:
        import win32crypt
        encrypted = win32crypt.CryptProtectData(key.encode("utf-8"), "Jarvis Fish Audio", None, None, None, 0)
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp = TOKEN_FILE.with_name(TOKEN_FILE.name + ".tmp")
        try:
            temp.write_bytes(encrypted)
            temp.replace(TOKEN_FILE)
        finally:
            temp.unlink(missing_ok=True)
    except Exception:
        raise FishVoiceError("Não foi possível salvar a chave com a proteção do Windows.") from None


def voice_status() -> str:
    if not read_settings()["enabled"]:
        return "Voz original selecionada. Fish Audio desativado."
    if not read_key():
        return "Jarvis UCM PT-BR selecionado; falta salvar a chave Fish Audio."
    return "Jarvis UCM PT-BR configurado. Modelo gratuito; disponibilidade confirmada ao gerar."


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def synthesize(text: str, key: str | None = None, speed: float = 1.0) -> bytes:
    """Return PCM16 mono 24 kHz. Never retry using a paid model."""
    key = key or read_key()
    if not key:
        raise FishVoiceError("Falta configurar a chave Fish Audio.")
    if not text.strip():
        raise FishVoiceError("Não há texto para falar.")
    payload = {
        "text": text, "reference_id": VOICE_ID, "format": "pcm", "sample_rate": SAMPLE_RATE,
        "normalize": False, "latency": "balanced", "chunk_length": 100,
        "prosody": {"speed": max(0.5, min(1.5, float(speed))), "volume": 0, "normalize_loudness": True},
    }
    request = urllib.request.Request(
        "https://api.fish.audio/v1/tts", data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                 "model": FREE_MODEL, "User-Agent": "Jarvis-Fish-Voice/1.0"},
    )
    try:
        opener = urllib.request.build_opener(_NoRedirect())
        with opener.open(request, timeout=20) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            if "json" in content_type or "text/" in content_type:
                raise FishVoiceError("O Fish Audio não retornou áudio PCM.")
            chunks, size = [], 0
            deadline = time.monotonic() + 60
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_AUDIO_BYTES or time.monotonic() > deadline:
                    raise FishVoiceError("A resposta de voz excedeu o limite; usando a voz original.")
                chunks.append(chunk)
            pcm = b"".join(chunks)
    except urllib.error.HTTPError as exc:
        messages = {401: "Chave Fish Audio inválida.", 403: "Conta sem acesso à voz ou ao modelo gratuito.",
                    402: "O modelo gratuito não está disponível para esta conta. Nenhum modelo pago foi solicitado.",
                    404: "Voz ou modelo gratuito indisponível.", 429: "Limite temporário do Fish Audio; tente depois.",
                    503: "Fish Audio temporariamente indisponível."}
        status = exc.code
        exc.close()
        raise FishVoiceError(messages.get(status, f"Fish Audio respondeu HTTP {status}."), status) from None
    except (OSError, urllib.error.URLError):
        raise FishVoiceError("Não foi possível acessar o Fish Audio agora.") from None
    if not pcm or len(pcm) % 2 or pcm[:4] in (b"RIFF", b"OggS"):
        raise FishVoiceError("Áudio PCM vazio ou inválido; usando a voz original.")
    return pcm


async def stream_fish(text_queue, key, speed, on_audio):
    """Stream incremental text and PCM concurrently; never race a latency timer."""
    import msgpack
    import websockets
    request = {
        "text": "", "reference_id": VOICE_ID, "format": "pcm", "sample_rate": SAMPLE_RATE,
        "normalize": False, "latency": "balanced", "chunk_length": 100, "min_chunk_length": 20,
        "prosody": {"speed": speed, "volume": 0, "normalize_loudness": True},
    }
    started = time.monotonic()
    stats = {"first_audio_seconds": None, "audio_bytes": 0}
    try:
        async with websockets.connect(
            "wss://api.fish.audio/v1/tts/live",
            additional_headers={"Authorization": "Bearer " + key, "model": FREE_MODEL},
            open_timeout=30, ping_interval=20, ping_timeout=60, close_timeout=5,
            max_size=2 * 1024 * 1024, compression=None,
        ) as ws:
            await ws.send(msgpack.packb({"event": "start", "request": request}, use_bin_type=True))
            stopped = asyncio.Event()

            async def send_text():
                buffered_words = 0
                while True:
                    text = await text_queue.get()
                    if text is None:
                        stopped.set()
                        await ws.send(msgpack.packb({"event": "stop"}, use_bin_type=True))
                        return
                    await ws.send(msgpack.packb({"event": "text", "text": text}, use_bin_type=True))
                    buffered_words += len(text.split())
                    if buffered_words >= 7 or text.rstrip().endswith((".", "!", "?", ":", ";")):
                        await ws.send(msgpack.packb({"event": "flush"}, use_bin_type=True))
                        buffered_words = 0

            async def receive_audio():
                carry = b""
                async for raw in ws:
                    event = msgpack.unpackb(raw, raw=False)
                    kind = event.get("event")
                    if kind == "audio":
                        chunk = event.get("audio", b"")
                        if not isinstance(chunk, bytes):
                            raise FishVoiceError("Fish retornou um bloco de áudio inválido.")
                        carry += chunk
                        pcm, carry = carry[:len(carry) // 2 * 2], carry[len(carry) // 2 * 2:]
                        if pcm:
                            if not stats["audio_bytes"] and pcm[:4] in (b"RIFF", b"OggS"):
                                raise FishVoiceError("Fish retornou um formato de áudio incompatível.")
                            stats["audio_bytes"] += len(pcm)
                            if stats["audio_bytes"] > MAX_AUDIO_BYTES:
                                raise FishVoiceError("O áudio do Fish excedeu o limite de tamanho.")
                            if stats["first_audio_seconds"] is None:
                                stats["first_audio_seconds"] = time.monotonic() - started
                            on_audio(pcm)
                    elif kind == "finish":
                        if event.get("reason") != "stop" or carry or not stats["audio_bytes"] or not stopped.is_set():
                            raise FishVoiceError("Fish informou falha ou áudio incompleto na transmissão.")
                        return
                    elif kind == "error":
                        raise FishVoiceError("Fish informou erro na transmissão.")
                raise FishVoiceError("A conexão Fish foi encerrada antes de concluir a voz.")

            async with asyncio.TaskGroup() as group:
                group.create_task(send_text())
                group.create_task(receive_audio())
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        # Do not expose server payloads, websocket headers or credentials.
        errors = list(getattr(exc, "exceptions", [exc]))
        known = next((e for e in errors if isinstance(e, FishVoiceError)), None)
        if known:
            raise known from None
        status = getattr(getattr(exc, "response", None), "status_code", 0)
        raise FishVoiceError("Não foi possível concluir a transmissão Fish Audio.", status) from None
    stats["total_seconds"] = time.monotonic() - started
    return stats


class FishVoiceSession:
    """Start Fish during the Gemini reply; keep native audio solely for failure."""
    def __init__(self, emit, report, allowed=lambda: True, synth=None, config=None,
                 streamer=None, discard_audio=None):
        self.emit, self.report, self.allowed = emit, report, allowed
        self.synth = synth or synthesize
        self.streamer = streamer or stream_fish
        self.discard_audio = discard_audio or (lambda: None)
        self.config = config or (lambda: (read_settings(), read_key()))
        self.jobs = asyncio.Queue()
        self._turns = {}
        self._current = None
        self._serial = 0

    @property
    def pending(self):
        return bool(self._turns)

    def select(self):
        if self._current is None:
            settings, key = self.config()
            self._serial += 1
            selected = bool(settings.get("enabled") and key)
            turn = {"id": self._serial, "key": key, "speed": settings.get("speed", 1.0),
                    "selected": selected, "native": [], "text": [], "size": 0,
                    "queue": asyncio.Queue(), "finished": asyncio.Event(), "cancelled": False,
                    "task": None, "started": False, "audio_bytes": 0,
                    "native_streaming": False}
            self._current = turn
            if selected:
                self._turns[turn["id"]] = turn
        return self._current["selected"]

    def capture(self, chunk: bytes) -> bool:
        if not self.select():
            return False
        turn = self._current
        turn["native"].append(chunk)
        turn["size"] += len(chunk)
        # Fish is the selected voice.  Retain Gemini's chunks as a fallback,
        # but do not play them before Fish has a chance to receive the output
        # transcript and start streaming.  The old behaviour marked Gemini as
        # the winner on its first chunk, which made Fish silent on every
        # otherwise healthy turn.
        return True

    def feed_text(self, text: str):
        if not text or not self.select() or not self.allowed():
            return
        turn = self._current
        piece = (" " if turn["text"] else "") + text
        turn["text"].append(text)
        turn["queue"].put_nowait(piece)
        if not turn["started"]:
            turn["started"] = True
            self.jobs.put_nowait(turn)

    def finish(self, text: str):
        self.select()
        turn = self._current
        if turn["selected"] and not turn["text"] and text.strip():
            self.feed_text(text)
        self._current = None
        turn["finished"].set()
        turn["queue"].put_nowait(None)
        if turn["selected"] and not turn["started"]:
            # Missing Gemini transcript is a real unavailable-Fish input, not a slow response.
            if self.allowed() and not turn["cancelled"]:
                for chunk in turn["native"]:
                    self.emit(chunk, None)
            self._turns.pop(turn["id"], None)

    def cancel(self):
        for turn in list(self._turns.values()):
            turn["cancelled"] = True
            turn["finished"].set()
            if turn["task"]:
                turn["task"].cancel()
            turn["native"].clear()
        self._turns.clear()
        self._current = None
        while not self.jobs.empty():
            self.jobs.get_nowait()
            self.jobs.task_done()

    def _emit_stream(self, turn, pcm):
        if not turn["cancelled"] and self.allowed():
            if not turn["audio_bytes"]:
                self.report("VOZ: Fish PT-BR em streaming.")
                # Fish won the race; discard native chunks still waiting to play.
                self.discard_audio()
            turn["audio_bytes"] += len(pcm)
            self.emit(pcm, VOICE_NAME)

    async def _speak_turn(self, turn):
        try:
            stats = await self.streamer(turn["queue"], turn["key"], turn["speed"],
                                        lambda pcm: self._emit_stream(turn, pcm))
            if isinstance(stats, dict) and stats.get("first_audio_seconds") is not None:
                self.report(f"VOZ: Primeiro áudio Fish em {stats['first_audio_seconds']:.2f}s após iniciar transmissão.")
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            # A failed WebSocket can still recover with the same free Fish voice over HTTP.
            if turn["cancelled"]:
                return
            self.report("VOZ: Transmissão Fish falhou; tentando recuperar a mesma voz.")
        await turn["finished"].wait()
        if turn["cancelled"] or not self.allowed():
            return
        try:
            pcm = await asyncio.to_thread(self.synth, " ".join(turn["text"]), turn["key"], turn["speed"])
            if not turn["cancelled"] and self.allowed() and not turn.get("native_streaming"):
                if turn["audio_bytes"]:
                    self.discard_audio()
                self.emit(pcm, VOICE_NAME)
                self.report("VOZ: Fish recuperado pela conexão HTTP.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not turn["cancelled"] and self.allowed() and not turn.get("native_streaming"):
                message = str(exc) if isinstance(exc, FishVoiceError) else "Fish Audio indisponível."
                if turn["audio_bytes"]:
                    self.discard_audio()
                self.report("VOZ: " + message + " As duas tentativas Fish falharam; usando Gemini.")
                for chunk in turn["native"]:
                    self.emit(chunk, None)

    async def run(self):
        try:
            while True:
                turn = await self.jobs.get()
                try:
                    if turn["cancelled"] or not self.allowed():
                        continue
                    turn["task"] = asyncio.create_task(self._speak_turn(turn))
                    try:
                        await turn["task"]
                    except asyncio.CancelledError:
                        if not turn["cancelled"]:
                            raise
                finally:
                    self._turns.pop(turn["id"], None)
                    turn["native"].clear()
                    self.jobs.task_done()
        finally:
            self.cancel()
