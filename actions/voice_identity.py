"""Voice routing for the avatar modes; normal preserves Fish-first behavior."""
from actions.fish_voice import read_settings, read_key


def fish_config_for_identity(mode: str):
    # These identities deliberately use their Gemini native voice.
    # This is an explicit mode selection, never a slow-Fish fallback.
    if mode in {"evil", "cute"}:
        return {"enabled": False, "speed": 1.0}, ""
    return read_settings(), read_key()
