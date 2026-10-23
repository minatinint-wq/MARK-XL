# live_vision.py - Modo visão em tempo real com análise e interação
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

try:
    import cv2
    _CV2 = True
except ImportError:
    _CV2 = False

try:
    import mss
    import mss.tools
    _MSS = True
except ImportError:
    _MSS = False

try:
    import PIL.Image
    _PIL = True
except ImportError:
    _PIL = False

from google import genai
from google.genai import types as gtypes

from actions.vision_desktop_context import make_vision_turn_parts

try:
    from actions.hand_braille import (
        analyze_camera_braille,
        capture_camera_frame,
        open_camera_capture,
        wants_hand_braille,
    )
    _HAND_BRAILLE = True
except Exception as e:
    print(f"[LiveVision] ⚠️ Hand/Braille module unavailable: {e}")
    _HAND_BRAILLE = False

try:
    from actions.vision_learning import (
        braille_confirmation_settings,
        confirm_braille_signal,
        ensure_vision_preferences,
        remember_braille_observation,
        remember_vision_event,
    )
    _VISION_LEARNING = True
except Exception as e:
    print(f"[LiveVision] ⚠️ Vision learning unavailable: {e}")
    _VISION_LEARNING = False

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE        = _base_dir()
_CONFIG_PATH = _BASE / "config" / "api_keys.json"

def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _get_api_key() -> str:
    key = _load_config().get("gemini_api_key", "")
    if not key:
        raise RuntimeError("gemini_api_key not found in config.")
    return key

_LIVE_MODEL         = "gemini-2.5-flash-native-audio-latest"
_CHANNELS           = 1
_RECEIVE_SAMPLE_RATE = 24_000
_CHUNK_SIZE         = 1_024
_VISION_SPEECH_PAUSE = 0.45

_IMG_MAX_W = 1600
_IMG_MAX_H = 900
_JPEG_Q    = 88
_VISION_SEND_RETRIES = 1


def _config_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "on", "enabled"}


def _vision_speech_enabled() -> bool:
    env_value = os.environ.get("MARK_XL_VISION_SPEECH")
    if env_value is not None:
        return _config_bool(env_value)
    return _config_bool(_load_config().get("vision_speech_enabled"), False)


_SYSTEM_PROMPT = (
    "Voce e JARVIS, um assistente avancado com visao em tempo real. "
    "Responda SEMPRE em portugues brasileiro natural, mesmo quando ferramentas, janelas ou textos estiverem em ingles. "
    "Nao chame o usuario de 'sir'. "
    "Voce esta observando a tela do usuario em tempo real. "
    ""
    "TAREFA PRINCIPAL: analisar o que esta na tela e guiar interacoes do usuario. "
    ""
    "Quando vir YouTube ou video:"
    "- Identifique player, play/pause, barra de progresso, volume, tela cheia, busca e comentarios."
    "- Se o usuario pedir para agir, indique o controle certo com clareza."
    ""
    "Quando vir navegador:"
    "- Identifique botoes, links, formularios, campos e menus."
    "- Informe onde estao os elementos e quais acoes estao disponiveis."
    ""
    "Quando vir Discord ou uma chamada/call:"
    "- Foque em quem esta na chamada, nomes visiveis, cards de voz, lista lateral, avatares e quem parece estar falando."
    "- Nao responda apenas que o Discord esta aberto."
    "- Leia nomes somente quando estiverem legiveis; se nao der para ler, diga que precisa ampliar/abrir a lista de participantes."
    "- Nunca invente participantes."
    ""
    "Quando vir qualquer aplicativo:"
    "- Identifique janelas, botoes, menus e barras."
    "- Descreva com clareza e seja especifico."
    ""
    "IMPORTANTE: seja conciso, mas detalhe nomes/participantes quando o usuario perguntar. "
    "Use browser_control ou computer_control se o usuario quiser que voce aja."
)

def _compress(img_bytes: bytes, source_format: str = "PNG") -> tuple[bytes, str]:
    if not _PIL:
        return img_bytes, f"image/{source_format.lower()}"

    try:
        img = PIL.Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img.thumbnail((_IMG_MAX_W, _IMG_MAX_H), PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_Q, optimize=False)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        print(f"[LiveVision] ⚠️ Image compress failed: {e}")
        return img_bytes, f"image/{source_format.lower()}"

