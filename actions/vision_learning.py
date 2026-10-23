from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
PROFILE_PATH = BASE_DIR / "memory" / "vision_learning.json"

DEFAULT_PROFILE = {
    "preferences": {
        "retain_temp_media": False,
        "vision_recording_policy": "process_delete",
        "screen_capture_policy": "process_only_no_screenshot_files",
        "braille_save_policy": "only_confirmed_100_percent",
        "braille_required_stable_frames": 5,
        "braille_min_confidence": 0.84,
    },
    "braille_signals": {},
    "vision_events": [],
}


def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        return json.loads(json.dumps(DEFAULT_PROFILE))
    try:
        data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return json.loads(json.dumps(DEFAULT_PROFILE))
    profile = json.loads(json.dumps(DEFAULT_PROFILE))
    if isinstance(data, dict):
        _merge_dict(profile, data)
    return profile


def save_profile(profile: dict) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_vision_preferences() -> None:
    profile = load_profile()
    save_profile(profile)
    cleanup_raw_vision_media()
    _persist_preferences_to_long_term(profile.get("preferences", {}))


def cleanup_raw_vision_media() -> int:
    removed = 0
    roots = [
        BASE_DIR / "memory" / "camera_recordings",
        BASE_DIR / "memory" / "camera_temp",
        BASE_DIR / "memory" / "screen_temp",
    ]
    for root in roots:
        if not root.exists():
            continue
        try:
            resolved_root = root.resolve()
            resolved_base = BASE_DIR.resolve()
            if not str(resolved_root).startswith(str(resolved_base)):
                continue
            for item in root.iterdir():
                if item.is_file() and item.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv", ".jpg", ".jpeg", ".png"}:
                    item.unlink()
                    removed += 1
        except Exception as e:
            print(f"[VisionLearning] Cleanup skipped for {root}: {e}")
    return removed


def _persist_preferences_to_long_term(prefs: dict) -> None:
    memory_path = BASE_DIR / "memory" / "long_term.json"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(memory_path.read_text(encoding="utf-8")) if memory_path.exists() else {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    preferences = data.setdefault("preferences", {})
    today = datetime.now().strftime("%Y-%m-%d")
    values = {
        "vision_recording_policy": prefs.get("vision_recording_policy", "process_delete"),
        "screen_capture_policy": prefs.get("screen_capture_policy", "process_only_no_screenshot_files"),
        "braille_save_policy": prefs.get("braille_save_policy", "only_confirmed_100_percent"),
        "vision_learning_mode": "stable-confirmation local feedback",
    }
    for key, value in values.items():
        preferences[key] = {"value": str(value), "updated": today}
    memory_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _persist_extra_preference(key: str, value: str) -> None:
    memory_path = BASE_DIR / "memory" / "long_term.json"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(memory_path.read_text(encoding="utf-8")) if memory_path.exists() else {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("preferences", {})[key] = {
        "value": str(value),
        "updated": datetime.now().strftime("%Y-%m-%d"),
    }
    memory_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def braille_confirmation_settings() -> tuple[int, float]:
    prefs = load_profile().get("preferences", {})
    stable_frames = int(prefs.get("braille_required_stable_frames", 5))
    min_confidence = float(prefs.get("braille_min_confidence", 0.84))
    return max(3, stable_frames), max(0.5, min(min_confidence, 0.98))


def remember_vision_event(mode: str, user_text: str, retained_media: bool = False) -> None:
    profile = load_profile()
    events = profile.setdefault("vision_events", [])
    events.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "intent": _clean_text(user_text)[:160],
        "retained_media": bool(retained_media),
    })
    del events[:-80]
    save_profile(profile)


