from __future__ import annotations

import json
import math
import re
import sys
import threading
import time
import wave
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import numpy as np
except Exception:
    np = None


BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "memory"
PROFILES_PATH = MEMORY_DIR / "sound_profiles.json"
SAMPLES_DIR = MEMORY_DIR / "sound_samples"
DEFAULT_SAMPLE_RATE = 16000
MAX_RECORD_SECONDS = 12.0
MIN_RECORD_SECONDS = 0.6
FEATURE_BANDS = (
    60,
    120,
    180,
    260,
    380,
    550,
    800,
    1150,
    1650,
    2400,
    3400,
    4800,
    6800,
    8000,
)


@dataclass
class _Recording:
    label: str
    sample_rate: int
    duration: float
    started_at: float = field(default_factory=time.time)
    chunks: list[bytes] = field(default_factory=list)
    event: threading.Event = field(default_factory=threading.Event)

    @property
    def target_bytes(self) -> int:
        return int(self.sample_rate * self.duration * 2)

    @property
    def current_bytes(self) -> int:
        return sum(len(chunk) for chunk in self.chunks)


class _SoundMemory:
    def __init__(self):
        self.lock = threading.Lock()
        self.active: _Recording | None = None

    def begin(self, label: str, duration: float, sample_rate: int) -> _Recording:
        duration = max(MIN_RECORD_SECONDS, min(float(duration), MAX_RECORD_SECONDS))
        sample_rate = int(sample_rate or DEFAULT_SAMPLE_RATE)
        rec = _Recording(label=label, duration=duration, sample_rate=sample_rate)
        with self.lock:
            self.active = rec
        return rec

    def ingest(self, data: bytes, sample_rate: int) -> bool:
        with self.lock:
            rec = self.active
            if rec is None:
                return False
            if sample_rate and int(sample_rate) != rec.sample_rate:
                return True
            if data:
                rec.chunks.append(bytes(data))
            if rec.current_bytes >= rec.target_bytes or time.time() - rec.started_at >= rec.duration:
                rec.event.set()
            return True

    def finish(self, rec: _Recording) -> bytes:
        with self.lock:
            if self.active is rec:
                self.active = None
            rec.event.set()
            return b"".join(rec.chunks)

    def is_recording(self) -> bool:
        with self.lock:
            return self.active is not None


_MEMORY = _SoundMemory()


def ingest_sound_audio(data: bytes, sample_rate: int = DEFAULT_SAMPLE_RATE) -> bool:
    """Called by the main microphone callback. Returns True while a sound capture is active."""
    return _MEMORY.ingest(data, sample_rate)


def is_sound_learning_recording() -> bool:
    return _MEMORY.is_recording()


def _slug(text: str, fallback: str = "som") -> str:
    text = str(text or "").lower().strip()
    text = re.sub(r"[^a-z0-9\u00c0-\u017f]+", "_", text, flags=re.I)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:80] or fallback


def _load_profiles() -> dict[str, Any]:
    try:
        if PROFILES_PATH.exists():
            data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"version": 1, "profiles": {}, "events": []}


def _save_profiles(data: dict[str, Any]) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _pcm_to_float(audio: bytes) -> Any:
    if np is None:
        raise RuntimeError("numpy nao esta disponivel para aprendizado de sons.")
    usable = len(audio) - (len(audio) % 2)
    if usable <= 0:
        return np.asarray([], dtype=np.float32)
    arr = np.frombuffer(audio[:usable], dtype=np.int16).astype(np.float32) / 32768.0
    return arr