def capture_screen() -> tuple[bytes, str]:
    if not _MSS:
        raise RuntimeError("mss is not installed. Run: pip install mss")

    with mss.mss() as sct:
        monitors = sct.monitors
        target   = monitors[1] if len(monitors) > 1 else monitors[0]
        shot     = sct.grab(target)
        png      = mss.tools.to_png(shot.rgb, shot.size)

    return _compress(png, "PNG")

def capture_camera(camera_index: int = 0) -> tuple[bytes, str]:
    """Capture a single frame from the specified camera."""
    if not _CV2:
        raise RuntimeError("OpenCV (cv2) is not installed. Run: pip install opencv-python")

    if _HAND_BRAILLE:
        frame = capture_camera_frame(camera_index=camera_index, warmup=12, width=1280, height=720)
    else:
        cap = cv2.VideoCapture(camera_index)
        try:
            if not cap.isOpened():
                raise RuntimeError(f"Could not open camera {camera_index}")

            ret, frame = cap.read()
            if not ret:
                raise RuntimeError("Failed to capture frame from camera")
        finally:
            cap.release()

    _, png = cv2.imencode(".png", frame)
    return _compress(png.tobytes(), "PNG")

def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "sim"}
    return bool(value)

def _capture_frame(mode: str) -> tuple[bytes, str]:
    if mode == "camera":
        return capture_camera()
    return capture_screen()

def _is_stop_request(mode: str, user_text: str) -> bool:
    if mode in {"stop", "off", "disable", "parar"}:
        return True

    text = user_text.lower()
    stop_phrases = (
        "stop live",
        "stop vision",
        "stop live view",
        "parar live",
        "parar visão",
        "parar visao",
        "desligar live",
        "desligar visão",
        "desligar visao",
        "encerrar live",
        "encerrar visão",
        "encerrar visao",
    )
    return any(phrase in text for phrase in stop_phrases)

def _wants_camera_vision(user_text: str) -> bool:
    text = (user_text or "").lower()
    return any(
        phrase in text
        for phrase in (
            "modo visão",
            "modo visao",
            "minha casa",
            "ver a casa",
            "ve minha casa",
            "vê minha casa",
            "camera da casa",
            "câmera da casa",
            "webcam",
        )
    )

def _wants_recording(params: dict, user_text: str) -> bool:
    if _as_bool(params.get("record", False)):
        return True
    text = (user_text or "").lower()
    return any(term in text for term in ("grava", "gravar", "gravando", "record", "recording"))