def remember_braille_observation(result: Any) -> None:
    if not getattr(result, "detected", False):
        return
    profile = load_profile()
    key = _signal_key(getattr(result, "finger_count", None))
    signal = profile.setdefault("braille_signals", {}).setdefault(key, {
        "observations": 0,
        "confirmations": 0,
        "avg_confidence": 0.0,
        "last_seen": "",
        "braille": getattr(result, "braille", ""),
        "dots": getattr(result, "dots", ""),
    })
    observations = int(signal.get("observations", 0)) + 1
    old_avg = float(signal.get("avg_confidence", 0.0))
    conf = float(getattr(result, "confidence", 0.0) or 0.0)
    signal["observations"] = observations
    signal["avg_confidence"] = round(((old_avg * (observations - 1)) + conf) / observations, 3)
    signal["last_seen"] = datetime.now().isoformat(timespec="seconds")
    signal["braille"] = getattr(result, "braille", "")
    signal["dots"] = getattr(result, "dots", "")
    save_profile(profile)


def confirm_braille_signal(result: Any, stable_frames: int, avg_confidence: float) -> dict:
    count = getattr(result, "finger_count", None)
    key = _signal_key(count)
    profile = load_profile()
    signals = profile.setdefault("braille_signals", {})
    signal = signals.setdefault(key, {})
    signal["confirmations"] = int(signal.get("confirmations", 0)) + 1
    signal["last_confirmed"] = datetime.now().isoformat(timespec="seconds")
    signal["stable_frames"] = int(stable_frames)
    signal["confirmed_confidence"] = 1.0
    signal["avg_confirmation_confidence"] = round(float(avg_confidence), 3)
    signal["braille"] = getattr(result, "braille", "")
    signal["dots"] = getattr(result, "dots", "")
    save_profile(profile)

    note_path = _write_braille_note(result, signal)
    _persist_extra_preference(
        "last_confirmed_braille_signal",
        f"{count} fingers -> {getattr(result, 'braille', '')}",
    )
    return {"note_path": str(note_path), "confirmations": signal["confirmations"]}


def _write_braille_note(result: Any, signal: dict) -> Path:
    folder = _obsidian_braille_folder()
    folder.mkdir(parents=True, exist_ok=True)
    count = getattr(result, "finger_count", None)
    braille = getattr(result, "braille", "")
    dots = getattr(result, "dots", "")
    now = datetime.now().isoformat(timespec="seconds")
    filename = f"braille-numero-{count}.md"
    path = folder / filename
    content = f"""---
type: vision-learning
tags: [braille, vision, machine-learning, confirmed]
updated: {now}
confidence: 1.0
---

# Braille numero {count}

- Sinal Braille: `{braille}`
- Leitura falada: {dots}
- Confirmacao: 100% por estabilidade local
- Frames estaveis exigidos: {signal.get("stable_frames", "")}
- Confianca media antes da confirmacao: {signal.get("avg_confirmation_confidence", "")}
- Total de confirmacoes: {signal.get("confirmations", 0)}
- Ultima confirmacao: {signal.get("last_confirmed", now)}

## Politica de privacidade

O MARK XLIV processa camera e tela como fluxo temporario. Midia bruta nao e preservada.
Esta nota so foi atualizada porque o sinal Braille ficou estavel e confirmado.

## Uso

Quando o usuario mostrar {count} dedo(s), o tradutor Braille deve associar ao sinal `{braille}`.
"""
    path.write_text(content, encoding="utf-8")
    return path


def _obsidian_braille_folder() -> Path:
    candidates = [
        Path(r"D:\xxxx_memory\30_Sistema\obsidian_data\xxxx-vault\YYYY\learned"),
        Path(r"D:\xxxx_memory\obsidian_data\xxxx-vault\YYYY\learned"),
        Path(r"D:\xxxx_memory"),
        BASE_DIR / "memory" / "learned",
    ]
    for root in candidates:
        try:
            if root.exists():
                if root.name == "learned":
                    return root / "braille"
                return root / "learned" / "braille"
        except Exception:
            pass
    return BASE_DIR / "memory" / "learned" / "braille"


def _merge_dict(target: dict, source: dict) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_dict(target[key], value)
        else:
            target[key] = value


def _signal_key(count: Any) -> str:
    return f"number_{count}"


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
