import json
from pathlib import Path
from video_options import VIDEO_PROVIDERS, video_settings
SETTINGS_FILE = Path(__file__).resolve().parent / "studio_settings.json"
DEFAULT_VIDEO = {"provider": "ltx", "quality": "economy", "duration": 8, "aspect_ratio": "16:9 (Landscape)"}


def load_video_preferences():
    try:
        value = json.loads(SETTINGS_FILE.read_text(encoding="utf-8")).get("video", {})
        result = {key: value.get(key, default) for key, default in DEFAULT_VIDEO.items()}
        video_settings(**result)
        return result
    except (OSError, ValueError, TypeError, AttributeError):
        return DEFAULT_VIDEO.copy()


def save_video_preferences(provider, quality, duration, aspect_ratio):
    video_settings(provider, quality, aspect_ratio, duration)
    value = {"video": {"provider": provider, "quality": quality, "duration": duration, "aspect_ratio": aspect_ratio}}
    temp = SETTINGS_FILE.with_name(SETTINGS_FILE.name + ".tmp")
    try:
        temp.write_text(json.dumps(value, indent=2), encoding="utf-8")
        temp.replace(SETTINGS_FILE)
    finally:
        temp.unlink(missing_ok=True)
