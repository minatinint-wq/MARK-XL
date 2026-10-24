"""Import one-time private transfer credentials on the destination PC."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CONFIG = ROOT / "config"


def main() -> int:
    fish_transfer = CONFIG / ".fish-key-transfer.txt"
    if fish_transfer.exists():
        from actions.fish_voice import save_key

        key = fish_transfer.read_text(encoding="utf-8").strip()
        if not key:
            print("[JARVIS] Chave Fish de transferencia vazia.")
            return 1
        try:
            save_key(key)
        except Exception as exc:
            print(f"[JARVIS] Nao foi possivel proteger a chave Fish neste PC: {type(exc).__name__}")
            return 1
        fish_transfer.unlink()
        print("[JARVIS] Chave Fish protegida para este usuario do Windows.")

    spotify_transfer = CONFIG / ".spotify-cache-transfer.json"
    if spotify_transfer.exists():
        spotify_cache = Path.home() / ".spotify_cache"
        if not spotify_cache.exists():
            shutil.copy2(spotify_transfer, spotify_cache)
            print("[JARVIS] Sessao Spotify importada; a conta pode pedir nova autorizacao.")
        else:
            print("[JARVIS] Sessao Spotify local existente preservada.")
        spotify_transfer.unlink()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