def _trim_silence(samples, threshold: float = 0.012):
    if samples.size == 0:
        return samples
    frame = max(160, min(800, samples.size // 20 or 160))
    mask = []
    for start in range(0, samples.size, frame):
        segment = samples[start:start + frame]
        mask.append(float(np.sqrt(np.mean(segment * segment))) >= threshold if segment.size else False)
    if not any(mask):
        return samples
    first = next(i for i, active in enumerate(mask) if active) * frame
    last = (len(mask) - next(i for i, active in enumerate(reversed(mask)) if active)) * frame
    return samples[max(0, first):min(samples.size, last)]


def _feature_vector(audio: bytes, sample_rate: int) -> tuple[list[float], dict[str, Any]]:
    samples = _trim_silence(_pcm_to_float(audio))
    if samples.size < int(sample_rate * 0.25):
        raise ValueError("audio curto ou silencioso demais para aprender.")

    samples = samples - float(np.mean(samples))
    rms = float(np.sqrt(np.mean(samples * samples)))
    peak = float(np.max(np.abs(samples)))
    zcr = float(np.mean(np.abs(np.diff(np.signbit(samples)).astype(np.float32)))) if samples.size > 1 else 0.0

    window = np.hanning(samples.size).astype(np.float32)
    spectrum = np.abs(np.fft.rfft(samples * window))
    freqs = np.fft.rfftfreq(samples.size, d=1.0 / sample_rate)
    if spectrum.size:
        spectrum[0] = 0.0
    total = float(np.sum(spectrum)) + 1e-9
    centroid = float(np.sum(freqs * spectrum) / total)
    cumulative = np.cumsum(spectrum)
    rolloff_idx = int(np.searchsorted(cumulative, cumulative[-1] * 0.85)) if cumulative.size else 0
    rolloff = float(freqs[min(rolloff_idx, freqs.size - 1)]) if freqs.size else 0.0
    flatness = float(math.exp(np.mean(np.log(spectrum + 1e-9))) / (np.mean(spectrum + 1e-9))) if spectrum.size else 0.0

    band_values: list[float] = []
    for low, high in zip(FEATURE_BANDS, FEATURE_BANDS[1:]):
        mask = (freqs >= low) & (freqs < high)
        band_values.append(float(np.sum(spectrum[mask])) if np.any(mask) else 0.0)
    band_total = sum(band_values) + 1e-9
    bands = [value / band_total for value in band_values]

    envelope_bins = 12
    envelope: list[float] = []
    bucket = max(1, samples.size // envelope_bins)
    for index in range(envelope_bins):
        segment = samples[index * bucket:(index + 1) * bucket]
        envelope.append(float(np.sqrt(np.mean(segment * segment))) if segment.size else 0.0)
    env_peak = max(envelope) or 1e-9
    envelope = [value / env_peak for value in envelope]

    vector = [
        min(1.0, rms * 8.0),
        min(1.0, peak),
        min(1.0, zcr * 4.0),
        min(1.0, centroid / 8000.0),
        min(1.0, rolloff / 8000.0),
        min(1.0, flatness),
        *bands,
        *envelope,
    ]
    details = {
        "duration_seconds": round(float(samples.size / sample_rate), 3),
        "rms": round(rms, 6),
        "peak": round(peak, 6),
        "zero_crossing": round(zcr, 6),
        "centroid_hz": round(centroid, 2),
        "rolloff_hz": round(rolloff, 2),
        "flatness": round(flatness, 6),
    }
    return [round(float(value), 6) for value in vector], details


def _save_wav(label: str, audio: bytes, sample_rate: int) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = SAMPLES_DIR / _slug(label)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{timestamp}-{_slug(label)}.wav"
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio)
    return str(path)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 1e-9 or nb <= 1e-9:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def _merge_average(old: list[float], new: list[float], old_count: int) -> list[float]:
    if not old or len(old) != len(new):
        return new
    count = max(0, int(old_count))
    return [round(((old[i] * count) + new[i]) / (count + 1), 6) for i in range(len(new))]


def _record_stream(label: str, duration: float, sample_rate: int) -> bytes:
    rec = _MEMORY.begin(label, duration, sample_rate)
    deadline = time.time() + rec.duration + 1.5
    while time.time() < deadline:
        if rec.event.wait(timeout=0.08):
            break
    return _MEMORY.finish(rec)


def _learn(
    label: str,
    duration: float,
    sample_rate: int,
    save_sample: bool = True,
    kind: str = "sound",
    emotion: str = "",
    relationship: str = "",
    note: str = "",
    transcribe: bool = False,
) -> str:
    if not label:
        return "Informe o nome do som. Exemplo: label='plastico amassando'."
    audio = _record_stream(label, duration, sample_rate)
    vector, details = _feature_vector(audio, sample_rate)
    profiles = _load_profiles()
    store = profiles.setdefault("profiles", {})
    key = _slug(label)
    now = datetime.now().isoformat(timespec="seconds")
    existing = store.get(key, {})
    sample_count = int(existing.get("sample_count") or 0)
    sample_path = _save_wav(label, audio, sample_rate) if save_sample else ""
    avg = _merge_average(existing.get("vector") or [], vector, sample_count)
    examples = list(existing.get("examples") or [])[-8:]
    examples.append({"created": now, "path": sample_path, "details": details})
    store[key] = {
        "label": label,
        "slug": key,
        "sample_count": sample_count + 1,
        "updated": now,
        "sample_rate": sample_rate,
        "vector": avg,
        "last_details": details,
        "examples": examples,
        "kind": kind,
        "emotion": emotion,
        "relationship": relationship,
    }
    _save_profiles(profiles)
    transcript = ""
    memory_note = ""
    try:
        from actions.affective_memory import observe_entity, remember_entity, transcribe_audio
        remember_entity(
            kind=kind,
            label=label,
            emotion=emotion,
            relationship=relationship,
            details=note or f"Perfil acustico aprendido com {sample_count + 1} amostra(s).",
            importance=0.7 if kind in {"voice", "person", "animal"} else 0.5,
            source="sound_learning",
        )
        if transcribe and sample_path:
            transcript = transcribe_audio(sample_path).get("text", "")
        memory = observe_entity(
            kind=kind,
            label=label,
            event="amostra de audio aprendida",
            details=f"centroid {details['centroid_hz']} Hz; rms {details['rms']}",
            confidence=1.0,
            transcript=transcript,
            source="sound_learning",
        )
        memory_note = str(memory.get("note_path") or "")
    except Exception as exc:
        memory_note = f"memoria afetiva pendente: {exc}"
    transcript_text = f" Fala transcrita: {transcript}" if transcript else ""
    return (
        f"Som aprendido: {label} ({sample_count + 1} amostra(s), tipo {kind}). "
        f"Assinatura: centroid {details['centroid_hz']} Hz, rms {details['rms']}. "
        f"Arquivo: {sample_path or 'nao salvo'}. Memoria: {memory_note}.{transcript_text}"
    )


def _classify(duration: float, sample_rate: int, top_k: int = 3) -> str:
    profiles = _load_profiles().get("profiles", {})
    if not profiles:
        return "Ainda nao ha sons aprendidos."
    audio = _record_stream("classificar", duration, sample_rate)
    vector, details = _feature_vector(audio, sample_rate)
    scored = []
    for key, profile in profiles.items():
        score = _cosine(vector, profile.get("vector") or [])
        scored.append((score, profile))
    scored.sort(key=lambda item: item[0], reverse=True)
    if scored and scored[0][0] >= 0.78:
        try:
            from actions.affective_memory import observe_entity
            best_score, best_profile = scored[0]
            observe_entity(
                kind=str(best_profile.get("kind") or "sound"),
                label=str(best_profile.get("label") or best_profile.get("slug")),
                event="assinatura sonora reconhecida",
                details=f"Audio de {details['duration_seconds']}s",
                confidence=best_score,
                source="sound_learning",
            )
        except Exception:
            pass
    top_k = max(1, min(int(top_k), 8))
    lines = [
        "Classificacao de som:",
        f"Audio capturado: {details['duration_seconds']}s, centroid {details['centroid_hz']} Hz",
    ]
    for score, profile in scored[:top_k]:
        confidence = int(round(score * 100))
        lines.append(f"- {profile.get('label', profile.get('slug'))}: {confidence}%")
    return "\n".join(lines)


def _list_profiles() -> str:
    profiles = _load_profiles().get("profiles", {})
    if not profiles:
        return "Nenhum som aprendido ainda."
    lines = [f"Sons aprendidos ({len(profiles)}):"]
    for key, profile in sorted(profiles.items()):
        details = profile.get("last_details") or {}
        lines.append(
            f"- {profile.get('label', key)}: {profile.get('sample_count', 0)} amostra(s), "
            f"centroid {details.get('centroid_hz', '--')} Hz"
        )
    return "\n".join(lines)


def _delete(label: str) -> str:
    profiles = _load_profiles()
    key = _slug(label)
    if key not in profiles.get("profiles", {}):
        return f"Som nao encontrado: {label}"
    profiles["profiles"].pop(key, None)
    _save_profiles(profiles)
    return f"Som removido da memoria auditiva: {label}"


def sound_learning(parameters: dict | None = None, player=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action") or "learn").lower().strip()
    sample_rate = int(params.get("sample_rate") or DEFAULT_SAMPLE_RATE)
    duration = float(params.get("duration") or params.get("seconds") or 3.0)

    if player:
        player.write_log(f"[SoundLearning] {action}")

    if action in {"status", "estado"}:
        state = "gravando" if is_sound_learning_recording() else "parado"
        return f"Memoria auditiva {state}. Perfis em: {PROFILES_PATH}"

    if action in {"learn", "record", "aprender", "gravar", "salvar"}:
        label = str(params.get("label") or params.get("name") or params.get("sound") or params.get("query") or "").strip()
        kind = str(params.get("kind") or params.get("type") or "sound").lower().strip()
        transcribe = bool(params.get("transcribe", kind in {"voice", "voz", "person", "pessoa"}))
        return _learn(
            label,
            duration,
            sample_rate,
            save_sample=bool(params.get("save_sample", True)),
            kind=kind,
            emotion=str(params.get("emotion") or params.get("affection") or ""),
            relationship=str(params.get("relationship") or ""),
            note=str(params.get("note") or params.get("details") or ""),
            transcribe=transcribe,
        )

    if action in {"classify", "identify", "identificar", "detectar", "compare"}:
        return _classify(duration, sample_rate, top_k=int(params.get("top_k") or 3))

    if action in {"list", "listar", "sons"}:
        return _list_profiles()

    if action in {"delete", "remove", "apagar"}:
        label = str(params.get("label") or params.get("name") or params.get("sound") or "").strip()
        return _delete(label)

    return "Acao invalida. Use learn, classify, list, delete ou status."


if __name__ == "__main__":
    print(sound_learning({"action": "status"}))
