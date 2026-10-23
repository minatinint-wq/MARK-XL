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
from typing import Optional

from actions.cpu_acceleration import configure_cpu_acceleration, configure_opencv

configure_cpu_acceleration()
import numpy as np
import sounddevice as sd

try:
    import cv2
    configure_opencv(cv2)
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
    from actions.hand_braille import analyze_camera_braille, capture_camera_frame, wants_hand_braille
    _HAND_BRAILLE = True
except Exception as e:
    print(f"[Vision] ⚠️  Hand/Braille module unavailable: {e}")
    _HAND_BRAILLE = False

try:
    from actions.vision_learning import ensure_vision_preferences, remember_vision_event
    _VISION_LEARNING = True
except Exception as e:
    print(f"[Vision] ⚠️  Vision learning unavailable: {e}")
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


def _save_config_key(key: str, value) -> None:
    try:
        cfg = _load_config()
        cfg[key] = value
        _CONFIG_PATH.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
    except Exception as e:
        print(f"[Vision] ⚠️  Could not save config key '{key}': {e}")


def _get_api_key() -> str:
    key = _load_config().get("gemini_api_key", "")
    if not key:
        raise RuntimeError("gemini_api_key not found in config.")
    return key


def _get_os() -> str:
    return _load_config().get("os_system", "windows").lower()

_LIVE_MODEL         = "gemini-2.5-flash-native-audio-latest"
_CHANNELS           = 1
_RECEIVE_SAMPLE_RATE = 24_000
_CHUNK_SIZE         = 1_024
_VISION_SPEECH_PAUSE = 0.45

_IMG_MAX_W = 1600
_IMG_MAX_H = 900
_JPEG_Q    = 88
_VISION_SEND_RETRIES = 1
_RECENT_SCREENSHOT_SECONDS = 600
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "on", "enabled"}


def _vision_speech_enabled() -> bool:
    env_value = os.environ.get("MARK_XL_VISION_SPEECH")
    if env_value is not None:
        return _as_bool(env_value)
    return _as_bool(_load_config().get("vision_speech_enabled"), False)


_SYSTEM_PROMPT = (
    "Voce e JARVIS, um assistente avancado com visao. "
    "Responda SEMPRE em portugues brasileiro natural, mesmo se a tela ou o aplicativo estiverem em ingles. "
    "Nao chame o usuario de 'sir'. "
    "Analise a imagem com precisao. "
    "Se for Discord ou chamada/call, foque em participantes visiveis, nomes, cards de voz, lista lateral e quem parece estar falando. "
    "Nao responda apenas que o Discord esta aberto. "
    "Leia nomes somente quando estiverem legiveis; se nao conseguir ler, diga que precisa ampliar ou abrir a lista de participantes. "
    "Nunca invente nomes. "
    "Seja direto, mas traga detalhes quando a pergunta pedir."
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
        print(f"[Vision] ⚠️  Image compress failed: {e}")
        return img_bytes, f"image/{source_format.lower()}"


def _is_under(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved_root = root.resolve()
        return resolved == resolved_root or resolved.is_relative_to(resolved_root)
    except Exception:
        return False


def _resolve_image_path(value: str | None) -> Path | None:
    if not value:
        return None
    try:
        path = Path(str(value)).expanduser()
        if not path.is_absolute():
            path = (_BASE / path).resolve()
        if path.suffix.lower() not in _IMAGE_EXTS or not path.exists() or not path.is_file():
            return None
        allowed_roots = [_BASE, Path.home()]
        if not any(_is_under(path, root) for root in allowed_roots):
            return None
        return path
    except Exception:
        return None


def _find_recent_screenshot() -> Path | None:
    candidates: list[Path] = []
    search_roots = [_BASE, Path.home() / "Desktop"]
    for root in search_roots:
        if not root.exists():
            continue
        for pattern in ("*screenshot*.png", "*screenshot*.jpg", "*captura*.png", "*captura*.jpg"):
            candidates.extend(root.glob(pattern))

    now = time.time()
    valid: list[Path] = []
    for path in candidates:
        try:
            if path.suffix.lower() in _IMAGE_EXTS and now - path.stat().st_mtime <= _RECENT_SCREENSHOT_SECONDS:
                valid.append(path)
        except Exception:
            continue

    if not valid:
        return None
    return max(valid, key=lambda item: item.stat().st_mtime)


def _capture_image_file(path: Path) -> tuple[bytes, str]:
    data = path.read_bytes()
    source_format = path.suffix.lower().lstrip(".") or "png"
    return _compress(data, source_format.upper())


def _capture_screen() -> tuple[bytes, str]:

    if not _MSS:
        raise RuntimeError("mss is not installed. Run: pip install mss")

    with mss.mss() as sct:
        monitors = sct.monitors          # [0] = all combined, [1..n] = real screens
        target   = monitors[1] if len(monitors) > 1 else monitors[0]
        shot     = sct.grab(target)
        png      = mss.tools.to_png(shot.rgb, shot.size)

    return _compress(png, "PNG")


def _cv2_backend() -> int:
    """Return the best OpenCV camera backend for the current OS."""
    if not _CV2:
        return 0
    os_name = _get_os()
    if os_name == "windows":
        return cv2.CAP_DSHOW    
    if os_name == "mac":
        return cv2.CAP_AVFOUNDATION  
    return cv2.CAP_ANY


def _probe_camera(index: int, backend: int, warmup: int = 5) -> bool:

    if not _CV2:
        return False
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        cap.release()
        return False
    for _ in range(warmup):
        cap.read()
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return False
    return bool(np.mean(frame) > 8)


def _detect_camera_index() -> int:

    backend = _cv2_backend()
    print("[Vision] 🔍 Auto-detecting camera...")
    for idx in range(6):
        if _probe_camera(idx, backend):
            print(f"[Vision] ✅ Camera found at index {idx}")
            _save_config_key("camera_index", idx)
            return idx
        print(f"[Vision] ⚠️  Camera index {idx}: no usable frame")

    print("[Vision] ⚠️  No camera found — defaulting to index 0")
    _save_config_key("camera_index", 0)
    return 0


def _get_camera_index() -> int:
    cfg = _load_config()
    if "camera_index" in cfg:
        return int(cfg["camera_index"])
    return _detect_camera_index()


def _capture_camera() -> tuple[bytes, str]:
    if not _CV2:
        raise RuntimeError("OpenCV (cv2) is not installed. Run: pip install opencv-python")

    index   = _get_camera_index()
    backend = _cv2_backend()
    if _HAND_BRAILLE:
        frame = capture_camera_frame(camera_index=index, warmup=12, width=1280, height=720)
    else:
        cap = cv2.VideoCapture(index, backend)

        if not cap.isOpened():
            raise RuntimeError(f"Camera index {index} could not be opened.")

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        for _ in range(12):
            cap.read()

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            raise RuntimeError("Camera returned no frame.")

    if _PIL:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(rgb)
        img.thumbnail((_IMG_MAX_W, _IMG_MAX_H), PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_Q)
        return buf.getvalue(), "image/jpeg"

    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_Q])
    return buf.tobytes(), "image/jpeg"

