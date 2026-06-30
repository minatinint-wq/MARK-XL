import asyncio
import os
import re
import threading
import time
import json
import sys
import io
import math
import traceback
import unicodedata
from array import array
from pathlib import Path

_qt_rules = os.environ.get("QT_LOGGING_RULES", "")
if "qt.qpa.window" not in _qt_rules:
    os.environ["QT_LOGGING_RULES"] = (_qt_rules + ";qt.qpa.window=false").strip(";")

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

# ============================================
# AUTO-INIT NEURAL DATA
# ============================================
def _init_neural_data():
    """Initialize all neural data on first run."""
    import importlib.util

    scripts = [
        (r"D:\xxxx_memory\brains\neural_data_initializer.py", "Dados neurais"),
        (r"D:\xxxx_memory\brains\neural_bio_data.py", "Bio/Cannabis"),
        (r"D:\xxxx_memory\brains\neural_specialized_data.py", "Especializado"),
        (r"D:\xxxx_memory\brains\dictionary_brain.py", "Dicionario"),
    ]

    for path, desc in scripts:
        try:
            script_path = Path(path)
            if script_path.exists():
                spec = importlib.util.spec_from_file_location(f"neural_{desc}", script_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"neural_{desc}"] = module
                spec.loader.exec_module(module)
                print(f"[Neural] {desc} carregado!")
        except Exception as e:
            print(f"[Neural] {desc}: {e}")

import sounddevice as sd
from google import genai
from google.genai import types

try:
    import numpy as np
except Exception:
    np = None

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass
from ui import JarvisUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
)

# ============================================
# XXXX LEARNING SYSTEM INTEGRATION
# Sistema de aprendizado avançado salvo em D:\xxxx_memory
# Superior ao Siri e Google Assistant
# ============================================
LEARNING_SYSTEM_PATH = Path(r"D:\xxxx_memory")
ADVANCED_LEARNER_PATH = Path(r"D:\xxxx_memory\brains\xxxx_advanced_learner.py")
NEURAL_MAP_PATH = Path(r"D:\xxxx_memory\brains\xxxx_neural_map.py")

_learning_available = False
_learning_module = None
_neural_map_available = False
_neural_map_module = None
_phone_module = None  # Persistir conexão Bluetooth entre chamadas
_neural_load_lock = threading.Lock()
_neural_load_started = False