class _LiveVisionSession:
    def __init__(self):
        self._loop:       Optional[asyncio.AbstractEventLoop] = None
        self._thread:     Optional[threading.Thread]          = None
        self._session                                          = None
        self._out_queue:  Optional[asyncio.Queue]             = None
        self._audio_in:   Optional[asyncio.Queue]             = None
        self._ready_evt:  threading.Event                     = threading.Event()
        self._player                                           = None
        self._lock:       threading.Lock                       = threading.Lock()
        self._active:     bool                                 = False
        self._speak_func: Optional[Callable]                   = None
        self._capture_thread: Optional[threading.Thread]       = None
        self._capture_stop: threading.Event                    = threading.Event()
        self._audio_generation: int                            = 0
        self._drop_audio_until: float                          = 0.0
        self._speech_enabled: bool                              = False

    def start(self, player=None, speak=None, timeout: float = 60.0) -> None:
        with self._lock:
            self._player = player
            self._speak_func = speak
            self._active = True

            if not self._thread or not self._thread.is_alive():
                self._ready_evt.clear()
                self._thread = threading.Thread(
                    target=self._run_event_loop,
                    daemon=True,
                    name="LiveVisionThread",
                )
                self._thread.start()

        if not self._ready_evt.wait(timeout=timeout):
            self._active = False
            raise RuntimeError(f"LiveVision session did not connect within {timeout}s.")
        print("[LiveVision] ✅ Session ready")

    def stop(self) -> None:
        self.stop_continuous()
        self._active = False
        with self._lock:
            if self._session:
                self._session = None
            self._ready_evt.clear()

    def analyze_frame(self, image_bytes: bytes, mime_type: str, user_text: str, mode: str = "screen") -> None:
        if not self._loop or not self._out_queue:
            print("[LiveVision] ⚠️ Session not started — dropping request")
            return
        asyncio.run_coroutine_threadsafe(
            self._out_queue.put((image_bytes, mime_type, user_text, mode, 0)),
            self._loop,
        )

    def is_ready(self) -> bool:
        return self._session is not None and self._active

    def start_continuous(self, mode: str, user_text: str, interval: float = 3.5) -> None:
        self.stop_continuous()
        self._capture_stop.clear()

        def worker() -> None:
            while not self._capture_stop.wait(interval):
                try:
                    image_bytes, mime_type = _capture_frame(mode)
                    print(f"[LiveVision] 🔁 Live frame: {len(image_bytes):,} bytes")
                    self.analyze_frame(image_bytes, mime_type, user_text, mode)
                except Exception as e:
                    print(f"[LiveVision] ❌ Continuous capture error: {e}")
                    break

        self._capture_thread = threading.Thread(
            target=worker,
            daemon=True,
            name="LiveVisionCaptureThread",
        )
        self._capture_thread.start()

    def stop_continuous(self) -> None:
        self._capture_stop.set()
        thread = self._capture_thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.5)
        self._capture_thread = None

    def _run_event_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._session_loop())

    async def _session_loop(self) -> None:
        self._out_queue = asyncio.Queue(maxsize=30)
        self._speech_enabled = _vision_speech_enabled()
        self._audio_in  = asyncio.Queue(maxsize=64) if self._speech_enabled else None

        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"},
        )
        config = gtypes.LiveConnectConfig(
            response_modalities=[gtypes.Modality.AUDIO],
            output_audio_transcription={},
            system_instruction=_SYSTEM_PROMPT,
            speech_config=gtypes.SpeechConfig(
                voice_config=gtypes.VoiceConfig(
                    prebuilt_voice_config=gtypes.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )

        backoff = 2.0
        while self._active:
            try:
                print("[LiveVision] 🔌 Connecting...")
                async with client.aio.live.connect(
                    model=_LIVE_MODEL, config=config
                ) as session:
                    self._session = session
                    self._ready_evt.set()
                    backoff = 2.0
                    print("[LiveVision] ✅ Connected")

                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._send_loop())
                        tg.create_task(self._recv_loop())
                        if self._speech_enabled:
                            tg.create_task(self._play_loop())

            except* Exception as eg:
                for exc in eg.exceptions:
                    print(f"[LiveVision] ⚠️ Session error: {exc}")
            finally:
                self._session = None
                self._ready_evt.clear()

            if not self._active:
                break
            print(f"[LiveVision] 🔄 Reconnecting in {backoff:.0f}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, 30.0)

    async def _send_loop(self) -> None:
        while True:
            item = await self._out_queue.get()
            if len(item) == 5:
                image_bytes, mime_type, user_text, mode, retry = item
            else:
                image_bytes, mime_type, user_text, mode = item
                retry = 0
            if not self._session:
                print("[LiveVision] ⚠️ No session — dropping image")
                continue
            try:
                self._begin_audio_generation(drop_window=0.0)
                await asyncio.sleep(_VISION_SPEECH_PAUSE)
                await self._session.send_client_content(
                    turns={
                        "parts": make_vision_turn_parts(
                            image_bytes,
                            mime_type,
                            user_text,
                            mode=mode,
                            log_prefix="[LiveVision]",
                        )
                    },
                    turn_complete=True,
                )
                print(f"[LiveVision] 📤 Sent {len(image_bytes):,} bytes")
            except Exception as e:
                print(f"[LiveVision] ⚠️ Send error: {e}")
                if retry < _VISION_SEND_RETRIES and self._out_queue:
                    try:
                        self._out_queue.put_nowait((image_bytes, mime_type, user_text, mode, retry + 1))
                        print("[LiveVision] 🔁 Requeued frame after send failure; reconnecting session.")
                    except asyncio.QueueFull:
                        print("[LiveVision] ⚠️ Retry queue full — frame dropped.")
                raise

    async def _recv_loop(self) -> None:
        transcript: list[str] = []
        try:
            async for response in self._session.receive():
                if response.data:
                    if self._speech_enabled and time.time() >= self._drop_audio_until:
                        self._put_audio_chunk_drop_oldest(response.data)

                sc = response.server_content
                if not sc:
                    continue

                if sc.output_transcription and sc.output_transcription.text:
                    chunk = sc.output_transcription.text.strip()
                    if chunk:
                        transcript.append(chunk)

                if sc.turn_complete:
                    if transcript and self._player:
                        full = re.sub(r"\s+", " ", " ".join(transcript)).strip()
                        if full:
                            self._player.write_log(f"Jarvis: {full}")
                            print(f"[LiveVision] 💬 {full}")
                            # Also execute any suggested browser actions
                            self._suggest_browser_actions(full)
                    transcript = []

        except Exception as e:
            print(f"[LiveVision] ⚠️ Recv error: {e}")
            raise

    def _begin_audio_generation(self, drop_window: float = 0.0) -> None:
        self._audio_generation += 1
        self._drop_audio_until = time.time() + max(0.0, drop_window)
        if not self._audio_in:
            return
        while True:
            try:
                self._audio_in.get_nowait()
            except asyncio.QueueEmpty:
                break

    def _put_audio_chunk_drop_oldest(self, chunk: bytes) -> None:
        if not self._audio_in:
            return
        item = (self._audio_generation, chunk)
        try:
            self._audio_in.put_nowait(item)
            return
        except asyncio.QueueFull:
            pass

        try:
            self._audio_in.get_nowait()
        except asyncio.QueueEmpty:
            pass

        try:
            self._audio_in.put_nowait(item)
        except asyncio.QueueFull:
            pass

    def _suggest_browser_actions(self, response_text: str) -> None:
        """Execute suggested browser actions based on the response."""
        if not self._speak_func:
            return

        response_lower = response_text.lower()

        # Extract action from response
        if "browser_control" in response_lower or "click" in response_lower or "type" in response_lower:
            # Let the main thread handle this
            pass

    async def _play_loop(self) -> None:
        if not self._speech_enabled or not self._audio_in:
            return
        try:
            import sounddevice as sd
            stream = sd.RawOutputStream(
                samplerate=_RECEIVE_SAMPLE_RATE,
                channels=_CHANNELS,
                dtype="int16",
                blocksize=_CHUNK_SIZE,
            )
            stream.start()
            try:
                while True:
                    chunk = await self._audio_in.get()
                    if isinstance(chunk, tuple) and len(chunk) == 2:
                        generation, chunk = chunk
                        if generation != self._audio_generation:
                            continue
                    await asyncio.to_thread(stream.write, chunk)
            except Exception as e:
                print(f"[LiveVision] ❌ Play error: {e}")
            finally:
                stream.stop()
                stream.close()
        except Exception as e:
            print(f"[LiveVision] ⚠️ Audio not available: {e}")

_session      = _LiveVisionSession()
_session_lock = threading.Lock()

class _CameraVisionProcessor:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def start(self, player=None, speak=None, fps: float = 8.0) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return

            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                args=(fps, player, speak),
                daemon=True,
                name="CameraVisionProcessor",
            )
            self._thread.start()

    def stop(self) -> bool:
        was_active = bool(self._thread and self._thread.is_alive())
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._thread = None
        return was_active

    def _run(self, fps: float, player=None, speak=None) -> None:
        cap = None
        try:
            if not _HAND_BRAILLE:
                raise RuntimeError("Camera helper is unavailable.")
            cap = open_camera_capture()
            fps = max(1.0, min(float(fps or 8.0), 20.0))
            frame_delay = 1.0 / fps
            while not self._stop.wait(frame_delay):
                ret, frame = cap.read()
                if not ret or frame is None or not frame.size:
                    continue

        except Exception as e:
            msg = f"Vision processing error: {e}"
            print(f"[LiveVision] ❌ {msg}")
            if player:
                try:
                    player.write_log(f"SYS: {msg}")
                except Exception:
                    pass
            if speak:
                try:
                    speak(msg)
                except Exception:
                    pass
        finally:
            if cap is not None:
                cap.release()

_vision_processor = _CameraVisionProcessor()

class _BrailleFingerMonitor:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._last_count: Optional[int] = None
        self._stable_count = 0
        self._conf_window: list[float] = []
        self._saved_count: Optional[int] = None

    def start(self, player=None, speak=None, interval: float = 1.0) -> None:
        with self._lock:
            self.stop()
            self._stop.clear()
            self._last_count = None
            self._stable_count = 0
            self._conf_window = []
            self._saved_count = None
            self._thread = threading.Thread(
                target=self._run,
                args=(player, speak, interval),
                daemon=True,
                name="BrailleFingerMonitor",
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.5)
        self._thread = None

    def _run(self, player=None, speak=None, interval: float = 1.0) -> None:
        while not self._stop.wait(interval):
            try:
                result = analyze_camera_braille()
            except Exception as e:
                print(f"[LiveVision] ⚠️ Braille monitor error: {e}")
                continue
            if _VISION_LEARNING:
                remember_braille_observation(result)
            if not result.detected:
                _publish_braille_result(result, player=player, speak=None, log=False)
                continue
            if result.finger_count == self._last_count:
                self._stable_count += 1
            else:
                self._last_count = result.finger_count
                self._stable_count = 1
                self._conf_window = []
                self._saved_count = None

            self._conf_window.append(float(result.confidence or 0.0))
            self._conf_window = self._conf_window[-8:]
            required_frames, min_confidence = braille_confirmation_settings() if _VISION_LEARNING else (5, 0.84)
            avg_confidence = sum(self._conf_window) / len(self._conf_window)

            if self._stable_count >= required_frames and avg_confidence >= min_confidence:
                payload = _confirmed_braille_payload(result, self._stable_count, avg_confidence)
                if _VISION_LEARNING and self._saved_count != result.finger_count:
                    saved = confirm_braille_signal(result, self._stable_count, avg_confidence)
                    payload["message"] += f" Conhecimento salvo no Obsidian: {saved['note_path']}"
                    self._saved_count = result.finger_count
                _publish_braille_result(payload, player=player, speak=speak)
                continue

            if self._stable_count > 1:
                _publish_braille_result(result, player=player, speak=None, log=False)
                continue
            self._last_count = result.finger_count
            _publish_braille_result(result, player=player, speak=speak)

_braille_monitor = _BrailleFingerMonitor()

def _publish_braille_result(result, player=None, speak=None, log: bool = True) -> None:
    message = result.get("message", "") if isinstance(result, dict) else getattr(result, "message", str(result))
    if player and hasattr(player, "update_braille_translation"):
        try:
            player.update_braille_translation(result)
        except Exception:
            pass

def _confirmed_braille_payload(result, stable_frames: int, avg_confidence: float) -> dict:
    return {
        "detected": True,
        "finger_count": result.finger_count,
        "braille": result.braille,
        "dots": result.dots,
        "confidence": 1.0,
        "message": (
            f"Confirmado 100%: {result.finger_count} dedo(s), sinal Braille {result.braille}. "
            f"Estavel por {stable_frames} frames; confianca media {avg_confidence:.2f}."
        ),
    }
    if player and log:
        try:
            player.write_log(f"Jarvis: {message}")
        except Exception:
            pass
    if speak:
        try:
            speak(message)
        except Exception:
            pass

def _ensure_session(player=None, speak=None) -> None:
    with _session_lock:
        if not _session.is_ready():
            _session.start(player=player, speak=speak)
        else:
            _session._player = player
            _session._speak_func = speak

def live_vision(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    """Start live vision mode - continuously analyze screen and interact."""
    if _VISION_LEARNING:
        ensure_vision_preferences()

    params    = parameters or {}
    user_text = params.get("text", "What do you see on screen? Describe briefly.").strip()
    mode      = params.get("mode", "screen").lower().strip()  # screen or camera
    # NVIDIA Camera Lab deterministic reroute
    request_key = user_text.casefold()
    requested_mode = str(params.get("provider") or params.get("camera_mode") or "").casefold()
    if (
        ("nvidia" in request_key and any(word in request_key for word in ("camera", "c\u00e2mera", "lab")))
        or requested_mode in {"nvidia", "nvidia_camera", "nvidia-camera"}
    ):
        from actions.nvidia_camera_lab import nvidia_camera_lab
        return nvidia_camera_lab({"action": "open"}, player=player)
    continuous = _as_bool(params.get("continuous", False))
    camera_vision = _wants_camera_vision(user_text)
    record_requested = _wants_recording(params, user_text)

    if _is_stop_request(mode, user_text):
        return stop_live_vision()

    if camera_vision:
        mode = "camera"
        continuous = True
    if record_requested:
        mode = "camera"
        continuous = True

    if mode not in {"screen", "camera"}:
        mode = "screen"

    print(f"[LiveVision] ▶ mode={mode}, continuous={continuous}")
    print(f"[LiveVision] 💬 Question: '{user_text}'")

    if mode == "camera" and _HAND_BRAILLE and wants_hand_braille(user_text):
        try:
            result = analyze_camera_braille()
            _publish_braille_result(result, player=player, speak=speak)
            interval = float(params.get("interval", 1.0) or 1.0)
            interval = max(0.5, min(interval, 5.0))
            _braille_monitor.start(player=player, speak=speak, interval=interval)
            return f"{result.message} Tradutor Braille ativo. So vou salvar no Obsidian quando confirmar 100%."
        except Exception as e:
            print(f"[LiveVision] ❌ Hand/Braille error: {e}")
            return f"Live vision camera Braille error: {e}"

    try:
        image_bytes, mime_type = _capture_frame(mode)
        if _VISION_LEARNING:
            remember_vision_event(mode, user_text, retained_media=False)
        label = "Camera frame" if mode == "camera" else "Screen captured"
        print(f"[LiveVision] {label}: {len(image_bytes):,} bytes")
    except Exception as e:
        print(f"[LiveVision] ❌ Capture error: {e}")
        return f"Live vision error: {e}"

    try:
        if mode == "camera" and record_requested:
            fps = float(params.get("fps", 8.0) or 8.0)
            _vision_processor.start(player=player, speak=speak, fps=fps)
            if player:
                player.write_log("SYS: Vision processing active. Raw video will not be kept.")

        _ensure_session(player=player, speak=speak)
        _session.analyze_frame(image_bytes, mime_type, user_text, mode)

        if continuous:
            interval = float(params.get("interval", 3.5) or 3.5)
            interval = max(1.5, min(interval, 12.0))
            _session.start_continuous(mode, user_text, interval=interval)
            if record_requested:
                return "Modo visão silencioso ativo. Processando a câmera sem salvar vídeo bruto e sem narração automática."
            return "Modo visão silencioso ativo. A análise vai para o log, sem narração automática."

        if record_requested:
            return "Camera capturada e processamento iniciado sem salvar video bruto."
        return "Tela capturada e analisada. O modo visão vai responder em português."

    except Exception as e:
        print(f"[LiveVision] ❌ Could not start session: {e}")
        return f"Erro no modo visão: {e}"

def stop_live_vision() -> str:
    """Stop the live vision session."""
    processing_was_active = _vision_processor.stop()
    _braille_monitor.stop()
    _session.stop()
    if processing_was_active:
        return "Modo visão parado. O processamento temporario da camera terminou; nenhum video bruto foi mantido."
    return "Modo visão parado."

def warmup_live_vision(player=None, speak=None) -> None:
    """Pre-start the vision session for faster first response."""
    try:
        _ensure_session(player=player, speak=speak)
        print("[LiveVision] ✅ Warmup complete")
    except Exception as e:
        print(f"[LiveVision] ⚠️ Warmup failed: {e}")

if __name__ == "__main__":
    print("[TEST] live_vision.py")
    print("=" * 52)
    mode = input("mode — screen / camera (default: screen): ").strip().lower() or "screen"
    q    = input("Question (Enter = default): ").strip() or "What do you see on screen? Be brief."

    t0 = time.perf_counter()
    warmup_live_vision()
    print(f"Session ready in {time.perf_counter()-t0:.2f}s\n")

    t1 = time.perf_counter()
    result = live_vision({"mode": mode, "text": q})
    print(f"Queued in {time.perf_counter()-t1:.3f}s — {result}")
    time.sleep(8)
    print("Done.")