class _VisionSession:
    def __init__(self):
        self._loop:       Optional[asyncio.AbstractEventLoop] = None
        self._thread:     Optional[threading.Thread]          = None
        self._session                                          = None
        self._out_queue:  Optional[asyncio.Queue]             = None
        self._audio_in:   Optional[asyncio.Queue]             = None
        self._ready_evt:  threading.Event                     = threading.Event()
        self._player                                           = None
        self._lock:       threading.Lock                       = threading.Lock()
        self._audio_generation: int                            = 0
        self._drop_audio_until: float                          = 0.0
        self._speech_enabled: bool                              = False

    def start(self, player=None, timeout: float = 25.0) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                if player is not None:
                    self._player = player
            else:
                self._ready_evt.clear()
                self._player = player
                self._thread = threading.Thread(
                    target=self._run_event_loop,
                    daemon=True,
                    name="VisionSessionThread",
                )
                self._thread.start()

        if not self._ready_evt.wait(timeout=timeout):
            raise RuntimeError(f"Vision session did not connect within {timeout}s.")
        print("[Vision] ✅ Session ready")

    def analyze(self, image_bytes: bytes, mime_type: str, user_text: str, mode: str = "screen") -> None:
        if not self._loop or not self._out_queue:
            print("[Vision] ⚠️  Session not started — dropping request")
            return
        asyncio.run_coroutine_threadsafe(
            self._out_queue.put((image_bytes, mime_type, user_text, mode, 0)),
            self._loop,
        )

    def is_ready(self) -> bool:
        return self._session is not None

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
        while True:
            try:
                print("[Vision] 🔌 Connecting...")
                async with client.aio.live.connect(
                    model=_LIVE_MODEL, config=config
                ) as session:
                    self._session = session
                    self._ready_evt.set()
                    backoff = 2.0  
                    print("[Vision] ✅ Connected")

                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._send_loop())
                        tg.create_task(self._recv_loop())
                        if self._speech_enabled:
                            tg.create_task(self._play_loop())

            except* Exception as eg:
                for exc in eg.exceptions:
                    print(f"[Vision] ⚠️  Session error: {exc}")
            finally:
                self._session = None
                self._ready_evt.clear()

            print(f"[Vision] 🔄 Reconnecting in {backoff:.0f}s...")
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
                print("[Vision] ⚠️  No session — dropping image")
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
                            log_prefix="[Vision]",
                        )
                    },
                    turn_complete=True,
                )
                print(f"[Vision] 📤 Sent {len(image_bytes):,} bytes — '{user_text[:60]}'")
            except Exception as e:
                print(f"[Vision] ⚠️  Send error: {e}")
                if retry < _VISION_SEND_RETRIES and self._out_queue:
                    try:
                        self._out_queue.put_nowait((image_bytes, mime_type, user_text, mode, retry + 1))
                        print("[Vision] 🔁 Requeued image after send failure; reconnecting session.")
                    except asyncio.QueueFull:
                        print("[Vision] ⚠️  Retry queue full — image dropped.")
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
                            print(f"[Vision] 💬 {full}")
                    transcript = []

        except Exception as e:
            print(f"[Vision] ⚠️  Recv error: {e}")
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

    async def _play_loop(self) -> None:
        if not self._speech_enabled or not self._audio_in:
            return
        try:
            stream = sd.RawOutputStream(
                samplerate=_RECEIVE_SAMPLE_RATE,
                channels=_CHANNELS,
                dtype="int16",
                blocksize=_CHUNK_SIZE,
            )
            stream.start()
        except Exception as e:
            print(f"[Vision] ⚠️  Audio not available: {e}")
            return

        try:
            while True:
                chunk = await self._audio_in.get()
                if isinstance(chunk, tuple) and len(chunk) == 2:
                    generation, chunk = chunk
                    if generation != self._audio_generation:
                        continue
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            print(f"[Vision] ❌ Play error: {e}")
            raise
        finally:
            stream.stop()
            stream.close()