def _load_module_from_path(module_name: str, path: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(module_name, path)
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_neural_modules():
    """Load vault/learning modules outside the startup critical path."""
    global _learning_available, _learning_module, _neural_map_available, _neural_map_module

    try:
        cerebro_path = Path(r"D:\xxxx_memory\brains\cerebro_central.py")
        if cerebro_path.exists():
            _load_module_from_path("cerebro_central", cerebro_path)
            print("[Neural] Cerebro Central carregado!")
    except Exception as e:
        print(f"[Neural] Cerebro Central: {e}")

    _init_neural_data()

    if ADVANCED_LEARNER_PATH.exists():
        try:
            _learning_module = _load_module_from_path("xxxx_advanced_learner", ADVANCED_LEARNER_PATH)
            _learning_available = True
            print("[Learn] Sistema AVANÇADO de aprendizado carregado!")
            print(f"[Learn] Local: D:\\xxxx_memory")
            print(f"[Learn] Modo: SUPERIOR ao Siri/Google Assistant")
        except Exception as e:
            print(f"[Learn] Erro ao carregar sistema avançado: {e}")

    if NEURAL_MAP_PATH.exists():
        try:
            _neural_map_module = _load_module_from_path("xxxx_neural_map", NEURAL_MAP_PATH)
            _neural_map_available = True
            print("[Neural] NOTEBOOK Integração Obsidian/Neural Map carregada!")
            print(f"[Neural] Vault: D:\\xxxx_memory")
        except Exception as e:
            print(f"[Neural] Erro ao carregar neural map: {e}")


def _start_neural_background_load(delay: float = 8.0):
    global _neural_load_started
    with _neural_load_lock:
        if _neural_load_started:
            return
        _neural_load_started = True

    def worker():
        if delay > 0:
            time.sleep(delay)
        _load_neural_modules()

    threading.Thread(target=worker, daemon=True, name="NeuralLazyLoader").start()

def _auto_learn_from_message(message: str):
    """Função interna para auto-aprendizado após cada mensagem."""
    if not _learning_available:
        _start_neural_background_load(delay=0)
        return
    try:
        result = _learning_module.learn_everything(message)
        if result.get('learned', 0) > 0:
            print(f"[Learn] USER Aprendido: {result['learned']} info(s) - Total: {result['total_memories']}")
            # Sincronizar com Obsidian
            if _neural_map_available:
                try:
                    _neural_map_module.auto_sync_on_learn()
                except Exception:
                    pass
    except Exception as e:
        print(f"[Learn] Erro no auto-aprendizado: {e}")

from actions.file_processor import file_processor
from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor  import screen_process
from actions.youtube_video     import youtube_video
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller as file_controller_action
from actions.obsidian_controller import obsidian_control
from actions.live_vision       import live_vision
from actions.smart_api_manager import get_api_manager, handle_api_error
from actions.code_helper       import code_helper
from actions.dev_agent         import dev_agent
from actions.web_search        import web_search as web_search_action
from actions.image_search      import image_search as image_search_action
from actions.maps_mode         import maps_mode as maps_mode_action
from actions.wallpaper_engine  import wallpaper_engine as wallpaper_engine_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater
from actions.game_control      import game_control
from actions.steam_store       import steam_store as steam_store_action
from actions.game_vision       import game_vision as game_vision_action
from actions.quick_commands    import quick_command
from actions.automation        import automation as automation_action
from actions.spotify_control   import spotify_control
from actions.smart_home        import smart_home
from actions.study_mode        import study_mode as study_mode_action
from actions.brain_mode        import brain_mode as brain_mode_action
from actions.local_llm         import local_llm as local_llm_action
from actions.camera_hand_ui    import camera_hand_ui
from actions.sound_learning    import sound_learning as sound_learning_action, ingest_sound_audio
from actions.jarvis_lab        import jarvis_lab as jarvis_lab_action
from actions.iphone_bridge     import iphone_bridge as iphone_bridge_action
from actions.social_control    import social_control as social_control_action
from actions.iphone_shortcuts  import iphone_shortcuts as iphone_shortcuts_action
from actions.operation_memory  import operation_memory as operation_memory_action
from actions.startup_animation import run_startup_animation, enable_clap_detection

def normalize_path(path):
    if path and len(path) == 2 and path[1] == ":":
        path += "\\"
    return path

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent



BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LIVE_MODEL = "gemini-2.5-flash-native-audio-latest"  # Native audio model
TEXT_MODEL = "gemini-2.0-flash-001"  # Text-only fallback model
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024
VOICE_NAME          = "Charon"
VOICE_BAND_EDGES_HZ = (60, 90, 130, 180, 250, 350, 500, 700, 1000, 1400, 2000, 2800, 4000, 5600, 8000)
VOICE_BANDS_HZ      = tuple(int((low + high) / 2) for low, high in zip(VOICE_BAND_EDGES_HZ, VOICE_BAND_EDGES_HZ[1:]))
VOICE_METRIC_INTERVAL = 0.05
SPEECH_TAIL_SECONDS = 1.35
WAKE_WORDS          = ("jarvis", "javis", "jarves", "jervis")
TEMP_MUTE_COMMANDS  = (
    "muta",
    "mute",
    "silencio",
    "silenciar",
    "fica quieto",
    "fica mudo",
    "modo silencio",
    "modo silencioso",
    "para de falar",
)

def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are JARVIS, Tony Stark's AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )

_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

def _clean_transcript(text: str) -> str:    
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()


def _live_inline_data_chunks(response) -> list[bytes]:
    """Extract audio chunks without touching response.data, which logs SDK warnings."""
    try:
        server_content = getattr(response, "server_content", None)
        model_turn = getattr(server_content, "model_turn", None)
        parts = getattr(model_turn, "parts", None) or []
    except Exception:
        return []

    chunks: list[bytes] = []
    for part in parts:
        inline_data = getattr(part, "inline_data", None)
        data = getattr(inline_data, "data", None)
        if isinstance(data, bytes) and data:
            chunks.append(data)
    return chunks


def _normalize_spoken_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _has_wake_word(text: str) -> bool:
    normalized = _normalize_spoken_text(text)
    return any(word in normalized for word in WAKE_WORDS)


def _is_temp_mute_command(text: str) -> bool:
    normalized = _normalize_spoken_text(text)
    if normalized in TEMP_MUTE_COMMANDS:
        return True
    return any(cmd in normalized for cmd in TEMP_MUTE_COMMANDS)


def _strip_wake_word(text: str) -> str:
    cleaned = _normalize_spoken_text(text)
    for word in WAKE_WORDS:
        cleaned = re.sub(rf"\b{re.escape(word)}\b", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _pcm16_floats(data: bytes, limit: int = 1024) -> list[float]:
    usable = len(data) - (len(data) % 2)
    if usable <= 0:
        return []

    samples = array("h")
    samples.frombytes(data[:usable])
    if sys.byteorder != "little":
        samples.byteswap()

    if len(samples) > limit:
        samples = samples[-limit:]

    return [max(-1.0, min(1.0, sample / 32768.0)) for sample in samples]


def _goertzel_power(samples: list[float], sample_rate: int, freq: int) -> float:
    n = len(samples)
    if n < 8 or sample_rate <= 0:
        return 0.0

    k = int(0.5 + (n * freq / sample_rate))
    if k <= 0:
        return 0.0

    omega = (2.0 * math.pi * k) / n
    coeff = 2.0 * math.cos(omega)
    q0 = q1 = q2 = 0.0
    for sample in samples:
        q0 = coeff * q1 - q2 + sample
        q2 = q1
        q1 = q0

    power = q1 * q1 + q2 * q2 - q1 * q2 * coeff
    return math.sqrt(max(0.0, power)) / n


def _waveform_points(samples: list[float], count: int = 64) -> list[float]:
    if not samples or count <= 0:
        return []

    if len(samples) <= count:
        points = [max(-1.0, min(1.0, float(sample))) for sample in samples]
        points.extend([0.0] * (count - len(points)))
        return points

    bucket = len(samples) / count
    points: list[float] = []
    for idx in range(count):
        start = int(idx * bucket)
        end = max(start + 1, int((idx + 1) * bucket))
        segment = samples[start:end]
        if not segment:
            points.append(0.0)
            continue
        points.append(max(segment, key=lambda value: abs(value)))

    return [round(max(-1.0, min(1.0, value)), 4) for value in points]


def _compress_bands(raw_bands: list[float]) -> list[float]:
    if not raw_bands:
        return []

    peak = max(raw_bands)
    if peak <= 1e-10:
        return [0.0 for _ in raw_bands]

    scale = math.log1p(9.0)
    return [
        round(_clamp01(math.log1p((max(0.0, value) / peak) * 9.0) / scale), 4)
        for value in raw_bands
    ]


def _fft_voice_metrics(samples: list[float], sample_rate: int) -> tuple[list[float], float, float, float]:
    if np is None or sample_rate <= 0 or len(samples) < 32:
        return [], 0.0, 0.0, 0.0

    arr = np.asarray(samples, dtype=np.float32)
    arr = arr - float(arr.mean())
    window = np.hanning(arr.size).astype(np.float32)
    spectrum = np.abs(np.fft.rfft(arr * window))
    freqs = np.fft.rfftfreq(arr.size, d=1.0 / sample_rate)
    if spectrum.size:
        spectrum[0] = 0.0

    max_freq = min(8000.0, sample_rate / 2.0)
    voice_mask = (freqs >= 60.0) & (freqs <= max_freq)
    if not np.any(voice_mask):
        return [], 0.0, 0.0, 0.0

    voice_freqs = freqs[voice_mask]
    voice_mags = spectrum[voice_mask]
    floor = float(np.percentile(voice_mags, 25)) if voice_mags.size else 0.0
    clean = np.maximum(voice_mags - floor, 0.0)
    if clean.size and float(clean.max()) <= 1e-9:
        clean = voice_mags

    total = float(clean.sum())
    dominant = 0.0
    centroid = 0.0
    clarity = 0.0
    if total > 1e-9:
        dominant = float(voice_freqs[int(np.argmax(clean))])
        centroid = float((voice_freqs * clean).sum() / total)
        clarity = _clamp01(float(clean.max()) / total * 18.0)

    raw_bands: list[float] = []
    for low, high in zip(VOICE_BAND_EDGES_HZ, VOICE_BAND_EDGES_HZ[1:]):
        high = min(float(high), max_freq)
        if high <= low:
            raw_bands.append(0.0)
            continue
        band_mask = (freqs >= float(low)) & (freqs < high)
        if not np.any(band_mask):
            raw_bands.append(0.0)
            continue
        values = spectrum[band_mask]
        raw_bands.append(float(np.sqrt(np.mean(values * values))))

    return _compress_bands(raw_bands), dominant, centroid, clarity


def _pcm_voice_metrics(data: bytes, sample_rate: int) -> dict:
    samples = _pcm16_floats(data, limit=2048)
    if not samples:
        return {}

    n = len(samples)
    rms = math.sqrt(sum(sample * sample for sample in samples) / n)
    peak = max(abs(sample) for sample in samples)
    level = _clamp01((rms * 7.0) + (peak * 0.25))
    waveform = _waveform_points(samples)

    crossings = 0
    for prev, cur in zip(samples, samples[1:]):
        if (prev >= 0.0 > cur) or (prev < 0.0 <= cur):
            crossings += 1
    zcr_hz = 0.0
    if n > 1 and sample_rate > 0:
        zcr_hz = crossings * sample_rate / (2.0 * (n - 1))

    bands, dominant, centroid, clarity = _fft_voice_metrics(samples, sample_rate)
    if not bands:
        raw_bands = [_goertzel_power(samples, sample_rate, freq) for freq in VOICE_BANDS_HZ]
        bands = _compress_bands(raw_bands)
        max_band = max(raw_bands) if raw_bands else 0.0
        if max_band > 0:
            energy = sum(raw_bands)
            centroid = sum(freq * value for freq, value in zip(VOICE_BANDS_HZ, raw_bands)) / max(energy, 1e-9)
            dominant = VOICE_BANDS_HZ[raw_bands.index(max_band)]
            clarity = _clamp01(max_band / max(energy, 1e-9) * 8.0)
        else:
            centroid = zcr_hz
            dominant = zcr_hz
    else:
        bands = [float(value) for value in bands]

    if peak < 0.0025 and rms < 0.0006:
        dominant = 0.0
        centroid = 0.0
        bands = [0.0 for _ in VOICE_BANDS_HZ]
        waveform = [0.0 for _ in waveform]
        clarity = 0.0

    return {
        "level": round(level, 4),
        "rms": round(rms, 5),
        "peak": round(peak, 4),
        "dominant_hz": round(float(dominant), 1),
        "centroid_hz": round(float(centroid), 1),
        "zcr_hz": round(float(zcr_hz), 1),
        "bands": [round(value, 4) for value in bands],
        "waveform": waveform,
        "clarity": round(float(clarity), 4),
        "analyzer": "fft" if np is not None else "goertzel",
        "sample_rate": sample_rate,
    }


def _voice_coupling(user_metrics: dict | None, ai_metrics: dict | None) -> float:
    if not user_metrics or not ai_metrics:
        return 0.0

    user_level = float(user_metrics.get("level") or 0.0)
    ai_level = float(ai_metrics.get("level") or 0.0)
    if user_level < 0.01 and ai_level < 0.01:
        return 0.0

    user_centroid = float(user_metrics.get("centroid_hz") or 0.0)
    ai_centroid = float(ai_metrics.get("centroid_hz") or 0.0)
    freq_link = 1.0 - min(1.0, abs(user_centroid - ai_centroid) / 4200.0)

    user_bands = user_metrics.get("bands") or []
    ai_bands = ai_metrics.get("bands") or []
    band_pairs = list(zip(user_bands, ai_bands))
    if band_pairs:
        band_link = 1.0 - min(1.0, sum(abs(float(a) - float(b)) for a, b in band_pairs) / len(band_pairs))
    else:
        band_link = 0.0

    level_link = 1.0 - min(1.0, abs(user_level - ai_level))
    active = _clamp01((user_level + ai_level) * 0.75)
    return round(_clamp01((freq_link * 0.45 + band_link * 0.35 + level_link * 0.2) * active), 4)

TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens any application on the computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query"},
                "mode":   {"type": "STRING", "description": "search (default) or compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "price | specs | reviews"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "maps_mode",
        "description": (
            "Maps, address and route assistant. Use for endereco, rua, CEP, buscar lugar, abrir Google Maps, rotas, navegacao, "
            "and questions like 'quantos minutos de X ate Y'. Returns estimated time/distance without real-time traffic and Google Maps links."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "search/endereco | cep | open/abrir | tempo/minutos | rota/route | navegar | reverse | set_default | status"},
                "query": {"type": "STRING", "description": "Address/place/search query or destination"},
                "address": {"type": "STRING", "description": "Address text"},
                "endereco": {"type": "STRING", "description": "Endereco em portugues"},
                "cep": {"type": "STRING", "description": "Brazilian CEP, with or without dash"},
                "origin": {"type": "STRING", "description": "Route origin / origem"},
                "origem": {"type": "STRING", "description": "Origem da rota"},
                "destination": {"type": "STRING", "description": "Route destination / destino"},
                "destino": {"type": "STRING", "description": "Destino da rota"},
                "city": {"type": "STRING", "description": "City/cidade context"},
                "state": {"type": "STRING", "description": "State/UF context"},
                "country": {"type": "STRING", "description": "Country context, default Brasil"},
                "mode": {"type": "STRING", "description": "driving | walking | bicycling | transit"},
                "open": {"type": "BOOLEAN", "description": "Open Google Maps after preparing result"},
                "lat": {"type": "STRING", "description": "Latitude for reverse geocode"},
                "lon": {"type": "STRING", "description": "Longitude for reverse geocode"},
                "limit": {"type": "INTEGER", "description": "Max address results"}
            },
            "required": []
        }
    },    {
        "name": "image_search",
        "description": (
            "Searches images or stock videos through configured provider APIs (Pexels, Pixabay, Unsplash) and can download/save them. "
            "Use for buscar/procurar/baixar/salvar imagem, video, wallpaper, referencia visual, logo, foto, b-roll, clips, or visual assets. "
            "Use media_type='video' for videos. Use action='set_api_key' to save provider API keys and action='set_folder' to save default folders."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "search | download/save | set_folder | set_video_folder | set_api_key | status/providers | list | save_url"},
                "media_type": {"type": "STRING", "description": "image (default) | video"},
                "provider": {"type": "STRING", "description": "pexels | pixabay | unsplash | bing | ddg. Unsplash supports images only"},
                "query": {"type": "STRING", "description": "Image or video search query"},
                "url": {"type": "STRING", "description": "Direct image/video URL for save_url"},
                "folder": {"type": "STRING", "description": "Optional folder. If omitted, uses saved image/video default folder"},
                "filename": {"type": "STRING", "description": "Optional filename stem for saved media"},
                "count": {"type": "INTEGER", "description": "Number of media items to return or save"},
                "save": {"type": "BOOLEAN", "description": "When true, download search results to the default folder"},
                "safe_search": {"type": "STRING", "description": "on | moderate | off"},
                "region": {"type": "STRING", "description": "Search region, default br-pt"},
                "orientation": {"type": "STRING", "description": "landscape | portrait | square/squarish"},
                "size": {"type": "STRING", "description": "Provider size filter: large | medium | small"},
                "quality": {"type": "STRING", "description": "Download/search quality: original | large | large2x | medium | small"},
                "color": {"type": "STRING", "description": "Optional image color filter"},
                "image_type": {"type": "STRING", "description": "photo | clipart | gif | transparent | line"},
                "license": {"type": "STRING", "description": "Optional image license filter"},
                "api_key": {"type": "STRING", "description": "API key when action=set_api_key"},
                "max_file_mb": {"type": "INTEGER", "description": "Maximum media file size in MB. Images default 15; videos default 120"}
            },
            "required": []
        }
    },
    {
        "name": "wallpaper_engine",
        "description": (
            "Controls Wallpaper Engine through its command-line interface. Use for opening Wallpaper Engine, pausing/resuming/stopping/muting wallpapers, "
            "changing to the next wallpaper, applying a wallpaper file/project/video, opening playlists/profiles, getting the current wallpaper, "
            "applying properties, and hiding/showing desktop icons."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "status | set_path | start/open | pause | play/resume | stop | mute | unmute | next | open_wallpaper | close | get | apply_properties | open_playlist | open_profile | hide_icons | show_icons | save_wallpaper"},
                "path": {"type": "STRING", "description": "Path to wallpaper64.exe for set_path, or wallpaper project/file for open_wallpaper/save_wallpaper"},
                "file": {"type": "STRING", "description": "Wallpaper file path: project.json, scene.pkg, mp4, html, image"},
                "name": {"type": "STRING", "description": "Alias, playlist, profile, or saved wallpaper name"},
                "monitor": {"type": "INTEGER", "description": "Monitor index starting at 0"},
                "location": {"type": "STRING", "description": "Wallpaper Engine monitor/window location identifier"},
                "playlist": {"type": "STRING", "description": "Saved Wallpaper Engine playlist name"},
                "profile": {"type": "STRING", "description": "Saved Wallpaper Engine display profile name"},
                "properties": {"type": "OBJECT", "description": "Wallpaper properties JSON for apply_properties"},
                "play_in_window": {"type": "STRING", "description": "Open wallpaper in a named pop-out window"},
                "width": {"type": "INTEGER", "description": "Pop-out window width"},
                "height": {"type": "INTEGER", "description": "Pop-out window height"},
                "activate": {"type": "BOOLEAN", "description": "Bring pop-out window to foreground"},
                "borderless": {"type": "BOOLEAN", "description": "Open pop-out window borderless"}
            },
            "required": []
        }
    },
    {
        "name": "weather_report",
        "description": (
            "Weather forecast without API key. Use for previsao do tempo, clima agora, vai chover, temperatura, vento, "
            "forecast by city/address/CEP/coordinates, today/tomorrow and next days."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "forecast | current/agora | today/hoje | tomorrow/amanha | rain/chuva | open/abrir"},
                "city": {"type": "STRING", "description": "City name, e.g. Sao Paulo"},
                "cidade": {"type": "STRING", "description": "Cidade em portugues"},
                "location": {"type": "STRING", "description": "City, neighborhood, address or place"},
                "query": {"type": "STRING", "description": "Natural weather query/location"},
                "cep": {"type": "STRING", "description": "Brazilian CEP"},
                "lat": {"type": "STRING", "description": "Latitude"},
                "lon": {"type": "STRING", "description": "Longitude"},
                "days": {"type": "INTEGER", "description": "Forecast days, 1 to 7"},
                "when": {"type": "STRING", "description": "today | tomorrow | date-ish text"},
                "open": {"type": "BOOLEAN", "description": "Open Google weather as fallback/confirmation"}
            },
            "required": []
        }
    },    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "social_control",
        "description": (
            "Controls WhatsApp and Instagram through official web/app surfaces. "
            "Use for opening WhatsApp Web, Instagram Direct, chats, profiles, posts, conversations, "
            "and sending a single user-requested message. Do not use for spam, scraping, or bypassing login."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "open | open_chat | send_message | open_profile | open_post | view_posts | view_conversations | direct | search | copy_message | status"},
                "platform": {"type": "STRING", "description": "whatsapp | instagram"},
                "receiver": {"type": "STRING", "description": "Contact name, phone number, or Instagram user"},
                "message": {"type": "STRING", "description": "Message text for send/copy"},
                "message_text": {"type": "STRING", "description": "Alternative message text"},
                "username": {"type": "STRING", "description": "Instagram username/profile"},
                "post": {"type": "STRING", "description": "Instagram post URL or shortcode"},
                "url": {"type": "STRING", "description": "Direct post/profile URL"},
                "query": {"type": "STRING", "description": "Search query"},
                "send": {"type": "BOOLEAN", "description": "When true, send/press Enter if the web app is ready"},
                "silent": {"type": "BOOLEAN", "description": "When true, do not speak a follow-up"}
            },
            "required": []
        }
    },
    {
        "name": "iphone_bridge",
        "description": (
            "Controls what is possible with an iPhone from Windows through Bluetooth, Phone Link and system URI handlers. "
            "Use for conectar iPhone, abrir Phone Link, abrir Bluetooth, status do iPhone, chamadas, SMS preparation, "
            "media keys, volume, and opening the local iPhone/social config HTML."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "status | config | setup/connect/pair | open/phone_link | bluetooth_settings | open_app/open_game | call | sms | copy_to_phone | play_pause | next | previous | volume_up | volume_down | mute | set_name | help"},
                "target": {"type": "STRING", "description": "Preferred iPhone/device name"},
                "name": {"type": "STRING", "description": "Alternative iPhone/device name"},
                "app_name": {"type": "STRING", "description": "App/game name for open_app/open_game, e.g. Clash Royale"},
                "app": {"type": "STRING", "description": "Alternative app/game name"},
                "game": {"type": "STRING", "description": "Alternative game name"},
                "number": {"type": "STRING", "description": "Phone number for tel/sms"},
                "phone": {"type": "STRING", "description": "Alternative phone number"},
                "message": {"type": "STRING", "description": "Text to copy or prepare for SMS"},
                "text": {"type": "STRING", "description": "Alternative text"},
                "silent": {"type": "BOOLEAN", "description": "When true, do not speak a follow-up"}
            },
            "required": []
        }
    },
    {
        "name": "iphone_shortcuts",
        "description": (
            "Runs a local HTTP bridge for iPhone Shortcuts to send silent events to Jarvis. "
            "Use for Atalhos do iPhone, enviar bateria/localizacao/clipboard/foto/audio/foco/emergencia para Jarvis, "
            "starting/stopping the bridge, getting URL/token/templates, and reading received events."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "start | stop | restart | status | url | templates | events | latest | clear | test | config"},
                "port": {"type": "INTEGER", "description": "Local bridge port, default 8765"},
                "limit": {"type": "INTEGER", "description": "Number of events to list"},
                "type": {"type": "STRING", "description": "Event type for test/record"},
                "message": {"type": "STRING", "description": "Test event message"},
                "silent": {"type": "BOOLEAN", "description": "When true, do not speak a follow-up"}
            },
            "required": []
        }
    },
    {
        "name": "operation_memory",
        "description": (
            "Shows or updates silent operational learning for iPhone/social/automation usage: frequent contacts, event types, "
            "recent operations and preferences. Use when the user asks what Jarvis learned operationally."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "status | list | clear | set_preference | record"},
                "limit": {"type": "INTEGER", "description": "Result limit"},
                "key": {"type": "STRING", "description": "Preference key"},
                "value": {"type": "STRING", "description": "Preference value"},
                "source": {"type": "STRING", "description": "Operation source"},
                "operation": {"type": "STRING", "description": "Operation name"},
                "metadata": {"type": "OBJECT", "description": "Optional operation metadata"},
                "silent": {"type": "BOOLEAN", "description": "When true, do not speak a follow-up"}
            },
            "required": []
        }
    },
    {
        "name": "reminder",
        "description": "Sets PC reminders and alarms using the OS scheduler. Use for alarmes no PC, timers, reminders, listar/cancelar alarmes.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":  {"type": "STRING", "description": "set | set_alarm | alarm | list | cancel"},
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "hours":   {"type": "NUMBER", "description": "Relative hours from now"},
                "minutes": {"type": "NUMBER", "description": "Relative minutes from now"},
                "seconds": {"type": "NUMBER", "description": "Relative seconds from now"},
                "message": {"type": "STRING", "description": "Reminder/alarm message text"},
                "label":   {"type": "STRING", "description": "Optional alarm label/name"},
                "id":      {"type": "STRING", "description": "Alarm/reminder id for cancel"},
                "duration_seconds": {"type": "INTEGER", "description": "Alarm sound duration, default 60 for alarms"},
                "dry_run": {"type": "BOOLEAN", "description": "Preview without scheduling"}
            },
            "required": []
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image silently. "
            "Use when user asks what is on screen, what you see, analyze screen, look at camera. "
            "For the Braille/Braile translator, use angle='camera' only when the user explicitly says braille/braile. "
            "Do not narrate automatically; keep vision output silent/logged unless the user explicitly asks for spoken narration. "
            "You have NO visual ability without this tool."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"},
                "path":  {"type": "STRING", "description": "Optional path to an already-saved screenshot/image to analyze instead of recapturing the active screen"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use for ANY single computer control command. NEVER route to agent_task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Controls any web browser. Use for: opening websites, searching the web, "
            "clicking elements, filling forms, scrolling, screenshots, navigation, any web-based task. "
            "Always pass the 'browser' parameter when the user specifies a browser (e.g. 'open in Edge', "
            "'use Firefox', 'open Chrome'). Multiple browsers can run simultaneously."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | get_url | press | new_tab | close_tab | screenshot | back | forward | reload | switch | list_browsers | close | close_all"},
                "browser":     {"type": "STRING", "description": "Target browser: chrome | edge | firefox | opera | operagx | brave | vivaldi | safari. Omit to use the currently active browser."},
                "url":         {"type": "STRING", "description": "URL for go_to / new_tab action"},
                "query":       {"type": "STRING", "description": "Search query for search action"},
                "engine":      {"type": "STRING", "description": "Search engine: google | bing | duckduckgo | yandex (default: google)"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type"},
                "text":        {"type": "STRING", "description": "Text to click or type"},
                "description": {"type": "STRING", "description": "Element description for smart_click/smart_type"},
                "direction":   {"type": "STRING", "description": "up | down for scroll"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount in pixels (default: 500)"},
                "key":         {"type": "STRING", "description": "Key name for press action (e.g. Enter, Escape, F5)"},
                "path":        {"type": "STRING", "description": "Save path for screenshot"},
                "incognito":   {"type": "BOOLEAN", "description": "Open in private/incognito mode"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders: list, create, delete, move, copy, rename, read, write, find, disk usage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home"},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "obsidian_control",
        "description": (
            "Controls the Obsidian knowledge vault/brain. Use for vault notes, categories, tags, "
            "frontmatter, learned knowledge, moving notes between categories, opening notes in Obsidian, "
            "daily notes, backlinks, and searching/reading the vault. Prefer this over file_controller "
            "for any Obsidian, vault, note, knowledge-base, category, or brain-memory file operation."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "status | categories | list | search | read | create | append | replace | frontmatter | tag | remove_tag | move | rename | archive | backlinks | open | daily | organize"
                },
                "query": {"type": "STRING", "description": "Search query or note title/content to locate"},
                "category": {"type": "STRING", "description": "Vault category/folder, e.g. imoveis, games, tech, braille"},
                "destination": {"type": "STRING", "description": "Destination category for move/archive-style operations"},
                "target_category": {"type": "STRING", "description": "Alternative destination category for moving notes"},
                "path": {"type": "STRING", "description": "Exact note path if known"},
                "name": {"type": "STRING", "description": "Note file name"},
                "title": {"type": "STRING", "description": "Human-readable note title"},
                "new_name": {"type": "STRING", "description": "New file name for rename"},
                "content": {"type": "STRING", "description": "Content to create, append, or replace"},
                "heading": {"type": "STRING", "description": "Heading to use when appending content"},
                "tags": {"type": "STRING", "description": "Comma-separated tags or inline tag list"},
                "tag": {"type": "STRING", "description": "Single tag to add/remove"},
                "type": {"type": "STRING", "description": "Frontmatter type value"},
                "folder": {"type": "STRING", "description": "Frontmatter folder value"},
                "status": {"type": "STRING", "description": "Frontmatter status value"},
                "summary": {"type": "STRING", "description": "Frontmatter summary value"},
                "limit": {"type": "INTEGER", "description": "Maximum results for list/search"},
                "max_chars": {"type": "INTEGER", "description": "Maximum characters for read"},
                "date": {"type": "STRING", "description": "Date for daily note"},
                "dry_run": {"type": "BOOLEAN", "description": "Preview organize without moving files"},
                "overwrite": {"type": "BOOLEAN", "description": "Allow create/replace to overwrite when explicitly requested"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, clean, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, or builds code files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto (default: auto)"},
                "description": {"type": "STRING", "description": "What the code should do or what change to make"},
                "language":    {"type": "STRING", "description": "Programming language (default: python)"},
                "output_path": {"type": "STRING", "description": "Where to save the file"},
                "file_path":   {"type": "STRING", "description": "Path to existing file for edit/explain/run/build"},
                "code":        {"type": "STRING", "description": "Raw code string for explain"},
                "args":        {"type": "STRING", "description": "CLI arguments for run/build"},
                "timeout":     {"type": "INTEGER", "description": "Execution timeout in seconds (default: 30)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects from scratch: plans, writes files, installs deps, opens VSCode, runs and fixes errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "What the project should do"},
                "language":     {"type": "STRING", "description": "Programming language (default: python)"},
                "project_name": {"type": "STRING", "description": "Optional project folder name"},
                "timeout":      {"type": "INTEGER", "description": "Run timeout in seconds (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING", "description": "Complete description of what to accomplish"},
                "priority": {"type": "STRING", "description": "low | normal | high (default: normal)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, clipboard, scroll, mouse, screenshots, screen element finding, and window management.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | type_for_me | click | double_click | right_click | hotkey | press | key_down | key_up | hold | scroll | move | mouse_relative | position | read_clipboard | copy | set_clipboard | paste | paste_clipboard | screenshot | wait | clear_field | focus_window | list_windows | active_window | close_window | minimize_window | maximize_window | restore_window | activate_window | move_window | resize_window | arrange_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "dx":          {"type": "INTEGER", "description": "Relative mouse X movement"},
                "dy":          {"type": "INTEGER", "description": "Relative mouse Y movement"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "width":       {"type": "INTEGER", "description": "Window width for resize/arrange"},
                "height":      {"type": "INTEGER", "description": "Window height for resize/arrange"},
                "active":      {"type": "BOOLEAN", "description": "Allow current active window for close_window when true"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "sound_learning",
        "description": (
            "Learns and recognizes standard environmental sounds from the live microphone stream. "
            "Use when the user says things like 'esse e barulho de plastico', 'aprende esse som', "
            "'grava barulho padrao', 'identifica esse barulho', or asks to list/delete learned sounds. "
            "During learn/classify it records the next few seconds from the existing mic stream."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "learn/record | classify/identify | list | delete | status"},
                "label": {"type": "STRING", "description": "Name of the sound to learn, e.g. plastico amassando"},
                "name": {"type": "STRING", "description": "Alternative sound name for learn/delete"},
                "sound": {"type": "STRING", "description": "Alternative sound name"},
                "duration": {"type": "NUMBER", "description": "Seconds to record, default 3, max 12"},
                "seconds": {"type": "NUMBER", "description": "Alternative duration field"},
                "top_k": {"type": "INTEGER", "description": "Number of classification matches to return"},
                "save_sample": {"type": "BOOLEAN", "description": "Save wav sample, default true"}
            },
            "required": []
        }
    },
    {
        "name": "jarvis_lab",
        "description": (
            "Opens/closes/toggles the complementary Nexus Lab UI for Jarvis. "
            "Use when the user asks for modo laboratorio, tela complementar, Nexus Lab, lab do Jarvis, "
            "or wants the extra modules 5/7/8/9/11 visible outside the main HUD."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "open | close | toggle | status"}
            },
            "required": []
        }
    },
    {
        "name": "quick_command",
        "description": (
            "Runs and manages saved standard commands/macros. Use for phrases like 'abrir mine', "
            "'abrir Taskbar Hero', 'abrir Brawlhalla', 'salva esse comando padrão', "
            "'listar comandos padrão', 'pesquisar dados', 'pesquisar fórmula', and 'calcular conta'. "
            "Commands are persisted in memory/quick_commands.json."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "run | list | show | save | delete | seed | calculate | search | formula"},
                "name": {"type": "STRING", "description": "Saved command name to run/show/save/delete"},
                "command": {"type": "STRING", "description": "Natural saved command phrase, e.g. 'abrir mine'"},
                "description": {"type": "STRING", "description": "Description when saving a command"},
                "aliases": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Alternative phrases for the command"},
                "steps": {"type": "ARRAY", "items": {"type": "OBJECT"}, "description": "Macro steps: [{'tool':'open_app','parameters':{...}}]"},
                "tool": {"type": "STRING", "description": "Shortcut for saving one-step command"},
                "parameters": {"type": "OBJECT", "description": "Tool parameters for one-step save"},
                "app_name": {"type": "STRING", "description": "Shortcut for saving/opening an app command"},
                "query": {"type": "STRING", "description": "Search/formula topic or command lookup"},
                "text": {"type": "STRING", "description": "Text/query/value for command variables"},
                "value": {"type": "STRING", "description": "Value for command variables"},
                "expression": {"type": "STRING", "description": "Math expression for calculate"},
                "overwrite": {"type": "BOOLEAN", "description": "Replace existing command when saving"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "automation",
        "description": (
            "Runs and manages reusable automation macros made of multiple safe steps. "
            "Use when the user asks to automate a workflow, save an automation, run a macro, repeat actions, "
            "or execute a sequence combining keyboard/mouse, apps, browser, clipboard, image search, Spotify/smart home, or Obsidian."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "run | run_sequence | save | list | show | delete | defaults | status"},
                "name": {"type": "STRING", "description": "Macro name to run/show/save/delete"},
                "macro": {"type": "STRING", "description": "Alternative macro name"},
                "description": {"type": "STRING", "description": "Description when saving a macro"},
                "aliases": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Alternative voice phrases"},
                "steps": {"type": "ARRAY", "items": {"type": "OBJECT"}, "description": "Steps such as {'tool':'computer_control','parameters':{'action':'hotkey','keys':'ctrl+l'}} or shortcut {'action':'wait','seconds':1}"},
                "repeat": {"type": "INTEGER", "description": "Repeat count for run/run_sequence, capped for safety"},
                "query": {"type": "STRING", "description": "Variable available to steps as {query}"},
                "text": {"type": "STRING", "description": "Variable available to steps as {text}"},
                "value": {"type": "STRING", "description": "Variable available to steps as {value}"},
                "path": {"type": "STRING", "description": "Variable available to steps as {path}"},
                "count": {"type": "INTEGER", "description": "Variable available to steps as {count}"}
            },
            "required": []
        }
    },
    {
        "name": "game_updater",
        "description": (
            "Steam/Epic library operations only: installing, downloading, updating games, "
            "listing installed games, checking download status, and scheduling updates. "
            "For Steam Store prices or Steam Market items use steam_store. "
            "For controlling an already-open game's keyboard/mouse gameplay, use game_control."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "game_control",
        "description": (
            "Controls an open game with keyboard and mouse input. Use for gameplay commands like "
            "focus game window, launch by Steam/Epic app id, press/hold/release keys, WASD movement, "
            "jump, crouch, sprint, interact, reload, inventory, map, pause, mouse look/aim/click, "
            "short bounded sequences, and saving per-game key profiles. "
            "Do not use for cheating, anti-cheat bypass, or unattended farming."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "status | focus | launch | tap | hold | key_down | key_up | combo | mouse | sequence | stop | profile | forward | back | left | right | jump | crouch | sprint | interact | reload | inventory | map | pause"
                },
                "game": {"type": "STRING", "description": "Game/profile name or window title fragment"},
                "game_name": {"type": "STRING", "description": "Game name/window title fragment"},
                "window_title": {"type": "STRING", "description": "Window title fragment to focus"},
                "platform": {"type": "STRING", "description": "steam | epic for launch"},
                "app_id": {"type": "STRING", "description": "Steam/Epic app id for launch"},
                "path": {"type": "STRING", "description": "Executable/shortcut path for launch"},
                "profile": {"type": "STRING", "description": "Saved key profile name"},
                "profile_action": {"type": "STRING", "description": "show | list | save"},
                "bindings": {"type": "OBJECT", "description": "Key bindings to save in a profile, e.g. {'jump':'space','inventory':'e'}"},
                "key": {"type": "STRING", "description": "Single key or mapped command key"},
                "keys": {"type": "STRING", "description": "Hotkey combo such as alt+tab or ctrl+shift+esc"},
                "command": {"type": "STRING", "description": "Mapped command: forward, jump, reload, inventory, etc."},
                "seconds": {"type": "NUMBER", "description": "Hold/mouse duration, capped for safety"},
                "repeat": {"type": "INTEGER", "description": "Repeat count, capped for safety"},
                "interval": {"type": "NUMBER", "description": "Delay between taps/sequence steps"},
                "mode": {"type": "STRING", "description": "mouse mode: move | look | aim | click | scroll"},
                "mouse_action": {"type": "STRING", "description": "Alternative mouse mode"},
                "dx": {"type": "INTEGER", "description": "Relative mouse X movement"},
                "dy": {"type": "INTEGER", "description": "Relative mouse Y movement"},
                "x": {"type": "INTEGER", "description": "Absolute mouse X coordinate"},
                "y": {"type": "INTEGER", "description": "Absolute mouse Y coordinate"},
                "button": {"type": "STRING", "description": "left | right | middle"},
                "clicks": {"type": "INTEGER", "description": "Mouse click count"},
                "amount": {"type": "INTEGER", "description": "Mouse scroll amount"},
                "sequence": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Bounded key/action sequence"},
                "steps": {"type": "ARRAY", "items": {"type": "OBJECT"}, "description": "Advanced bounded sequence steps"},
                "dry_run": {"type": "BOOLEAN", "description": "Preview without sending input"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "steam_store",
        "description": (
            "Steam Store and Steam Community Market lookup for current prices, costs, DLCs, packs, and market items. "
            "Use for TBH/Task Bar Hero/Taskbarheroes price questions, app details, market price checks, and saving TBH price snapshots into Obsidian brain. "
            "For installing/updating games use game_updater; for gameplay keyboard/mouse use game_control."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "status | set_config | search | details | price | market | item | taskbar_hero | save_taskbar_hero | open_store | open_market"},
                "query": {"type": "STRING", "description": "Steam store or market search query"},
                "game": {"type": "STRING", "description": "Game name, e.g. Task Bar Hero"},
                "game_name": {"type": "STRING", "description": "Alternative game name"},
                "appid": {"type": "STRING", "description": "Steam AppID"},
                "app_id": {"type": "STRING", "description": "Steam AppID alias"},
                "item": {"type": "STRING", "description": "Steam Market item name"},
                "market_hash_name": {"type": "STRING", "description": "Exact Steam Market hash name"},
                "market_query": {"type": "STRING", "description": "Market search query for snapshots"},
                "count": {"type": "INTEGER", "description": "Maximum Store/Market results"},
                "country": {"type": "STRING", "description": "Steam country code, default BR"},
                "language": {"type": "STRING", "description": "Steam language, default brazilian"},
                "market_currency": {"type": "INTEGER", "description": "Steam market currency id, default 7 for BRL"}
            },
            "required": []
        }
    },
    {
        "name": "game_vision",
        "description": (
            "Game-focused screen vision mode. Use when the user wants Jarvis to see, watch, or analyze an active game screen, especially TBH: Task Bar Hero. "
            "It focuses the game window, sends a game-aware vision prompt, can run once or live, and stays silent unless the vision module is explicitly configured to speak."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "start | once | analyze | stop | status | set_config"},
                "game": {"type": "STRING", "description": "Game/profile name, e.g. taskbar hero"},
                "game_name": {"type": "STRING", "description": "Alternative game/profile name"},
                "window_title": {"type": "STRING", "description": "Window title fragment to focus"},
                "launch": {"type": "BOOLEAN", "description": "Launch known game before vision when supported"},
                "focus": {"type": "BOOLEAN", "description": "Focus game window before capture"},
                "interval": {"type": "NUMBER", "description": "Live vision interval seconds"},
                "text": {"type": "STRING", "description": "Additional game analysis instruction"},
                "prompt": {"type": "STRING", "description": "Additional game analysis prompt"},
                "market_hint": {"type": "STRING", "description": "Optional item/value focus for Steam Market awareness"}
            },
            "required": []
        }
    },    {
        "name": "spotify_control",
        "description": (
            "Controls the local Spotify desktop app on this computer. "
            "Use for simple Spotify commands: play, pause, next, previous, shuffle, repeat, "
            "liked songs, current track, local volume, search, playlists, queue, lyrics, devices."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | pause | next | previous | shuffle | repeat | liked | current | volume_up | volume_down | search | playlist | home | queue | lyrics | devices"},
                "query":  {"type": "STRING", "description": "Search query for Spotify search"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "smart_home",
        "description": (
            "Controls Spotify Connect through the Spotify Web API and smart devices. "
            "Use domain='spotify' for account setup, devices, playback on phone/speaker/PC, "
            "search, playlists, queue, current track, liked songs, recent tracks, and recommendations. "
            "Spotify credentials are read from config/spotify_credentials.json; do not ask for them in chat. "
            "If credentials are present but not authorized, use action='setup' or 'status' to show the auth link."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "domain":        {"type": "STRING", "description": "spotify | wifi | bluetooth | discover | register"},
                "action":        {"type": "STRING", "description": "Spotify: status | login | configure | setup | callback | code | play | pause | next | previous | volume | search | current | shuffle | repeat | devices | queue | playlists | playlist_play | liked | recent | recommend"},
                "device":        {"type": "STRING", "description": "Device name for Spotify Connect, Bluetooth, or smart home device"},
                "query":         {"type": "STRING", "description": "Song, artist, playlist, callback URL, or other search/query text"},
                "value":         {"type": "STRING", "description": "Volume or other numeric value"},
                "client_id":     {"type": "STRING", "description": "Spotify app Client ID for configure"},
                "client_secret": {"type": "STRING", "description": "Spotify app Client Secret for configure"},
                "url":           {"type": "STRING", "description": "Full Spotify callback URL"}
            },
            "required": ["domain", "action"]
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "shutdown_jarvis",
        "description": (
            "Shuts down the assistant completely. "
            "Call this when the user expresses intent to end the conversation, "
            "close the assistant, say goodbye, or stop Jarvis. "
            "The user can say this in ANY language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "live_vision",
        "description": (
            "Enables real-time screen vision with AI analysis. "
            "Use this when the user asks to see, watch, look at screen, or analyze screen. "
            "There are two separate camera modes: "
            "1) vision mode for watching/processing the house or room with mode='camera', continuous=true, and record=true when the user asks to record, but do not retain raw video files; "
            "2) Braille/Braile translator only when the user explicitly says braille/braile. Save Braille knowledge only after stable 100% confirmation."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "text":       {"type": "STRING", "description": "What to ask about the screen"},
                "mode":       {"type": "STRING", "description": "screen, camera, or stop"},
                "continuous": {"type": "BOOLEAN", "description": "Enable continuous monitoring"},
                "interval":   {"type": "NUMBER", "description": "Seconds between continuous camera/screen checks"},
                "record":     {"type": "BOOLEAN", "description": "Process webcam stream for house/room vision mode without retaining raw video"},
                "fps":        {"type": "NUMBER", "description": "Camera processing frames per second"}
            },
            "required": []
        }
    },
    {
        "name": "camera_hand_ui",
        "description": (
            "Opens a local webcam UI with a futuristic overlay that tracks the user's hand. "
            "Use when the user asks for camera UI, squares following the hand, hand tracking, "
            "drawing with fingers, or Braille camera UI. Modes: hand, braille, draw/desenho. "
            "In Braille mode it draws finger/bone alignment and shows the detected Braille signal. "
            "In drawing mode the fingertip draws neon strokes and the UI shows instructions. "
            "Use action='stop' when the user asks to close, stop, quit, sair, encerrar, or fechar the Braille/camera UI."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "start/open/abrir, stop/close/fechar/sair/encerrar, status, or run"},
                "mode": {"type": "STRING", "description": "hand, braille, or draw/desenho"},
                "camera_index": {"type": "INTEGER", "description": "Optional camera index"},
                "width": {"type": "INTEGER", "description": "Camera width, default 1280"},
                "height": {"type": "INTEGER", "description": "Camera height, default 720"},
                "mirror": {"type": "BOOLEAN", "description": "Mirror camera image, default true"},
                "squares": {"type": "INTEGER", "description": "Number of tracking squares, default 28"},
                "braille_mode": {"type": "BOOLEAN", "description": "Show Braille finger/bone alignment, default true"}
            },
            "required": []
        }
    },
    {
        "name": "file_processor",
        "description": (
            "Processes any file that the user has uploaded or dropped onto the interface. "
        "Use this when the user refers to an uploaded file and wants an action on it. "
        "Supports: images (describe/ocr/resize/compress/convert), "
        "PDFs (summarize/extract_text/to_word), "
        "Word docs & text files (summarize/fix/reformat/translate), "
        "CSV/Excel (analyze/stats/filter/sort/convert), "
        "JSON/XML (validate/format/analyze), "
        "code files (explain/review/fix/optimize/run/document/test), "
        "audio (transcribe/trim/convert/info), "
        "video (trim/extract_audio/extract_frame/compress/transcribe/info), "
        "archives (list/extract), "
        "presentations (summarize/extract_text). "
        "ALWAYS call this tool when a file has been uploaded and the user gives a command about it. "
        "If the user's command is ambiguous, pick the most logical action for that file type."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Full path to the uploaded file. Leave empty to use the currently uploaded file."
            },
            "action": {
                "type": "STRING",
                "description": (
                    "What to do with the file. Examples by type:\n"
                    "image: describe | ocr | resize | compress | convert | info\n"
                    "pdf: summarize | extract_text | to_word | info\n"
                    "docx/txt: summarize | fix | reformat | translate_hint | word_count | to_bullet\n"
                    "csv/excel: analyze | stats | filter | sort | convert | info\n"
                    "json: validate | format | analyze | to_csv\n"
                    "code: explain | review | fix | optimize | run | document | test\n"
                    "audio: transcribe | trim | convert | info\n"
                    "video: trim | extract_audio | extract_frame | compress | transcribe | info | convert\n"
                    "archive: list | extract\n"
                    "pptx: summarize | extract_text | analyze"
                )
            },
            "instruction": {
                "type": "STRING",
                "description": "Free-form instruction if action doesn't cover it. E.g. 'translate this to Turkish', 'find all email addresses'"
            },
            "format": {
                "type": "STRING",
                "description": "Target format for conversion. E.g. 'mp3', 'pdf', 'csv', 'png'"
            },
            "width":     {"type": "INTEGER", "description": "Target width for image resize"},
            "height":    {"type": "INTEGER", "description": "Target height for image resize"},
            "scale":     {"type": "NUMBER",  "description": "Scale factor for image resize (e.g. 0.5)"},
            "quality":   {"type": "INTEGER", "description": "Quality 1-100 for image/video compress"},
            "start":     {"type": "STRING",  "description": "Start time for trim: seconds or HH:MM:SS"},
            "end":       {"type": "STRING",  "description": "End time for trim: seconds or HH:MM:SS"},
            "timestamp": {"type": "STRING",  "description": "Timestamp for video frame extraction HH:MM:SS"},
            "column":    {"type": "STRING",  "description": "Column name for CSV filter/sort"},
            "value":     {"type": "STRING",  "description": "Filter value for CSV filter"},
            "condition": {"type": "STRING",  "description": "Filter condition: equals|contains|gt|lt"},
            "ascending": {"type": "BOOLEAN", "description": "Sort order for CSV sort (default: true)"},
            "save":      {"type": "BOOLEAN", "description": "Save result to file (default: true)"},
            "destination": {"type": "STRING", "description": "Output folder for archive extract"},
        },
        "required": []
    }
},
    {
        "name": "read_memory",
        "description": (
            "MANDATORY personal memory reader. Read the current long-term personal memory loaded from memory/long_term.json. "
            "Use before answering about Lucas/Sabrina identity, preferences, projects, relationships, saved commands, or anything the user says Jarvis should remember. "
            "This is personal memory; use search_knowledge for Obsidian/vault knowledge."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Optional topic to focus the memory summary"},
                "category": {"type": "STRING", "description": "Optional memory category"}
            },
            "required": []
        }
    },    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Fatih, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "info_service",
        "description": (
            "Get various information: weather, crypto prices (BTC, ETH), stock prices, "
            "news, sports scores, currency exchange, word definitions, random facts, trivia, "
            "population data, Brazilian B3 stocks (PETR4, VALE3), Ibovespa index, mini contracts, "
            "and Brazilian market news. Use for any information query."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "type": {"type": "STRING", "description": "Type of info: crypto, crypto_brl, stock, ibovespa, mini, market_news, weather, news, sports, currency, definition, fact, trivia, population, real_estate, real_estate_news, financing"},
                "action": {"type": "STRING", "description": "Specific action if needed (e.g., portfolio for multiple stocks)"},
                "coin": {"type": "STRING", "description": "Cryptocurrency name (bitcoin, ethereum, etc.) for crypto type"},
                "symbol": {"type": "STRING", "description": "Stock symbol (AAPL, PETR4, VALE3, ITUB4, etc.) for stock type"},
                "city": {"type": "STRING", "description": "City name for weather"},
                "topic": {"type": "STRING", "description": "Topic for news search"},
                "sport": {"type": "STRING", "description": "Sport type for sports (football, basketball, etc.)"},
                "team": {"type": "STRING", "description": "Team name for sports"},
                "from": {"type": "STRING", "description": "Source currency code (USD, EUR, etc.)"},
                "to": {"type": "STRING", "description": "Target currency code (BRL, EUR, etc.)"},
                "amount": {"type": "NUMBER", "description": "Amount to convert"},
                "word": {"type": "STRING", "description": "Word to define"},
                "country": {"type": "STRING", "description": "Country name for population"},
                "days": {"type": "INTEGER", "description": "Number of forecast days (for weather)"},
                "currency": {"type": "STRING", "description": "Currency for crypto (usd, brl, eur)"},
                "zone": {"type": "STRING", "description": "Zone for real estate: zona sul, zona norte, zona leste, zona oeste, centro, abcd"},
                "developer": {"type": "STRING", "description": "Construction company name for real estate (e.g., Cyrela, MRV, Eztec)"},
                "city": {"type": "STRING", "description": "City for real estate data (default: sp)"}
            },
            "required": ["type"]
        }
    },
    {
        "name": "search_knowledge",
        "description": (
            "MANDATORY Obsidian brain reader. Modo pesquisa do cerebro Obsidian. Busca contexto relevante no vault D:\\xxxx_memory antes de responder. "
            "Use para qualquer pergunta que possa ter conhecimento no cerebro. Retorna resultados e trechos profundos quando deep=true."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Pergunta ou termo a buscar no cerebro"},
                "deep": {"type": "BOOLEAN", "description": "Incluir conteudo profundo das melhores notas"},
                "max_results": {"type": "INTEGER", "description": "Quantidade maxima de resultados"},
                "max_chars": {"type": "INTEGER", "description": "Limite de caracteres do contexto retornado"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "brain_mode",
        "description": (
            "Controla o modo cerebral full_neural do Jarvis. "
            "Use action='pesquisa' para contexto RAG do Obsidian, action='sono' para reindexar/consolidar em segundo plano, "
            "action='sleep_once' para reindexar agora, action='modulo' para trocar parametros leve/plus/pro/max/ultra, action='modulos' para listar, action='status' para status."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "status | pesquisa | sono | sleep_once | modulo | modulos | pin | fixar | start | stop_sleep"},
                "mode": {"type": "STRING", "description": "pesquisa | sono | full_neural"},
                "module": {"type": "STRING", "description": "Modulo de parametros: leve | plus | pro | max | ultra"},
                "modulo": {"type": "STRING", "description": "Alias de module"},
                "query": {"type": "STRING", "description": "Consulta para modo pesquisa"},
                "text": {"type": "STRING", "description": "Alias de query"},
                "deep": {"type": "BOOLEAN", "description": "Incluir conteudo profundo no modo pesquisa"},
                "max_results": {"type": "INTEGER", "description": "Quantidade maxima de resultados"},
                "max_chars": {"type": "INTEGER", "description": "Limite de caracteres do retorno"},
                "wait": {"type": "BOOLEAN", "description": "No modo sono, aguardar terminar em vez de rodar em background"},
                "run_sleep": {"type": "BOOLEAN", "description": "Ao ativar full_neural, rodar ciclo de sono imediatamente"},
                "context_budget_chars": {"type": "INTEGER", "description": "Orcamento operacional de contexto local"},
                "deep_count": {"type": "INTEGER", "description": "Quantidade de notas lidas profundamente"},
                "per_note_chars": {"type": "INTEGER", "description": "Caracteres lidos por nota profunda"},
                "max_context_budget_chars": {"type": "INTEGER", "description": "Teto de contexto operacional local"}
            },
            "required": []
        }
    },
    {
        "name": "local_llm",
        "description": (
            "Controla o modelo local real via Ollama. "
            "Use action='status' para ver modelo/parametros, action='fast' para modo rapido 1B, action='deep' para modo profundo 8B, action='start' para iniciar Ollama, "
            "action='pull' para baixar modelo, action='ask' para perguntar direto ao modelo local, "
            "e action='brain_answer' para responder usando contexto do Obsidian no modelo local."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "status | fast | deep | setup | start | list | pull | ask | brain_answer"},
                "model": {"type": "STRING", "description": "Modelo Ollama, ex: llama3.1:8b"},
                "modelo": {"type": "STRING", "description": "Alias de model"},
                "mode": {"type": "STRING", "description": "fast | deep"},
                "parameters_b": {"type": "NUMBER", "description": "Parametros aproximados em bilhoes"},
                "query": {"type": "STRING", "description": "Pergunta para o modelo local"},
                "prompt": {"type": "STRING", "description": "Prompt para o modelo local"},
                "text": {"type": "STRING", "description": "Alias de prompt/query"},
                "context_chars": {"type": "INTEGER", "description": "Contexto maximo do Obsidian no brain_answer"},
                "wait": {"type": "BOOLEAN", "description": "Aguardar pull terminar"},
                "num_ctx": {"type": "INTEGER", "description": "Janela de contexto do Ollama"},
                "num_predict": {"type": "INTEGER", "description": "Limite de tokens de saida do Ollama"},
                "timeout_seconds": {"type": "INTEGER", "description": "Timeout da chamada local"},
                "temperature": {"type": "NUMBER", "description": "Temperatura do modelo local"}
            },
            "required": []
        }
    },
    {
        "name": "brain_stats",
        "description": (
            "Mostra estatísticas do cérebro neural do XXXX. "
            "Use para saber quantas notas, categorias e informações estão armazenadas."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "phone_connect",
        "description": (
            "Conecta o JARVIS ao celular via Bluetooth. "
            "Use quando o usuário falar: 'conecta meu celular', 'conecta iPhone', 'liga o Bluetooth', "
            "'conectar telefone', 'parear celular', 'meu celular', 'connect phone', 'pair phone'. "
            "Também para: enviar SMS, fazer ligação, ver bateria, ver notificações. "
            "Action 'connect' é o padrão se não especificado."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "connect, status, sms, call, battery, notifications"},
                "number": {"type": "STRING", "description": "Número de telefone para SMS ou ligação"},
                "message": {"type": "STRING", "description": "Mensagem para enviar por SMS"}
            },
            "required": []
        }
    },
    {
        "name": "study_mode",
        "description": (
            "Controla o modo estudo ciclico. O XXXX expande o cérebro neural no Obsidian "
            "em ciclos contínuos, criando notas novas com timestamp em auto_study. "
            "Use start para iniciar, stop para parar, status para ver progresso, once para um ciclo único."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "start | stop | status | once"},
                "mode": {"type": "STRING", "description": "Alias de action: auto/deep/expand iniciam o ciclo"},
                "interval_seconds": {"type": "INTEGER", "description": "Intervalo entre ciclos, minimo 30s, padrao 300s"},
                "interval": {"type": "INTEGER", "description": "Alias de interval_seconds"},
                "topics_per_cycle": {"type": "INTEGER", "description": "Quantos topicos/conceitos estudar por ciclo, padrao 3"},
                "batch": {"type": "INTEGER", "description": "Alias de topics_per_cycle"},
                "run_now": {"type": "BOOLEAN", "description": "Executar primeiro ciclo imediatamente ao iniciar"}
            },
            "required": []
        }
    },
    {
        "name": "brain_expand",
        "description": (
            "Expande o cerebro neural com novo conhecimento. "
            "Use quando o usuário pedir para 'mandar informação pro cérebro' ou 'ensinar algo'. "
            "Cria novas notas no Obsidian com o conhecimento ensinado. "
            "SEMPRE organize automaticamente em pastas por categoria (imóveis, cannabis, tech, música, etc). "
            "Se houver notas órfãs na raiz, mova para a pasta correta."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "topic": {"type": "STRING", "description": "Tópico do conhecimento"},
                "content": {"type": "STRING", "description": "Conteúdo/informação a aprender"}
            },
            "required": ["topic", "content"]
        }
    },
    {
        "name": "brain_organize",
        "description": (
            "Organiza o próprio cérebro do JARVIS. "
            "Use quando o usuário pedir para 'organizar seu cérebro', 'limpar memórias', "
            "'ver suas memórias', ' estatisticas do cérebro', ou 'reorganizar conhecimento'. "
            "Ações: stats (mostrar estatísticas), clean (limpar duplicatas), "
            "rebuild (reconstruir índice neural), list (listar todas as memórias)."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "stats, clean, rebuild, list, consolidate"},
                "target": {"type": "STRING", "description": "O que organizar: memories, learned, neural, all"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "stop_thinking",
        "description": (
            "Para o modo pensamento e ativa o microfone novamente. "
            "Use quando terminar de estudar ou querer voltar a interagir normalmente."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
]

class JarvisLive:

    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self.ui.on_text_command = self._on_text_command
        self._turn_done_event: asyncio.Event | None = None
        self._voice_metrics: dict[str, dict | None] = {"user": None, "ai": None}
        self._voice_metric_ts: dict[str, float] = {"user": 0.0, "ai": 0.0}
        self._temporary_mute = False
        self._temporary_mute_lock = threading.Lock()

    def _on_text_command(self, text: str):
        if not self._loop or not self.session:
            return
        if self._handle_local_text_command(text):
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        elif self.is_temporary_muted():
            self.ui.set_state("WAKE MUTED")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def speak(self, text: str):
        if not self._loop or not self.session or self.is_temporary_muted():
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def is_temporary_muted(self) -> bool:
        with self._temporary_mute_lock:
            return self._temporary_mute

    def _set_temporary_mute(self, value: bool, wake_reply: str | None = None):
        with self._temporary_mute_lock:
            changed = self._temporary_mute != value
            self._temporary_mute = value

        if value:
            self._clear_audio_queue()
            if self._turn_done_event:
                self._turn_done_event.clear()
            self.set_speaking(False)
            if hasattr(self.ui, "set_temporary_mute"):
                self.ui.set_temporary_mute(True)
            else:
                self.ui.set_state("WAKE MUTED")
            if changed:
                self.ui.write_log("SYS: Mute temporário ativo. Diga JARVIS para voltar.")
        else:
            self._clear_audio_queue()
            if hasattr(self.ui, "set_temporary_mute"):
                self.ui.set_temporary_mute(False)
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            if changed:
                self.ui.write_log("SYS: Wake word detectada. JARVIS voltou.")
            if wake_reply:
                self.speak(wake_reply)

    def _clear_audio_queue(self):
        if not self.audio_in_queue:
            return
        while True:
            try:
                self.audio_in_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def _handle_local_text_command(self, text: str) -> bool:
        if _is_temp_mute_command(text):
            self._set_temporary_mute(True)
            return True

        if self.is_temporary_muted():
            if _has_wake_word(text):
                command = _strip_wake_word(text)
                self._set_temporary_mute(False)
                if command:
                    asyncio.run_coroutine_threadsafe(
                        self.session.send_client_content(
                            turns={"parts": [{"text": command}]},
                            turn_complete=True
                        ),
                        self._loop
                    )
                else:
                    self.speak("Voltei.")
            return True

        return False

    def _handle_voice_transcript_gate(self, full_in: str) -> bool:
        if not full_in:
            return False

        if self.is_temporary_muted():
            if _has_wake_word(full_in):
                command = _strip_wake_word(full_in)
                self._set_temporary_mute(False)
                if command:
                    self.speak(command)
                else:
                    self.speak("Voltei.")
            return True

        if _is_temp_mute_command(full_in):
            self._set_temporary_mute(True)
            return True

        return False

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory, include_vault=False)
        mem_categories = ", ".join(k for k, v in memory.items() if isinstance(v, dict) and v) or "none"
        memory_status = (
            "[MEMORY STATUS]\n"
            f"Long-term personal memory is loaded from memory/long_term.json. Categories: {mem_categories}.\n"
            "For personal facts/preferences/projects, use the provided memory summary or call read_memory. "
            "For Obsidian brain knowledge, call search_knowledge before answering.\n"
        )
        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        _learned_context = ""
        if _learning_available:
            try:
                _learned_context = _learning_module.get_context_for_ai()
            except Exception:
                pass

        parts = [time_ctx]
        if _learned_context:
            parts.append(_learned_context)
        if mem_str:
            parts.append(mem_str)
        parts.append(
            "[VAULT ACCESS]\n"
            "The Obsidian vault is available through search_knowledge and brain_mode pesquisa. "
            "Use brain_mode sono for background reindex/consolidation; the vault is not preloaded at startup so listening starts quickly."
        )
        parts.append(sys_prompt)

        return types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=VOICE_NAME
                    )
                )
            ),
        )

    def _publish_voice_metrics(self, source: str, data: bytes, sample_rate: int):
        if source not in self._voice_metrics or not data:
            return

        now = time.time()
        if now - self._voice_metric_ts.get(source, 0.0) < VOICE_METRIC_INTERVAL:
            return
        self._voice_metric_ts[source] = now

        metrics = _pcm_voice_metrics(data, sample_rate)
        if not metrics:
            return

        self._voice_metrics[source] = metrics
        payload = dict(metrics)
        payload["source"] = source
        payload["voice_name"] = VOICE_NAME
        payload["coupling"] = _voice_coupling(
            self._voice_metrics.get("user"),
            self._voice_metrics.get("ai"),
        )

        try:
            self.ui.update_voice_metrics(payload)
        except Exception:
            pass

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        print(f"[JARVIS] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")

        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                print(f"[Memory] 💾 save_memory: {category}/{key} = {value}")
                # Salvar também no disco D: para backup
                if _learning_available:
                    try:
                        _learning_module.save_memory_to_disk(category, key, value)
                    except Exception:
                        pass
                # Sincronizar com Obsidian
                if _neural_map_available:
                    try:
                        _neural_map_module.auto_sync_on_learn()
                        print("[Neural] Obsidian atualizado!")
                    except Exception:
                        pass
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        loop   = asyncio.get_event_loop()
        result = "Done."

        try:
            if name == "open_app":
                r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=self.ui))
                result = r or f"Opened {args.get('app_name')}."

            elif name == "weather_report":
                r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=self.ui))
                result = r or "Weather delivered."

            elif name == "browser_control":
                r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "file_controller":
                r = await loop.run_in_executor(None, lambda: file_controller_action(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "obsidian_control":
                r = await loop.run_in_executor(None, lambda: obsidian_control(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "send_message":
                r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None))
                result = r or f"Message sent to {args.get('receiver')}."

            elif name == "social_control":
                r = await loop.run_in_executor(None, lambda: social_control_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Social action completed."

            elif name == "iphone_bridge":
                r = await loop.run_in_executor(None, lambda: iphone_bridge_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "iPhone bridge updated."

            elif name == "iphone_shortcuts":
                r = await loop.run_in_executor(None, lambda: iphone_shortcuts_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "iPhone Shortcuts bridge updated."

            elif name == "operation_memory":
                r = await loop.run_in_executor(None, lambda: operation_memory_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Operational memory updated."

            elif name == "reminder":
                r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=self.ui))
                result = r or "Reminder set."

            elif name == "youtube_video":
                r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "screen_process":
                threading.Thread(
                    target=screen_process,
                    kwargs={"parameters": args, "response": None,
                            "player": self.ui, "session_memory": None},
                    daemon=True
                ).start()
                result = "Modo visão silencioso ativado. A análise vai para o log, sem narração automática."

            elif name == "computer_settings":
                r = await loop.run_in_executor(None, lambda: computer_settings(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "desktop_control":
                r = await loop.run_in_executor(None, lambda: desktop_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "code_helper":
                r = await loop.run_in_executor(None, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "dev_agent":
                r = await loop.run_in_executor(None, lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "agent_task":
                from agent.task_queue import get_queue, TaskPriority
                priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
                result   = f"Task started (ID: {task_id})."

            elif name == "web_search":
                r = await loop.run_in_executor(None, lambda: web_search_action(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "maps_mode":
                r = await loop.run_in_executor(None, lambda: maps_mode_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "image_search":
                r = await loop.run_in_executor(None, lambda: image_search_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "wallpaper_engine":
                r = await loop.run_in_executor(None, lambda: wallpaper_engine_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "info_service":
                from actions.info_service import info_service
                r = await loop.run_in_executor(None, lambda: info_service(parameters=args, player=self.ui, session_memory=None))
                result = r or "Done."

            elif name == "read_memory":
                memory_now = load_memory()
                category = str(args.get("category") or "").strip()
                query = str(args.get("query") or "").strip().lower()
                if category and isinstance(memory_now.get(category), dict):
                    scoped = {category: memory_now.get(category, {})}
                    result = format_memory_for_prompt(scoped, include_vault=False)
                else:
                    result = format_memory_for_prompt(memory_now, include_vault=False)
                if query:
                    lines = [line for line in result.splitlines() if query in line.lower()]
                    if lines:
                        result = "[MEMORY MATCHES]\n" + "\n".join(lines[:80])
                result = result or "Nenhuma memoria pessoal encontrada."
            elif name == "file_processor":
                if not args.get("file_path") and self.ui.current_file:
                    args["file_path"] = self.ui.current_file
                r = await loop.run_in_executor(
                    None,
                    lambda: file_processor(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Done."

            elif name == "computer_control":
                r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "sound_learning":
                r = await loop.run_in_executor(None, lambda: sound_learning_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "jarvis_lab":
                r = await loop.run_in_executor(None, lambda: jarvis_lab_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "quick_command":
                r = await loop.run_in_executor(None, lambda: quick_command(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "automation":
                r = await loop.run_in_executor(None, lambda: automation_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "game_updater":
                r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "game_control":
                r = await loop.run_in_executor(None, lambda: game_control(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "steam_store":
                r = await loop.run_in_executor(None, lambda: steam_store_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "game_vision":
                r = await loop.run_in_executor(None, lambda: game_vision_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "spotify_control":
                r = await loop.run_in_executor(None, lambda: spotify_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "smart_home":
                r = await loop.run_in_executor(None, lambda: smart_home(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "live_vision":
                r = await loop.run_in_executor(None, lambda: live_vision(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "camera_hand_ui":
                r = await loop.run_in_executor(None, lambda: camera_hand_ui(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "flight_finder":
                r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "search_knowledge":
                query = args.get("query", "")
                try:
                    payload = dict(args)
                    payload["action"] = "pesquisa"
                    payload["query"] = query
                    if payload.get("deep") is None:
                        payload["deep"] = True
                    r = await loop.run_in_executor(None, lambda: brain_mode_action(parameters=payload, player=self.ui, speak=self.speak))
                    result = r or "Nenhum resultado encontrado no vault."
                except Exception as e:
                    result = f"Erro na busca: {e}"

            elif name == "brain_mode":
                r = await loop.run_in_executor(None, lambda: brain_mode_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Brain mode atualizado."

            elif name == "local_llm":
                r = await loop.run_in_executor(None, lambda: local_llm_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Modelo local atualizado."
            elif name == "shutdown_jarvis":
                self.ui.write_log("SYS: Shutdown requested.")
                self.speak("Até mais.")
                def _shutdown():
                    import time, os
                    time.sleep(1)
                    os._exit(0)
                threading.Thread(target=_shutdown, daemon=True).start()

            elif name == "brain_stats":
                """Mostra estatísticas do cérebro neural."""
                try:
                    from memory.memory_manager import scan_vault_structure, _existing_vaults
                    structure = scan_vault_structure()
                    total = sum(structure.values())
                    categories = len(structure)
                    vaults = _existing_vaults()
                    result = f"📊 Cerebro Neural: {total} notas em {categories} categorias ({len(vaults)} vault(s))"
                except Exception as e:
                    result = f"Erro ao buscar stats: {e}"

            elif name == "phone_connect":
                r = await loop.run_in_executor(None, lambda: iphone_bridge_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "iPhone bridge updated."

            elif name == "study_mode":
                r = await loop.run_in_executor(None, lambda: study_mode_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Modo estudo atualizado."

            elif name == "study_mode_legacy":
                """Entra em modo estudo - expande o cérebro com tópicos aleatórios."""
                mode = args.get("mode", "auto")
                try:
                    # Importa scripts de expansão
                    import importlib.util
                    import random
                    from pathlib import Path
                    from datetime import datetime

                    scripts = [
                        r"D:\xxxx_memory\cerebro_central.py",
                        r"D:\xxxx_memory\dictionary_brain.py",
                        r"D:\xxxx_memory\brain_expander.py",
                    ]

                    expanded = 0
                    for script in scripts:
                        sp = Path(script)
                        if sp.exists():
                            spec = importlib.util.spec_from_file_location("exp", sp)
                            m = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(m)
                            expanded += 1

                    # ============================================
                    # EXPANSÃO AUTO-ESTUDO - Tópicos Aleatórios
                    # ============================================
                    STUDY_TOPICS = [
                        ("filosofia", "Filosofia", [
                            "Existencialismo - filosofia que enfatiza a existência e liberdade individual",
                            "Utilitarismo - teoria ética baseada na maximização da felicidade",
                            "Ceticismo - corrente que questiona a possibilidade de conhecimento certo",
                            "Materialismo - filosofia que sustenta que apenas matéria existe",
                            "Idealismo - filosofia que sustenta que a realidade é mental",
                            "Fenomenologia - estudo das experiências conscientes",
                            "Estoicismo - filosofia de resiliência e aceitação",
                            "Nietzsche - filosofia do Super-Homem e vontade de poder",
                            "Kant - filosofia crítica e imperativo categórico",
                            "Sartre - existencialismo ateu e liberdade radical",
                        ]),
                        ("matematica", "Matemática", [
                            "Teorema de Pitágoras - relação entre lados do triângulo retângulo",
                            "Número de Ouro - proporção áurea presente na natureza",
                            "Conjuntos - teoria dos conjuntos e operações",
                            "Cálculo - derivadas e integrais",
                            "Álgebra - equações e estruturas algébricas",
                            "Geometria - estudo de formas e espaços",
                            "Probabilidade - teoria das chances e eventos",
                            "Estatística - análise de dados e inferências",
                            "Topologia - estudo das propriedades invariantes",
                            "Teoria dos números - propriedades dos inteiros",
                        ]),
                        ("psicologia", "Psicologia", [
                            "Efeito placebo - melhora por expectativa",
                            "Viés de confirmação - tendência a buscar informações que confirmem crenças",
                            "Resiliência - capacidade de se recuperar de adversidades",
                            "Inteligência emocional - capacidade de reconhecer e gerenciar emoções",
                            "Teoria do apego - relação entre vínculos emocionais",
                            "Gesto primário - comportamento instintivo",
                            "Teoria cognitiva - processos de pensamento",
                            "Psicanálise - estudo do inconsciente",
                            "Behaviorismo - estudo do comportamento observável",
                            "Humanismo - abordagem centrada na pessoa",
                        ]),
                        ("astronomia", "Astronomia", [
                            "Buracos negros - regiões de gravidade extrema",
                            "Estrelas de nêutrons - núcleos colapsados de estrelas",
                            "Via Láctea - nossa galáxia",
                            "Planetas rochosos - Mercúrio, Vênus, Terra, Marte",
                            "Planetas gasosos - Júpiter, Saturno, Urano, Netuno",
                            "Asteroides - corpos rochosos entre Marte e Júpiter",
                            "Cometas - corpos gelados com cauda",
                            "Exoplanetas - planetas fora do sistema solar",
                            "Nebulosas - nuvens de gás e poeira cósmica",
                            "Big Bang - início do universo",
                        ]),
                        ("literatura", "Literatura", [
                            "Romantismo - movimento literário do século XIX",
                            "Realismo - representação fiel da realidade",
                            "Modernismo - ruptura com tradições",
                            "Trovadorismo - poesia medieval portuguesa",
                            "Modernismo brasileiro - Semana de Arte Moderna 1922",
                            "Machado de Assis - maior escritor brasileiro",
                            "Clarice Lispector - literatura íntima brasileira",
                            "Gabriel García Márquez - realismo mágico",
                            "Jorge Luis Borges - ficção filosófica",
                            "Shakespeare - teatro inglês renascentista",
                        ]),
                        ("arte", "Arte", [
                            "Renascimento - revolução artística séculos XV-XVI",
                            "Impressionismo - arte de luz e cor",
                            "Surrealismo - arte do inconsciente",
                            "Pintura barroca - dramaticidade e contraste",
                            "Art Nouveau - estilo ornamental",
                            "Arte contemporânea - expressões pós-modernas",
                            "Escultura grega - beleza idealizada",
                            "Pintura abstrata - arte sem representação",
                            "Fotografia - captura da realidade visual",
                            "Street art - arte urbana e grafite",
                        ]),
                        ("musica", "Música", [
                            "Harmonia - combinação de notas musicais",
                            "Ritmo - organização temporal dos sons",
                            "Melodia - sequência de notas",
                            "Orquestra - conjunto instrumental",
                            "Jazz - música improvisada americana",
                            "Rock - gênero musical de rock",
                            "MPB - música popular brasileira",
                            "Samba - ritmo brasileiro raiz",
                            "Clássica - música de concerto",
                            "Eletrônica - música digital e sintetizadores",
                        ]),
                        ("esportes", "Esportes", [
                            "VO2 máximo - consumo máximo de oxigênio",
                            "Período de recuperação - tempo para o corpo se recuperar",
                            "Hipertrofia - crescimento muscular por exercício",
                            "Aeróbico - metabolismo com oxigênio",
                            "Anaeróbico - metabolismo sem oxigênio",
                            "Alongamento - exercícios para flexibilidade",
                            "Treino intervalado - exercícios de alta intensidade",
                            "Resistência - capacidade de esforço prolongado",
                            "Força - capacidade de aplicar potência",
                            "Agilidade - capacidade de mudança rápida de direção",
                        ]),
                        ("culinaria", "Culinária", [
                            "Cozinha italiana - massas, pizzas, risotos",
                            "Cozinha japonesa - sushi, ramen, tempurá",
                            "Cozinha francesa - haute cuisine",
                            "Cozinha brasileira - regionalidades diversas",
                            "Cozinha mexicana - tacos, burritos, nachos",
                            "Cozinha indiana - curry, especiarias",
                            "Técnicas de preparo - assar, grelhar, refogar",
                            "Temperos - sal, pimenta, ervas",
                            "Conservação - métodos de preservar alimentos",
                            "Gastronomia molecular - ciência na cozinha",
                        ]),
                        ("negocios", "Negócios", [
                            "Marketing digital - estratégias online",
                            "Lean startup - metodologia ágil",
                            "Scrum - framework de gestão de projetos",
                            "Fintech - tecnologia financeira",
                            "E-commerce - comércio eletrônico",
                            "Startups - empresas inovadoras",
                            "Investimento anjo - capital para startups",
                            "MVP - produto mínimo viável",
                            "Pivot - mudança de estratégia",
                            "Scale-up - crescimento acelerado",
                        ]),
                    ]

                    # Criar notas dos tópicos de estudo aleatório
                    vault = Path(r"D:\xxxx_memory\30_Sistema\obsidian_data\xxxx-vault\YYYY")
                    study_folder = vault / "auto_study"
                    study_folder.mkdir(parents=True, exist_ok=True)

                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                    topics_learned = 0
                    facts_learned = 0

                    # Selecionar 3-5 tópicos aleatórios
                    selected_topics = random.sample(STUDY_TOPICS, min(5, len(STUDY_TOPICS)))

                    for topic_slug, topic_title, facts in selected_topics:
                        topic_folder = study_folder / topic_slug
                        topic_folder.mkdir(parents=True, exist_ok=True)

                        content = f"""---
created: {timestamp}
tags: [auto_estudo, neural, {topic_slug}]
type: study-note
neural-color: #9370DB
---

# 📖 {topic_title}

> Aprendizado automático em modo estudo - {timestamp}

## Conceitos Estudados

"""

                        for fact in facts:
                            content += f"- {fact}\n"

                        content += f"""
## Conexões
- [[Cerebro-Central|Cerebro Central]]
- [[YYYY-Learning|Aprendizado]]
- [[Memoria-Central|Memória Central]]

---
*Auto-estudo neural - {timestamp}*
"""

                        filename = topic_folder / f"{topic_slug}.md"
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(content)

                        topics_learned += 1
                        facts_learned += len(facts)

                    # Ativa modo pensamento - mute do mic
                    self.ui.muted = True
                    self.ui.write_log("SYS: Modo Pensamento ATIVADO - Microfone silenciado")

                    result = f"🧠 Modo Estudo ATIVADO. Cerebro expandido em {expanded} camadas + {topics_learned} tópicos estudados ({facts_learned} fatos). Microfone silenciado para concentração. Navegue no Obsidian para ver as novas conexões em auto_study."
                    print(f"[Study] Modo estudo: {result}")
                except Exception as e:
                    result = f"Erro no modo estudo: {e}"
                    print(f"[Study] Erro: {e}")

            elif name == "brain_expand":
                """Envia informação para o cérebro neural com organização inteligente."""
                topic = args.get("topic", "general")
                content = args.get("content", "")

                # Mapeamento de categorias por área - DETECÇÃO AUTOMÁTICA
                AUTO_CATEGORIES = {
                    # Imobiliário
                    "imovel": {"color": "#3498DB", "icon": "🏠", "folder": "imoveis", "tags": ["imobiliário", "imóveis"]},
                    "lead": {"color": "#2ECC71", "icon": "🎯", "folder": "imoveis", "tags": ["lead", "imobiliário"]},
                    "corretor": {"color": "#9B59B6", "icon": "💼", "folder": "imoveis", "tags": ["corretor", "imobiliário"]},
                    "constru": {"color": "#E74C3C", "icon": "🏗️", "folder": "imoveis", "tags": ["construção", "imobiliário"]},
                    # Cannabis
                    "cannabis": {"color": "#27AE60", "icon": "🌿", "folder": "cannabis", "tags": ["cannabis", "cultivo"]},
                    "thc": {"color": "#27AE60", "icon": "🌿", "folder": "cannabis", "tags": ["thc", "cannabis"]},
                    "cbd": {"color": "#27AE60", "icon": "🌿", "folder": "cannabis", "tags": ["cbd", "cannabis"]},
                    "cultivo": {"color": "#27AE60", "icon": "🌿", "folder": "cannabis", "tags": ["cultivo", "planta"]},
                    "planta": {"color": "#27AE60", "icon": "🌿", "folder": "cannabis", "tags": ["planta", "cultivo"]},
                    # Tecnologia
                    "python": {"color": "#34495E", "icon": "🐍", "folder": "tech", "tags": ["python", "programação"]},
                    "code": {"color": "#34495E", "icon": "💻", "folder": "tech", "tags": ["código", "programação"]},
                    "program": {"color": "#34495E", "icon": "💻", "folder": "tech", "tags": ["programação", "dev"]},
                    "ia": {"color": "#9B59B6", "icon": "🤖", "folder": "tech", "tags": ["ia", "inteligência artificial"]},
                    "api": {"color": "#34495E", "icon": "🔌", "folder": "tech", "tags": ["api", "tech"]},
                    # Música
                    "música": {"color": "#C44DFF", "icon": "🎵", "folder": "musica", "tags": ["música", "audio"]},
                    "rock": {"color": "#C44DFF", "icon": "🎸", "folder": "musica", "tags": ["rock", "música"]},
                    "spotify": {"color": "#C44DFF", "icon": "🎧", "folder": "musica", "tags": ["spotify", "música"]},
                    # Psicologia
                    "psico": {"color": "#E91E63", "icon": "🧠", "folder": "psicologia", "tags": ["psicologia", "mente"]},
                    "mente": {"color": "#E91E63", "icon": "🧠", "folder": "psicologia", "tags": ["psicologia", "mente"]},
                    # Viagem
                    "viagem": {"color": "#1ABC9C", "icon": "✈️", "folder": "viagens", "tags": ["viagem", "turismo"]},
                    "milha": {"color": "#1ABC9C", "icon": "✈️", "folder": "viagens", "tags": ["milhas", "viagem"]},
                    "passagem": {"color": "#1ABC9C", "icon": "✈️", "folder": "viagens", "tags": ["passagem", "viagem"]},
                    # Matemática
                    "matem": {"color": "#F39C12", "icon": "🔢", "folder": "estudo", "tags": ["matemática", "estudo"]},
                    "fórmul": {"color": "#F39C12", "icon": "🔢", "folder": "estudo", "tags": ["fórmula", "estudo"]},
                }

                def detect_category(topic: str, content: str) -> dict:
                    """Detecta a categoria baseada no tópico e conteúdo."""
                    text = (topic + " " + content).lower()
                    for key, cat in AUTO_CATEGORIES.items():
                        if key in text:
                            return cat
                    return {"color": "#9ACD32", "icon": "📝", "folder": "geral", "tags": ["aprendido"]}

                try:
                    from pathlib import Path
                    import re
                    from datetime import datetime

                    vault = Path(r"D:\xxxx_memory\30_Sistema\obsidian_data\xxxx-vault\YYYY")
                    learned = vault / "learned"

                    # Detectar categoria automaticamente
                    category_info = detect_category(topic, content)
                    folder_name = category_info["folder"]
                    color = category_info["color"]
                    icon = category_info["icon"]
                    tags = category_info["tags"] + [topic.lower()]

                    # Criar pasta organizada por categoria
                    category_folder = learned / folder_name
                    category_folder.mkdir(parents=True, exist_ok=True)

                    # Nome do arquivo limpo (sem acentos, espaços -> hifens)
                    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', topic.replace(' ', '-'))[:40]
                    timestamp = datetime.now().strftime('%Y%m%d-%H%M')

                    note_content = f"""---
created: {timestamp}
tags: [{', '.join(tags)}]
type: learned-note
neural-color: {color}
folder: {folder_name}
---

# {icon} {topic.title()}

> Ensinado ao XXXX - {timestamp}

## Conhecimento

{content}

## Conexoes Neurais
- [[Cerebro-Central|Cerebro Central]]
- [[Memoria-Central|Memoria Central]]
- [[YYYY-Learning|Aprendizado]]
---
*Aprendido - neural-color: {color}*
"""

                    filename = category_folder / f"note_{timestamp}.md"
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(note_content)

                    # AUTO-ORGANIZAÇÃO: verificar se precisa reorganizar
                    import shutil
                    learned = vault / "learned"
                    if learned.exists():
                        # Verificar se há notas fora das pastas organizadas
                        for note_file in learned.glob("*.md"):
                            if note_file.is_file() and note_file.stem != "indice-cerebro":
                                # Mover para pasta correta
                                content_check = note_file.read_text(encoding='utf-8', errors='ignore').lower()
                                filename_check = note_file.stem.lower()

                                keywords_map = {
                                    "imoveis": ["imovel", "lead", "corretor", "constru", "imobili", "zonaleste"],
                                    "cannabis": ["cannabis", "cannab", "thc", "cbd", "cultivo", "planta"],
                                    "tech": ["python", "code", "program", "api", "ia", "tech"],
                                    "musica": ["música", "rock", "spotify", "playlist"],
                                    "psicologia": ["psico", "mente", "psicologia"],
                                    "viagens": ["viagem", "milha", "passagem"],
                                    "estudo": ["matem", "fórmul", "estudo"],
                                }

                                for folder, keywords in keywords_map.items():
                                    if any(kw in filename_check or kw in content_check for kw in keywords):
                                        dest = learned / folder
                                        dest.mkdir(exist_ok=True)
                                        try:
                                            shutil.move(str(note_file), str(dest / note_file.name))
                                        except:
                                            pass
                                        break

                    result = f"✅ Informação enviada ao cérebro! {icon} Nota criada em: {folder_name}/{safe_name}. O XXXX aprendeu: {content[:80]}..."
                    print(f"[Brain] Nova nota criada: {filename} (categoria: {topic})")
                except Exception as e:
                    result = f"Erro ao enviar para cérebro: {e}"
                    print(f"[Brain] Erro: {e}")

            elif name == "brain_organize":
                """Organiza o próprio cérebro do JARVIS."""
                action = args.get("action", "stats").lower()
                target = args.get("target", "all").lower()

                try:
                    from pathlib import Path
                    import json

                    brain_root = Path(r"D:\xxxx_memory")
                    vault = brain_root / "obsidian_data" / "xxxx-vault"
                    memory_file = brain_root / "profile" / "memory_core.json"

                    if action == "stats":
                        # Mostrar estatísticas do cérebro
                        stats = {
                            "memórias": 0,
                            "categorias": {},
                            "última_atualização": "N/A"
                        }

                        if memory_file.exists():
                            with open(memory_file, 'r', encoding='utf-8') as f:
                                mem_data = json.load(f)
                                memory = mem_data.get('memory', {})
                                stats["memórias"] = sum(len(v) for v in memory.values() if isinstance(v, dict))
                                for cat, items in memory.items():
                                    if isinstance(items, dict):
                                        stats["categorias"][cat] = len(items)
                                stats["última_atualização"] = mem_data.get('last_updated', 'N/A')

                        # Contar notas no vault
                        note_count = 0
                        learned_count = 0
                        if vault.exists():
                            for folder in vault.rglob("*"):
                                if folder.is_dir() and folder.name != "YYYY":
                                    note_count += len(list(folder.glob("*.md")))
                                if "learned" in str(folder):
                                    learned_count += len(list(folder.glob("*.md")))

                        result = f"""🧠 CEREBRO DO JARVIS - ESTATÍSTICAS

📊 Memórias aprendidas: {stats['memórias']}
📁 Notas no Vault: {note_count}
📝 Notas de Aprendizado: {learned_count}
🕐 Última atualização: {stats['última_atualização']}

📂 Por categoria:
"""
                        for cat, count in stats['categorias'].items():
                            result += f"  • {cat}: {count}\n"

                    elif action == "list":
                        # Listar todas as memórias
                        if memory_file.exists():
                            with open(memory_file, 'r', encoding='utf-8') as f:
                                mem_data = json.load(f)
                                memory = mem_data.get('memory', {})

                            result = "🧠 TODAS AS MEMÓRIAS DO JARVIS:\n\n"
                            for cat, items in memory.items():
                                if isinstance(items, dict) and items:
                                    result += f"## {cat.upper()}\n"
                                    for key, data in items.items():
                                        val = data.get('value', data) if isinstance(data, dict) else data
                                        result += f"  • {key}: {val}\n"
                                    result += "\n"
                        else:
                            result = "Nenhuma memória encontrada."

                    elif action == "clean":
                        # Limpar duplicatas e dados antigos
                        cleaned = 0
                        if memory_file.exists():
                            with open(memory_file, 'r', encoding='utf-8') as f:
                                mem_data = json.load(f)

                            memory = mem_data.get('memory', {})
                            for cat, items in memory.items():
                                if isinstance(items, dict):
                                    seen = {}
                                    for key, data in list(items.items()):
                                        val = data.get('value', data) if isinstance(data, dict) else data
                                        if val in seen:
                                            del items[key]
                                            cleaned += 1
                                        else:
                                            seen[val] = key

                            with open(memory_file, 'w', encoding='utf-8') as f:
                                json.dump(mem_data, f, indent=2, ensure_ascii=False)

                        result = f"🧹 Cerebro limpo! {cleaned} itens duplicados/removidos."

                    elif action == "rebuild":
                        # Reconstruir índice neural
                        if _neural_map_available:
                            _neural_map_module.create_neural_category_folder()
                            _neural_map_module.create_neural_graph_index()
                            _neural_map_module.create_category_hubs()
                            _neural_map_module.sync_all_to_obsidian()
                            result = "🔄 Índice neural reconstruído! Estrutura do cérebro reorganizada."
                        else:
                            result = "Sistema neural não disponível."

                    elif action == "consolidate":
                        # Consolidar todas as memórias no Obsidian
                        if _neural_map_available:
                            _neural_map_module.sync_all_to_obsidian()
                            result = "💾 Todas as memórias consolidadas no Obsidian!"
                        else:
                            result = "Sistema neural não disponível."

                    elif action == "reorganize":
                        # REORGANIZAR - mover notas para pastas corretas
                        import shutil

                        learned = vault / "learned"
                        if not learned.exists():
                            result = "Pasta learned não encontrada."
                        else:
                            # Definir categorias de reorganização
                            reorganize_map = {
                                "imoveis": ["imovel", "lead", "corretor", "constru", "imobili", "zonaleste"],
                                "cannabis": ["cannabis", "cannab", "thc", "cbd", "cultivo", "planta", "especie", "frmuladebhaskara"],
                                "tech": ["python", "code", "program", "api", "ia", "tech", "autentic", "controlflow"],
                                "musica": ["música", "rock", "spotify", "playlist", "rockandroll", "paparoach"],
                                "psicologia": ["psico", "mente", "psicologia"],
                                "viagens": ["viagem", "milha", "passagem", "area"],
                                "estudo": ["matem", "fórmul", "estudo"],
                            }

                            moved = 0
                            created_folders = set()

                            # Criar pastas de destino
                            for folder in reorganize_map.keys():
                                dest = learned / folder
                                dest.mkdir(exist_ok=True)
                                created_folders.add(folder)

                            # Mover cada nota
                            for note_file in learned.glob("**/*.md"):
                                if note_file.is_file():
                                    folder_name = note_file.parent.name
                                    # Se já está em uma pasta organizada, pular
                                    if folder_name in reorganize_map.keys():
                                        continue
                                    # Verificar se precisa mover
                                    filename_lower = note_file.stem.lower()
                                    content_lower = note_file.read_text(encoding='utf-8', errors='ignore').lower()

                                    for target_folder, keywords in reorganize_map.items():
                                        if any(kw in filename_lower or kw in content_lower for kw in keywords):
                                            dest = learned / target_folder
                                            try:
                                                shutil.move(str(note_file), str(dest / note_file.name))
                                                moved += 1
                                                break
                                            except Exception:
                                                pass

                            # Criar índice reorganizado
                            index_content = """---
created: 2026-05-13
tags: [índice, reorganizado]
type: index-note
---

# 🧠 Índice do Cérebro Reorganizado

> Estrutura organizada de conhecimento.

## Categorias
"""
                            for folder in sorted(created_folders):
                                count = len(list((learned / folder).glob("*.md")))
                                index_content += f"- [[{folder}|{folder.title()}]]: {count} notas\n"

                            index_content += "\n---\n*Cérebro reorganizado automaticamente*"

                            with open(learned / "indice-cerebro.md", 'w', encoding='utf-8') as f:
                                f.write(index_content)

                            result = f"🔄 Cerebro reorganizado! {moved} notas movidas para pastas organizadas."

                    else:
                        result = f"Ação '{action}' não reconhecida. Use: stats, list, clean, rebuild, consolidate, reorganize"

                    print(f"[Brain] Organize: {action} - {result[:100]}")

                except Exception as e:
                    result = f"Erro ao organizar cérebro: {e}"
                    print(f"[Brain] Organize erro: {e}")

            elif name == "stop_thinking":
                """Para modo pensamento e ativa microfone."""
                try:
                    self.ui.muted = False
                    self.ui.write_log("SYS: Modo Pensamento DESATIVADO - Microfone ativo")
                    result = "✅ Modo pensamento desativado. Microfone ativo novamente. Puedo ouvi-lo agora!"
                except Exception as e:
                    result = f"Erro ao ativar microfone: {e}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            self.speak_error(name, e)

        if self.is_temporary_muted():
            self.ui.set_state("WAKE MUTED")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[JARVIS] OUT {name} → {str(result)[:80]}")
        response = {"result": result}
        if name in {"screen_process", "live_vision", "camera_hand_ui"}:
            response.update({
                "silent": True,
                "no_spoken_followup": True,
            })
        silent_capable = {"iphone_bridge", "iphone_shortcuts", "social_control", "operation_memory"}
        report_actions = {"status", "info", "events", "list", "listar", "latest", "ultimo", "last", "templates", "modelos", "url", "link", "help", "ajuda", "summary", "resumo"}
        action_name = str(args.get("action") or "").lower().strip()
        if name in silent_capable and (bool(args.get("silent")) or action_name not in report_actions):
            response.update({
                "silent": True,
                "no_spoken_followup": True,
            })
        return types.FunctionResponse(
            id=fc.id, name=name,
            response=response
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    def _put_out_queue_drop_oldest(self, msg):
        try:
            self.out_queue.put_nowait(msg)
        except asyncio.QueueFull:
            try:
                self.out_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self.out_queue.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    async def _receive_audio(self):
        print("[JARVIS] 👂 Recv started")
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():

                    audio_chunks = _live_inline_data_chunks(response)
                    if audio_chunks:
                        if self.is_temporary_muted():
                            continue
                        if self._turn_done_event and self._turn_done_event.is_set():
                            self._turn_done_event.clear()
                        for chunk in audio_chunks:
                            self.audio_in_queue.put_nowait(chunk)

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt:
                                out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()

                            full_in = " ".join(in_buf).strip()
                            if self._handle_voice_transcript_gate(full_in):
                                in_buf = []
                                out_buf = []
                                continue

                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                                _auto_learn_from_message(full_in)
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"Jarvis: {full_out}")
                            out_buf = []

                    if response.tool_call:
                        if self.is_temporary_muted():
                            ignored = [
                                types.FunctionResponse(
                                    id=fc.id,
                                    name=fc.name,
                                    response={"result": "Ignored while temporary mute is active.", "silent": True}
                                )
                                for fc in response.tool_call.function_calls
                            ]
                            await self.session.send_tool_response(function_responses=ignored)
                            continue
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[JARVIS] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )
        except asyncio.QueueFull:
            print("[JARVIS] WARN Audio buffer full, continuing...")
        except Exception as e:
            print(f"[JARVIS] FAIL Recv: {e}")
            traceback.print_exc()
            raise

    async def _receive_audio_text(self):
        """Text-only mode (no audio) - for when audio is not available"""
        print("[JARVIS] 📝 Text mode started")
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():
                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt:
                                out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()

                            full_in = " ".join(in_buf).strip()
                            if self._handle_voice_transcript_gate(full_in):
                                in_buf = []
                                out_buf = []
                                continue

                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                                _auto_learn_from_message(full_in)
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"Jarvis: {full_out}")
                            out_buf = []

                    if response.tool_call:
                        if self.is_temporary_muted():
                            ignored = [
                                types.FunctionResponse(
                                    id=fc.id,
                                    name=fc.name,
                                    response={"result": "Ignored while temporary mute is active.", "silent": True}
                                )
                                for fc in response.tool_call.function_calls
                            ]
                            await self.session.send_tool_response(function_responses=ignored)
                            continue
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[JARVIS] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )
        except Exception as e:
            print(f"[JARVIS] FAIL Text Recv: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[JARVIS] 🔊 Play started")
        stream = None
        retry_count = 0
        max_retries = 3
        last_audio_at = 0.0

        while retry_count < max_retries:
            try:
                if stream:
                    try:
                        stream.stop()
                        stream.close()
                    except:
                        pass

                stream = sd.RawOutputStream(
                    samplerate=RECEIVE_SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=CHUNK_SIZE,
                )
                stream.start()
                retry_count = 0
                print("[JARVIS] 🔊 Audio stream ready")

                while True:
                    try:
                        chunk = await asyncio.wait_for(
                            self.audio_in_queue.get(),
                            timeout=0.5
                        )
                    except asyncio.TimeoutError:
                        # Only stop speaking if queue is empty for a while AND turn is done
                        if (
                            self._turn_done_event
                            and self._turn_done_event.is_set()
                            and self.audio_in_queue.empty()
                            and last_audio_at > 0.0
                            and time.time() - last_audio_at >= SPEECH_TAIL_SECONDS
                        ):
                            self.set_speaking(False)
                            self._turn_done_event.clear()
                        continue
                    if self.is_temporary_muted():
                        self._clear_audio_queue()
                        self.set_speaking(False)
                        if self._turn_done_event:
                            self._turn_done_event.clear()
                        continue
                    self.set_speaking(True)
                    await asyncio.to_thread(stream.write, chunk)
                    last_audio_at = time.time()
            except Exception as e:
                retry_count += 1
                print(f"[JARVIS] WARN Play error ({retry_count}/{max_retries}): {e}")
                await asyncio.sleep(0.5)

        print("[JARVIS] ERROR Play: max retries exceeded")

    async def _listen_audio(self):
        print("[JARVIS] 🎤 Mic started")
        loop = asyncio.get_event_loop()
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                def callback(indata, frames, time_info, status):
                    data = indata.tobytes()
                    sound_capture_active = ingest_sound_audio(data, SEND_SAMPLE_RATE)
                    if not sound_capture_active and not self.ui.muted:
                        loop.call_soon_threadsafe(
                            self._publish_voice_metrics,
                            "user",
                            data,
                            SEND_SAMPLE_RATE,
                        )

                    with self._speaking_lock:
                        jarvis_speaking = self._is_speaking
                    if not sound_capture_active and not jarvis_speaking and not self.ui.muted:
                        loop.call_soon_threadsafe(
                            self._put_out_queue_drop_oldest,
                            {"data": data, "mime_type": "audio/pcm"}
                        )

                with sd.InputStream(
                    samplerate=SEND_SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=CHUNK_SIZE,
                    callback=callback,
                ):
                    print("[JARVIS] 🎤 Mic stream open")
                    retry_count = 0
                    while True:
                        await asyncio.sleep(0.1)
            except Exception as e:
                retry_count += 1
                print(f"[JARVIS] WARN Mic error ({retry_count}/{max_retries}): {e}")
                await asyncio.sleep(1)

        print("[JARVIS] ERROR Mic: max retries exceeded")

    async def run(self):
        use_proxy = True
        use_audio = True  # Fallback to text-only if audio fails
        reconnect_count = 0

        while True:
            try:
                print("[JARVIS] 🔌 Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                # Configure based on audio availability
                if use_audio:
                    config.response_modalities = [types.Modality.AUDIO]
                else:
                    config.response_modalities = [types.Modality.TEXT]
                    print("[JARVIS] 📝 Using text-only mode")

                client = genai.Client(
                    api_key=_get_api_key(),
                    http_options={"api_version": "v1beta"}
                )

                model_name = TEXT_MODEL if not use_audio else LIVE_MODEL
                async with (
                    client.aio.live.connect(model=model_name, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_event_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue(maxsize=10)
                    self._turn_done_event = asyncio.Event()

                    print("[JARVIS] OK Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: JARVIS online.")

                    # Only start audio tasks if audio mode is enabled
                    if use_audio:
                        tg.create_task(self._send_realtime())
                        tg.create_task(self._listen_audio())
                        tg.create_task(self._receive_audio())
                        tg.create_task(self._play_audio())
                    else:
                        tg.create_task(self._receive_audio_text())
                    reconnect_count = 0

            except Exception as e:
                err_str = str(e)
                reconnect_count += 1

                # Check for quota exhaustion
                if any(x in err_str.lower() for x in ["429", "quota", "resource_exhausted", "exceeded", "rate limit"]):
                    print(f"[JARVIS] WARN Quota exhausted: {err_str[:80]}")
                    # Try to switch API key
                    switched = handle_api_error(e, self.speak)
                    if switched:
                        self.ui.write_log("SYS: Switched to backup API key")
                        reconnect_count = 0
                        use_audio = True  # Try with audio again
                        continue
                    else:
                        self.speak("Sir, all API keys have exceeded their quota. Please add new keys.")
                elif "1008" in err_str or "policy violation" in err_str.lower():
                    print(f"[JARVIS] WARN Audio not available (1008): switching to text-only")
                    use_audio = False
                else:
                    print(f"[JARVIS] WARN {e}")
                    traceback.print_exc()

                # After 5 reconnects with audio, switch to text mode (avoid rate limit)
                if reconnect_count >= 5 and use_audio:
                    print(f"[JARVIS] WARN Multiple failures: switching to text-only mode")
                    use_audio = False

            self.set_speaking(False)
            self.ui.set_state("THINKING")
            # Faster backoff: 5s, 10s, 15s, max 30s
            delay = min(5 * (2 ** reconnect_count), 30)
            print(f"[JARVIS] SYNC Reconnecting in {delay}s...")
            await asyncio.sleep(delay)

def main():
    if os.environ.get("MARK_XL_BOOT_ANIMATION", "1") != "0":
        run_startup_animation(theme_color="magenta")

    # Load user name from memory for personalized greeting
    from memory.memory_manager import load_memory
    memory = load_memory()
    user_name = memory.get("identity", {}).get("name", {}).get("value", "Sir")

    ui = JarvisUI("face.png")
    if os.environ.get("MARK_XL_PRELOAD_NEURAL") == "1":
        _start_neural_background_load(delay=30.0)

    def start_iphone_shortcuts_bridge():
        if os.environ.get("MARK_XL_IPHONE_SHORTCUTS_AUTOSTART", "1") == "0":
            return
        time.sleep(3)
        try:
            result = iphone_shortcuts_action({"action": "start", "silent": True}, player=ui)
            ui.write_log(f"SYS: {result}")
        except Exception as exc:
            ui.write_log(f"SYS: iPhone Shortcuts Bridge offline: {str(exc)[:120]}")

    threading.Thread(target=start_iphone_shortcuts_bridge, daemon=True).start()

    # Define clap callback to wake JARVIS
    def on_clap():
        print("\n👏 Double clap detected!")
        if ui:
            # Show greeting and menu
            greeting = f"Hello, {user_name}! How can I assist you today?"
            ui.write_log(f"SYS: 👏 Clap detected - {greeting}")
            if hasattr(ui, 'speak') and ui.speak:
                ui.speak(greeting)

    # Enable clap detection in background
    def start_clap_detection():
        time.sleep(2)  # Wait for system to fully start
        if enable_clap_detection(on_clap):
            print("[JARVIS] 👂 Clap detection enabled - double clap to wake me!")

    threading.Thread(target=start_clap_detection, daemon=True).start()

    def runner():
        ui.wait_for_api_key()
        jarvis = JarvisLive(ui)
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()

if __name__ == "__main__":
    main()