_session      = _VisionSession()
_session_lock = threading.Lock()
_session_up   = False


def _ensure_session(player=None) -> None:
    global _session_up
    with _session_lock:
        if not _session.is_ready():
            _session_up = False
            _session.start(player=player)
            _session_up = True
        elif player is not None:
            _session._player = player


def screen_process(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
) -> bool:
    if _VISION_LEARNING:
        ensure_vision_preferences()

    params    = parameters or {}
    user_text = (params.get("text") or params.get("user_text") or "").strip()
    angle     = params.get("angle", "screen").lower().strip()
    # NVIDIA Camera Lab deterministic reroute
    request_key = user_text.casefold()
    requested_mode = str(params.get("provider") or params.get("camera_mode") or "").casefold()
    if (
        ("nvidia" in request_key and any(word in request_key for word in ("camera", "c\u00e2mera", "lab")))
        or requested_mode in {"nvidia", "nvidia_camera", "nvidia-camera"}
    ):
        from actions.nvidia_camera_lab import nvidia_camera_lab
        return nvidia_camera_lab({"action": "open"}, player=player)
    image_path = _resolve_image_path(params.get("path") or params.get("image_path") or params.get("screenshot_path"))

    if not user_text:
        print("[Vision] ⚠️  No question provided — aborting")
        return False

    print(f"[Vision] ▶ angle={angle!r}  question='{user_text[:80]}'")
    if not image_path and angle == "screen" and any(term in user_text.lower() for term in ("screenshot", "captura", "print")):
        image_path = _find_recent_screenshot()

    if angle == "camera" and _HAND_BRAILLE and wants_hand_braille(user_text):
        try:
            result = analyze_camera_braille()
            if player and hasattr(player, "update_braille_translation"):
                player.update_braille_translation(result)
            if player:
                player.write_log(f"Jarvis: {result.message}")
            return result.message
        except Exception as e:
            print(f"[Vision] ❌ Hand/Braille error: {e}")
            return f"Camera Braille error: {e}"

    try:
        analysis_mode = angle
        if image_path:
            image_bytes, mime_type = _capture_image_file(image_path)
            analysis_mode = "image"
            print(f"[Vision] 🖼️  Screenshot file: {image_path} ({len(image_bytes):,} bytes)")
        elif angle == "camera":
            image_bytes, mime_type = _capture_camera()
            print(f"[Vision] 📷 Camera: {len(image_bytes):,} bytes")
        else:
            image_bytes, mime_type = _capture_screen()
            print(f"[Vision] 🖥️  Screen: {len(image_bytes):,} bytes")
        if _VISION_LEARNING:
            remember_vision_event(angle, user_text, retained_media=False)
    except Exception as e:
        print(f"[Vision] ❌ Capture error: {e}")
        return False

    try:
        _ensure_session(player=player)
    except Exception as e:
        print(f"[Vision] ❌ Could not start session: {e}")
        return False

    _session.analyze(image_bytes, mime_type, user_text, analysis_mode)
    return "Modo visão silencioso ativado. A análise vai para o log, sem narração automática."


def warmup_session(player=None) -> None:
    try:
        _ensure_session(player=player)
    except Exception as e:
        print(f"[Vision] ⚠️  Warmup failed: {e}")

if __name__ == "__main__":
    print("[TEST] screen_processor.py")
    print("=" * 52)
    mode = input("angle — screen / camera (default: screen): ").strip().lower() or "screen"
    q    = input("Question (Enter = default): ").strip() or "What do you see? Be brief."

    t0 = time.perf_counter()
    warmup_session()
    print(f"Session ready in {time.perf_counter()-t0:.2f}s\n")

    t1 = time.perf_counter()
    ok = screen_process({"angle": mode, "text": q})
    print(f"Queued in {time.perf_counter()-t1:.3f}s — waiting for audio...")
    time.sleep(10)
    print("Done." if ok else "Failed.")
